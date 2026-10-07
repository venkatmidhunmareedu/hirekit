import { useQuery } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { FileUp, TriangleAlert } from "lucide-react";
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
import { Section } from "../../components/Section";
import { errorMessage } from "../../lib/errors";
import { RoleHeader } from "../roles/RoleHeader";
import { budgetQueryOptions } from "../cost/hooks";
import { roleQueryOptions } from "../roles/hooks";

import { CompareTray } from "./CompareTray";
import { type Entry } from "./RankedList";
import { RankingInfo } from "./RankingInfo";
import { ReviewWorkspace } from "./ReviewWorkspace";
import { UploadZone } from "./UploadZone";
import { STAGES, type RankedPage, type Stage } from "./api";
import { STAGE_LABEL } from "./labels";
import { rankedQueryOptions, useRescore, useRoleQueue } from "./hooks";

/** Candidates: upload and ranked list (Design.md 8.3, PRD steps 4 and 6). */
export function CandidatesPage() {
  const { roleId } = useParams({ strict: false });
  if (roleId === undefined) throw new Error("route has no roleId");
  // key: the stage filter and page belong to one role.
  return <Candidates key={roleId} roleId={roleId} />;
}

function Candidates({ roleId }: { roleId: string }) {
  const role = useQuery(roleQueryOptions(roleId));
  const [uploadOpen, setUploadOpen] = useState(false);
  const total = useQuery({
    ...rankedQueryOptions(roleId, null, 0, false),
    enabled: role.data?.status === "approved",
  }).data?.total;
  const hasCandidates = total !== undefined && total > 0;

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
    <div className="flex flex-col gap-4">
      <RoleHeader
        role={role.data}
        current="candidates"
        actions={
          hasCandidates && (
            <Button
              type="button"
              variant="outline"
              className="h-10 px-4"
              aria-expanded={uploadOpen}
              aria-controls="upload-zone"
              onClick={() => {
                setUploadOpen(!uploadOpen);
              }}
            >
              <FileUp aria-hidden="true" />
              Upload resumes
            </Button>
          )
        }
      />
      {role.data.status === "draft" ? (
        <Notice>Approve the criteria to start uploading and scoring resumes.</Notice>
      ) : (
        <>
          {/* Hidden, not unmounted, so the result of an upload stays when it is closed. */}
          <div id="upload-zone" className={hasCandidates && !uploadOpen ? "hidden" : undefined}>
            <UploadZone roleId={roleId} compact={hasCandidates} />
          </div>
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
  const { working, waiting, running } = useRoleQueue(roleId);
  const ranked = useQuery(rankedQueryOptions(roleId, stage, offset, working));

  return (
    <div className={selected.length > 0 ? "pb-20" : undefined}>
      <Section
        id="ranked-heading"
        title="Ranked candidates"
        hideTitle
        action={
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
            {ranked.data?.data.some((c) => c.stale) && <StaleBar roleId={roleId} />}
            <div className="flex items-center gap-2">
              <Label htmlFor="stage-filter">Filter by stage</Label>
              <Select
                value={stage ?? "all"}
                onValueChange={(value) => {
                  setStage(STAGES.find((s) => s === value) ?? null);
                  setOffset(0);
                }}
              >
                <SelectTrigger id="stage-filter" className="h-10 w-44">
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
        }
      >
        <RankingInfo />
        {(flaggedOnly || overridesOnly) && (
          <p className="-mt-1 text-xs text-muted-foreground">
            These checkboxes filter the loaded page only; the stage filter covers every candidate.
          </p>
        )}
        {working && (
          <Notice>
            Processing resumes: {waiting} waiting, {running} running. The list refreshes by itself.
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
      <p role="status" className="sr-only">
        {selected.length === 0 ? "" : `${selected.length} candidates selected for compare`}
      </p>
      <CompareTray
        ids={selected}
        onClear={() => {
          setSelected([]);
        }}
      />
    </div>
  );
}

/** Out-of-date scores as one slim inline bar with the re-score action (Design.md section 11). */
function StaleBar({ roleId }: { roleId: string }) {
  const rescore = useRescore(roleId);
  const budget = useQuery(budgetQueryOptions);
  const blocked = budget.data?.model_actions_allowed === false;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-warn bg-warn-soft py-0.5 pr-1 pl-3 text-sm">
      <TriangleAlert aria-hidden="true" className="size-4 text-warn" />
      <span>Scores are out of date because the criteria changed.</span>
      <Button
        type="button"
        variant="outline"
        className="h-10 px-3"
        disabled={rescore.isPending || blocked}
        onClick={() => {
          rescore.mutate();
        }}
      >
        Re-score
      </Button>
      {rescore.isSuccess && (
        <span role="status">
          Re-scoring {rescore.data.queued} candidates; {rescore.data.skipped} skipped
        </span>
      )}
      {rescore.isError && (
        <span role="alert" className="text-bad">
          {errorMessage(rescore.error)}
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
  // Client-side, on the loaded page only: the API has no such filters.
  const entries: Entry[] = page.data
    .map((candidate, index) => ({ candidate, rank: page.offset + index + 1 }))
    .filter(
      ({ candidate: c }) =>
        (!flaggedOnly || c.scores.some((s) => s.flag_reason !== null)) &&
        (!overridesOnly || c.scores.some((s) => s.override_score !== null)),
    );
  return (
    <>
      {page.data.length === 0 ? (
        <EmptyState message="This page is past the last candidate. Go back to the previous page." />
      ) : entries.length === 0 ? (
        <EmptyState message="No candidates on this page match the filters." />
      ) : (
        <ReviewWorkspace
          roleId={roleId}
          page={page}
          entries={entries}
          selected={selected}
          onToggle={onToggle}
          onOffset={onOffset}
        />
      )}
    </>
  );
}
