import { Link } from "@tanstack/react-router";
import { Clock, Pencil, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";

import { type RankedCandidate, candidateLabel } from "./api";
import { PROCESSING_LABEL, STAGE_LABEL } from "./labels";

export interface Entry {
  candidate: RankedCandidate;
  /** Position in the whole ranking, not in the filtered view. */
  rank: number;
}

function Marker({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 text-foreground">
      {icon}
      {children}
    </span>
  );
}

/** One row's text: rank, anonymous id and total, then coverage, markers and stage. Never colored by score. */
function RowBody({ entry }: { entry: Entry }) {
  const { candidate, rank } = entry;
  const ready = candidate.processing_status === "done";
  const flagged = candidate.scores.some((s) => s.flag_reason !== null);
  const changed = candidate.scores.some((s) => s.override_score !== null);
  return (
    <>
      <span className="flex items-baseline gap-2">
        <span className="w-7 shrink-0 text-right font-mono text-xs text-muted-foreground tabular-nums">
          {rank}
        </span>
        <span className="font-mono text-sm font-semibold">
          {candidateLabel(candidate.candidate_no)}
        </span>
        <span className="ml-auto font-mono text-sm tabular-nums">
          {ready ? (
            candidate.total.toFixed(1)
          ) : (
            <span className="font-sans text-xs text-muted-foreground">
              {PROCESSING_LABEL[candidate.processing_status]}
            </span>
          )}
        </span>
      </span>
      <span className="flex flex-wrap gap-x-3 gap-y-0.5 pl-9 text-xs text-muted-foreground">
        <span>
          {ready
            ? `${candidate.must_have_covered} of ${candidate.must_have_total} must-haves`
            : "Not scored yet"}
        </span>
        <span>{STAGE_LABEL[candidate.stage]}</span>
        {flagged && (
          <Marker icon={<TriangleAlert aria-hidden="true" className="size-3.5 text-warn" />}>
            Needs a look
          </Marker>
        )}
        {changed && (
          <Marker icon={<Pencil aria-hidden="true" className="size-3.5" />}>
            Changed by recruiter
          </Marker>
        )}
        {candidate.stale && (
          <Marker icon={<Clock aria-hidden="true" className="size-3.5" />}>Out of date</Marker>
        )}
        {candidate.duplicate_of_candidate_no !== null && (
          <span>Possible duplicate of {candidateLabel(candidate.duplicate_of_candidate_no)}</span>
        )}
      </span>
    </>
  );
}

const ROW =
  "flex min-h-14 flex-1 flex-col justify-center gap-0.5 py-2 pr-3 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:ring-inset";

/**
 * The compact ranked list (Design.md 8.3). Every candidate stays listed. With `onOpen` the row
 * selects the candidate in review mode; without it the row is a link to the candidate page.
 */
export function RankedList({
  entries,
  activeId,
  selected,
  onToggle,
  onOpen,
  onArrow,
}: {
  entries: Entry[];
  activeId: string | null;
  selected: string[];
  onToggle: (id: string) => void;
  onOpen: ((id: string) => void) | null;
  onArrow: (delta: 1 | -1, from: HTMLElement) => void;
}) {
  return (
    <ol
      aria-label="Candidates ranked by weighted total, highest first"
      className="flex min-h-0 flex-1 flex-col overflow-y-auto"
    >
      {entries.map((entry) => {
        const { candidate } = entry;
        const active = candidate.id === activeId;
        const label = candidateLabel(candidate.candidate_no);
        return (
          <li
            key={candidate.id}
            id={`row-${candidate.id}`}
            className={cn(
              "flex items-stretch border-b border-l-2 last:border-b-0",
              active ? "border-l-primary bg-muted" : "border-l-transparent",
            )}
          >
            <div className="flex w-10 shrink-0 items-center justify-center">
              <Checkbox
                aria-label={`Select ${label} to compare`}
                checked={selected.includes(candidate.id)}
                onCheckedChange={() => {
                  onToggle(candidate.id);
                }}
              />
            </div>
            {onOpen ? (
              <button
                type="button"
                data-row=""
                aria-current={active ? "true" : undefined}
                className={ROW}
                onClick={() => {
                  onOpen(candidate.id);
                }}
                onKeyDown={(event) => {
                  if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
                  event.preventDefault();
                  onArrow(event.key === "ArrowDown" ? 1 : -1, event.currentTarget);
                }}
              >
                <RowBody entry={entry} />
              </button>
            ) : (
              <Link
                to="/candidates/$candidateId"
                params={{ candidateId: candidate.id }}
                className={ROW}
              >
                <RowBody entry={entry} />
              </Link>
            )}
          </li>
        );
      })}
    </ol>
  );
}
