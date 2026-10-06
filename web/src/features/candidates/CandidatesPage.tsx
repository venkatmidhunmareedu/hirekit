import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useState } from "react";

import { AlertIcon } from "../../components/AlertIcon";
import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { PageHeader } from "../../components/PageHeader";
import { errorMessage } from "../../lib/errors";
import { RoleTabs } from "../roles/RoleTabs";
import { budgetQueryOptions } from "../cost/hooks";
import { roleQueryOptions } from "../roles/hooks";

import { RankedTable } from "./RankedTable";
import { UploadZone } from "./UploadZone";
import { PAGE_SIZE, STAGES, type RankedPage, type Stage } from "./api";
import { STAGE_LABEL } from "./labels";
import { queueQueryOptions, rankedQueryOptions, useRescore } from "./hooks";

/** Candidates: upload and ranked list (Design.md 8.3, PRD steps 4 and 6). */
export function CandidatesPage() {
  const { roleId } = useParams({ strict: false });
  if (roleId === undefined) throw new Error("route has no roleId");
  // key: the stage filter and page belong to one role.
  return <Candidates key={roleId} roleId={roleId} />;
}

function Candidates({ roleId }: { roleId: string }) {
  const role = useQuery(roleQueryOptions(roleId));

  if (role.isPending) return <Loading label="Loading role" />;
  if (role.isError) {
    return (
      <ErrorNotice
        error={role.error}
        retry={() => {
          void role.refetch();
        }}
      />
    );
  }

  return (
    <div className="stack">
      <PageHeader title={role.data.title} />
      <RoleTabs roleId={roleId} status={role.data.status} current="candidates" />
      {role.data.status === "draft" ? (
        <div className="notice notice-info" role="status">
          <span>
            Approve the criteria to start uploading and scoring resumes. Candidates stay locked
            until then.
          </span>
          <Link to="/roles/$roleId" params={{ roleId }} className="btn btn-primary">
            Go to criteria
          </Link>
        </div>
      ) : (
        <>
          <UploadZone roleId={roleId} />
          <RankedList roleId={roleId} />
        </>
      )}
    </div>
  );
}

function RankedList({ roleId }: { roleId: string }) {
  const [stage, setStage] = useState<Stage | null>(null);
  const [offset, setOffset] = useState(0);
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [overridesOnly, setOverridesOnly] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const queue = useQuery(queueQueryOptions(roleId));
  const working = (queue.data?.waiting ?? 0) + (queue.data?.running ?? 0) > 0;
  const ranked = useQuery(rankedQueryOptions(roleId, stage, offset, working));

  return (
    <section aria-labelledby="ranked-heading" className="section">
      <h2 id="ranked-heading">Ranked candidates</h2>
      <p className="muted">
        Scores are AI suggestions that a person decides on. Hiding names reduces some bias but does
        not remove it: schools, clubs, wording and career gaps can still show. The hiring stage
        filter covers every candidate; the two checkboxes cover this page only.
      </p>
      <div className="field filter">
        <label htmlFor="stage-filter">Hiring stage</label>
        <select
          id="stage-filter"
          value={stage ?? ""}
          onChange={(e) => {
            setStage(STAGES.find((s) => s === e.target.value) ?? null);
            setOffset(0);
          }}
        >
          <option value="">All hiring stages</option>
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {STAGE_LABEL[s]}
            </option>
          ))}
        </select>
      </div>
      <div className="field filter">
        <label>
          <input
            type="checkbox"
            checked={flaggedOnly}
            onChange={(e) => {
              setFlaggedOnly(e.target.checked);
            }}
          />{" "}
          Needs a look only
        </label>
        <label>
          <input
            type="checkbox"
            checked={overridesOnly}
            onChange={(e) => {
              setOverridesOnly(e.target.checked);
            }}
          />{" "}
          Changed by recruiter
        </label>
      </div>
      {working && (
        <p role="status" className="notice notice-info">
          Processing resumes: {queue.data?.waiting ?? 0} waiting, {queue.data?.running ?? 0}{" "}
          running. The list refreshes by itself.
        </p>
      )}
      {ranked.isPending && <Loading label="Loading candidates" />}
      {ranked.isError && (
        <ErrorNotice
          error={ranked.error}
          retry={() => {
            void ranked.refetch();
          }}
        />
      )}
      {ranked.data && (
        <RankedBody
          roleId={roleId}
          page={ranked.data}
          filtered={stage !== null}
          flaggedOnly={flaggedOnly}
          overridesOnly={overridesOnly}
          selected={selected}
          onToggle={(id) => {
            setSelected((now) => (now.includes(id) ? now.filter((x) => x !== id) : [...now, id]));
          }}
          onOffset={setOffset}
        />
      )}
    </section>
  );
}

