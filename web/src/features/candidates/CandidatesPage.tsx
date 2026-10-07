import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { Notice } from "../../components/Notice";
import { PageHeader } from "../../components/PageHeader";
import { Section } from "../../components/Section";
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
    <div className="flex flex-col gap-8">
      <PageHeader title={role.data.title} />
      <RoleTabs roleId={roleId} status={role.data.status} current="candidates" />
      {role.data.status === "draft" ? (
        <Notice
          action={
            <Button asChild className="h-10 px-4">
              <Link to="/roles/$roleId" params={{ roleId }}>
                Go to criteria
              </Link>
            </Button>
          }
        >
          Approve the criteria to start uploading and scoring resumes. Candidates stay locked until
          then.
        </Notice>
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
    <Section
      id="ranked-heading"
      title="Ranked candidates"
      description="Scores are AI suggestions. Hiding names reduces some bias but does not remove it: schools, clubs and wording can still show."
    >
      <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="stage-filter">Hiring stage</Label>
          <Select
            value={stage ?? "all"}
            onValueChange={(value) => {
              setStage(STAGES.find((s) => s === value) ?? null);
              setOffset(0);
            }}
          >
            <SelectTrigger id="stage-filter" className="h-10 w-52">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All hiring stages</SelectItem>
              {STAGES.map((s) => (
                <SelectItem key={s} value={s}>
                  {STAGE_LABEL[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          <div className="flex min-h-10 items-center gap-2">
            <Checkbox
              id="flagged-only"
              checked={flaggedOnly}
              onCheckedChange={(checked) => {
                setFlaggedOnly(checked === true);
              }}
            />
            <Label htmlFor="flagged-only">Needs a look only</Label>
          </div>
          <div className="flex min-h-10 items-center gap-2">
            <Checkbox
              id="overrides-only"
              checked={overridesOnly}
              onCheckedChange={(checked) => {
                setOverridesOnly(checked === true);
              }}
            />
            <Label htmlFor="overrides-only">Changed by recruiter</Label>
          </div>
        </div>
      </div>
      {working && (
        <Notice>
          Processing resumes: {queue.data?.waiting ?? 0} waiting, {queue.data?.running ?? 0}{" "}
          running. The list refreshes by itself.
        </Notice>
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
    </Section>
  );
}

/** Out-of-date scores banner with the re-score action (Design.md section 11). */
function StaleBanner({ roleId }: { roleId: string }) {
  const rescore = useRescore(roleId);
  const budget = useQuery(budgetQueryOptions);
  const blocked = budget.data?.model_actions_allowed === false;
  return (
    <Notice
      tone="warning"
      action={
        <Button
          type="button"
          variant="outline"
          className="h-10 px-4"
          disabled={rescore.isPending || blocked}
          onClick={() => {
            rescore.mutate();
          }}
        >
          Re-score
        </Button>
      }
    >
      Scores are out of date. The criteria changed after some resumes were scored, so those still
      show the older results.
      {rescore.isSuccess && (
        <span role="status" className="mt-1 block">
          Re-scoring {rescore.data.queued} candidates; {rescore.data.skipped} skipped
        </span>
      )}
      {rescore.isError && (
        <span role="alert" className="mt-1 block text-bad">
          {errorMessage(rescore.error)}
        </span>
      )}
    </Notice>
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
      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          variant="outline"
          className="h-10 px-4"
          disabled={!canCompare}
          onClick={() => {
            void navigate({ to: "/compare", search: { ids: selected.join(",") } });
          }}
        >
          Compare
        </Button>
        <span className="text-sm text-muted-foreground" aria-live="polite">
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
      <nav aria-label="Pages" className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          variant="outline"
          className="h-10 px-4"
          disabled={page.offset === 0}
          onClick={() => {
            onOffset(Math.max(0, page.offset - PAGE_SIZE));
          }}
        >
          Previous page
        </Button>
        <span className="text-sm text-muted-foreground">
          {page.data.length === 0 ? 0 : page.offset + 1} to {last} of {page.total}
        </span>
        <Button
          type="button"
          variant="outline"
          className="h-10 px-4"
          disabled={last >= page.total}
          onClick={() => {
            onOffset(page.offset + PAGE_SIZE);
          }}
        >
          Next page
        </Button>
      </nav>
    </>
  );
}
