import { useQuery } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { useState } from "react";

import { AlertIcon } from "../../components/AlertIcon";
import { errorMessage } from "../../lib/errors";
import { RoleTabs } from "../roles/RoleTabs";
import { roleQueryOptions } from "../roles/hooks";

import { RankedTable } from "./RankedTable";
import { UploadZone } from "./UploadZone";
import { PAGE_SIZE, STAGES, type RankedPage, type Stage } from "./api";
import { queueQueryOptions, rankedQueryOptions } from "./hooks";

/** Candidates: upload and ranked list (Design.md 8.3, PRD steps 4 and 6). */
export function CandidatesPage() {
  const { roleId } = useParams({ strict: false });
  if (roleId === undefined) throw new Error("route has no roleId");
  // key: the stage filter and page belong to one role.
  return <Candidates key={roleId} roleId={roleId} />;
}

function Candidates({ roleId }: { roleId: string }) {
  const role = useQuery(roleQueryOptions(roleId));

  if (role.isPending) return <p role="status">Loading role</p>;
  if (role.isError) {
    return (
      <p role="alert" className="notice notice-danger">
        <AlertIcon />
        <span>{errorMessage(role.error)}</span>
        <button type="button" className="btn btn-secondary" onClick={() => void role.refetch()}>
          Try again
        </button>
      </p>
    );
  }

  return (
    <div className="stack">
      <h1>{role.data.title}</h1>
      <RoleTabs roleId={roleId} />
      {role.data.status === "draft" ? (
        <p className="notice notice-info" role="status">
          Approve the criteria to start uploading and scoring resumes. Candidates stay locked until
          then.
        </p>
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
  const queue = useQuery(queueQueryOptions(roleId));
  const working = (queue.data?.waiting ?? 0) + (queue.data?.running ?? 0) > 0;
  const ranked = useQuery(rankedQueryOptions(roleId, stage, offset, working));

  return (
    <section aria-labelledby="ranked-heading" className="stack">
      <h2 id="ranked-heading">Ranked candidates</h2>
      <p className="muted">
        Scores are model suggestions until a recruiter overrides them. Names are hidden. Hiding
        names reduces some bias but does not remove it: schools, clubs, wording and career gaps can
        still point to who someone is. A person decides, not the ranking.
      </p>
      <div className="field filter">
        <label htmlFor="stage-filter">Stage</label>
        <select
          id="stage-filter"
          value={stage ?? ""}
          onChange={(e) => {
            setStage(STAGES.find((s) => s === e.target.value) ?? null);
            setOffset(0);
          }}
        >
          <option value="">All stages</option>
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          ))}
        </select>
      </div>
      {working && (
        <p role="status">
          Processing resumes: {queue.data?.waiting ?? 0} waiting, {queue.data?.running ?? 0}{" "}
          running. The list refreshes by itself.
        </p>
      )}
      {ranked.isPending && <p role="status">Loading candidates</p>}
      {ranked.isError && (
        <p role="alert" className="notice notice-danger">
          <AlertIcon />
          <span>{errorMessage(ranked.error)}</span>
          <button type="button" className="btn btn-secondary" onClick={() => void ranked.refetch()}>
            Try again
          </button>
        </p>
      )}
      {ranked.data && (
        <RankedBody page={ranked.data} filtered={stage !== null} onOffset={setOffset} />
      )}
    </section>
  );
}

function RankedBody({
  page,
  filtered,
  onOffset,
}: {
  page: RankedPage;
  filtered: boolean;
  onOffset: (offset: number) => void;
}) {
  if (page.total === 0 && page.data.length === 0) {
    return (
      <p className="muted">
        {filtered
          ? "No candidates are in this stage."
          : "No resumes yet. Upload PDF or DOCX files to see a ranked list."}
      </p>
    );
  }
  const anyStale = page.data.some((c) => c.stale);
  const last = page.offset + page.data.length;
  return (
    <>
      {anyStale && (
        <p role="status" className="notice notice-warning">
          The criteria changed after some resumes were scored. Those scores are marked stale and
          still show the older results.
        </p>
      )}
      {page.data.length === 0 ? (
        <p className="muted">This page is past the last candidate. Go back to the previous page.</p>
      ) : (
        <RankedTable candidates={page.data} offset={page.offset} />
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