/** Out-of-date scores banner with the re-score action (Design.md section 11). */
function StaleBanner({ roleId }: { roleId: string }) {
  const rescore = useRescore(roleId);
  const budget = useQuery(budgetQueryOptions);
  const blocked = budget.data?.model_actions_allowed === false;
  return (
    <div role="status" className="notice notice-warning">
      <span>
        Scores are out of date. The criteria changed after some resumes were scored, so those still
        show the older results.
      </span>
      <button
        type="button"
        className="btn btn-secondary"
        disabled={rescore.isPending || blocked}
        onClick={() => {
          rescore.mutate();
        }}
      >
        Re-score
      </button>
      {rescore.isSuccess && (
        <span role="status">
          Re-scoring {rescore.data.queued} candidates; {rescore.data.skipped} skipped
        </span>
      )}
      {rescore.isError && (
        <span role="alert">
          <AlertIcon /> {errorMessage(rescore.error)}
        </span>
      )}
    </div>
  );
}

function RankedBody({
  roleId,
  page,
  filtered,
  flaggedOnly,
  overridesOnly,
  selected,
  onToggle,
  onOffset,
}: {
  roleId: string;
  page: RankedPage;
  filtered: boolean;
  flaggedOnly: boolean;
  overridesOnly: boolean;
  selected: string[];
  onToggle: (id: string) => void;
  onOffset: (offset: number) => void;
}) {
  const navigate = useNavigate();
  if (page.total === 0 && page.data.length === 0) {
    return (
      <EmptyState
        message={
          filtered
            ? "No candidates are in this hiring stage."
            : "No resumes yet. Upload PDF or DOCX files to see a ranked list."
        }
      />
    );
  }
  const anyStale = page.data.some((c) => c.stale);
  // Client-side, on the loaded page only: the API has no such filters.
  const shown = page.data.filter(
    (c) =>
      (!flaggedOnly || c.scores.some((s) => s.flag_reason !== null)) &&
      (!overridesOnly || c.scores.some((s) => s.override_score !== null)),
  );
  const canCompare = selected.length >= 2 && selected.length <= 4;
  const last = page.offset + page.data.length;
  return (
    <>
      {anyStale && <StaleBanner roleId={roleId} />}
      <div className="actions">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={!canCompare}
          onClick={() => {
            void navigate({ to: "/compare", search: { ids: selected.join(",") } });
          }}
        >
          Compare
        </button>
        <span className="muted" aria-live="polite">
          {selected.length} selected. Select 2 to 4 candidates to compare.
        </span>
      </div>
      {page.data.length === 0 ? (
        <EmptyState message="This page is past the last candidate. Go back to the previous page." />
      ) : shown.length === 0 ? (
        <EmptyState message="No candidates on this page match the filters." />
      ) : (
        <RankedTable
          candidates={shown}
          offset={page.offset}
          selected={selected}
          onToggle={onToggle}
        />
      )}
      <nav aria-label="Pages" className="actions">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={page.offset === 0}
          onClick={() => {
            onOffset(Math.max(0, page.offset - PAGE_SIZE));
          }}
        >
          Previous page
        </button>
        <span className="muted">
          {page.data.length === 0 ? 0 : page.offset + 1} to {last} of {page.total}
        </span>
        <button
          type="button"
          className="btn btn-secondary"
          disabled={last >= page.total}
          onClick={() => {
            onOffset(page.offset + PAGE_SIZE);
          }}
        >
          Next page
        </button>
      </nav>
    </>
  );
}
