import { useQuery } from "@tanstack/react-query";
import { Eye, UserMinus, UserPlus } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import { ErrorNotice } from "../../../components/ErrorNotice";
import { Loading } from "../../../components/Loading";
import { Notice } from "../../../components/Notice";
import { Section } from "../../../components/Section";
import { revealIn, scrollBehavior } from "../../../lib/scrollSpy";
import { type AuditEvent, type Identity } from "../api";
import { STAGE_LABEL } from "../labels";
import {
  anonymizedTextQueryOptions,
  assignmentsQueryOptions,
  interviewersQueryOptions,
  useAssign,
  useReveal,
  useUnassign,
} from "../hooks";

/** Where the quote sits in the text, matching on whitespace-normalized words only (PRD: no fuzzy match). */
export function findQuote(text: string, quote: string | null): [number, number] | null {
  const words = quote?.trim().split(/\s+/) ?? [];
  if (words.length === 0 || words[0] === "") return null;
  const pattern = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+");
  const hit = new RegExp(pattern).exec(text);
  return hit ? [hit.index, hit.index + hit[0].length] : null;
}

/** Split text around the quote; see findQuote for the match. */
export function splitAtQuote(text: string, quote: string | null): [string, string, string] | null {
  const at = findQuote(text, quote);
  return at && [text.slice(0, at[0]), text.slice(...at), text.slice(at[1])];
}

export interface QuoteMark {
  id: string;
  quote: string;
}

interface Highlight {
  start: number;
  end: number;
  /** Criteria whose quote is this exact span. */
  ids: string[];
}

/** Every quote's span in the text. Equal spans share one highlight; a partial overlap is dropped. */
export function highlightsFor(text: string, marks: QuoteMark[]): Highlight[] {
  const found: Highlight[] = [];
  for (const m of marks) {
    const at = findQuote(text, m.quote);
    if (!at) continue;
    const same = found.find((h) => h.start === at[0] && h.end === at[1]);
    if (same) same.ids.push(m.id);
    else found.push({ start: at[0], end: at[1], ids: [m.id] });
  }
  found.sort((x, y) => x.start - y.start);
  return found.filter((h, i) => i === 0 || h.start >= (found[i - 1]?.end ?? 0));
}

const STICKY = {
  lg: "lg:sticky lg:top-20 lg:self-start",
  xl: "xl:sticky xl:top-20 xl:self-start",
} as const;
const RAIL = { lg: "lg:resume-rail", xl: "xl:resume-rail" } as const;

/**
 * The anonymized resume text with every verified quote softly highlighted (Design.md 8.4); the
 * active criterion's is stronger. Each highlight is a button that takes the reader to its scoring
 * card. It is a scroll region of its own (sticky where the scores sit beside it). `locate` is a
 * counter: each increase scrolls the region to the active highlight and pulses it once.
 */
export function ResumeText({
  candidateId,
  marks,
  activeId,
  locate = 0,
  onMarkClick,
  stickyFrom,
}: {
  candidateId: string;
  marks: QuoteMark[];
  activeId: string | null;
  locate?: number;
  onMarkClick: (id: string) => void;
  stickyFrom: "lg" | "xl";
}) {
  const text = useQuery(anonymizedTextQueryOptions(candidateId));
  const regionRef = useRef<HTMLDivElement>(null);
  const highlights = text.data === undefined ? [] : highlightsFor(text.data, marks);
  const found = highlights.some((h) => activeId !== null && h.ids.includes(activeId));
  useEffect(() => {
    const region = regionRef.current;
    const mark = region?.querySelector<HTMLElement>(`[data-ids~="${activeId ?? ""}"]`);
    if (locate === 0 || !region || !mark) return;
    revealIn(region, mark);
    region.scrollIntoView({ block: "nearest", behavior: scrollBehavior() });
    // Opacity only, and not at all when the reader asked for less motion.
    if ("animate" in mark && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      mark.animate([{ opacity: 0.3 }, { opacity: 1 }], { duration: 600 });
    }
  }, [locate, found, activeId]);

  if (text.isPending) return <Loading label="Loading the resume text" />;
  if (text.isError) return <ErrorNotice error={text.error} />;
  const missing = locate > 0 && !found;
  const body: ReactNode[] = [];
  let at = 0;
  for (const h of highlights) {
    const active = activeId !== null && h.ids.includes(activeId);
    body.push(text.data.slice(at, h.start));
    body.push(
      <mark key={h.start} className="bg-transparent">
        <span
          role="button"
          tabIndex={0}
          data-ids={h.ids.join(" ")}
          aria-label={`Show scoring card for this quote: ${text.data.slice(h.start, h.end)}`}
          onClick={() => {
            // A drag-select across the highlight is not a click on it.
            if (window.getSelection()?.isCollapsed === false) return;
            onMarkClick(h.ids[0] ?? "");
          }}
          onKeyDown={(event) => {
            if (event.key !== "Enter" && event.key !== " ") return;
            event.preventDefault();
            onMarkClick(h.ids[0] ?? "");
          }}
          className={cn(
            "cursor-pointer rounded-sm px-0.5 text-mark-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
            active ? "bg-mark outline-2 outline-primary" : "bg-mark/40",
          )}
        >
          {text.data.slice(h.start, h.end)}
        </span>
      </mark>,
    );
    at = h.end;
  }
  body.push(text.data.slice(at));
  return (
    <div className={STICKY[stickyFrom]}>
      <Section
        id="resume-heading"
        title="Anonymized resume text"
        description="Identity signals are removed by code. Some signals, such as schools or career gaps, can remain."
      >
        <p role="status" className="sr-only">
          {locate > 0 && found ? "Quote located in the resume" : ""}
        </p>
        {missing && (
          <Notice tone="warning">
            {marks.some((m) => m.id === activeId)
              ? "This quote was not found in the resume text, so it cannot be shown here."
              : "This criterion has no quote to show."}
          </Notice>
        )}
        <div
          ref={regionRef}
          role="region"
          aria-label="Anonymized resume"
          tabIndex={0}
          className={`max-h-120 max-w-prose overflow-auto rounded-lg border bg-card p-4 whitespace-pre-wrap ${RAIL[stickyFrom]}`}
        >
          {body}
        </div>
      </Section>
    </div>
  );
}

/** Show candidate name (Design.md section 9): an explicit, logged action behind a confirmation. */
export function RevealIdentity({ candidateId }: { candidateId: string }) {
  const reveal = useReveal(candidateId);
  const [asking, setAsking] = useState(false);
  const identity: Identity | undefined = reveal.data;

  if (identity) {
    return (
      <p>
        <span className="text-muted-foreground">Candidate name (shown, logged): </span>
        <strong>{identity.identity_name ?? "No name found"}</strong>
        <span className="text-muted-foreground"> from {identity.file_name}</span>
      </p>
    );
  }
  return (
    <>
      <Button
        type="button"
        variant="outline"
        className="h-10 px-4"
        onClick={() => {
          setAsking(true);
        }}
      >
        <Eye aria-hidden="true" />
        Show candidate name
      </Button>
      <Dialog open={asking} onOpenChange={setAsking}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-2xl font-medium">Show candidate name?</DialogTitle>
            <DialogDescription>
              Showing the name is recorded in the history under your name.
            </DialogDescription>
          </DialogHeader>
          {reveal.error && <ErrorNotice error={reveal.error} />}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              className="h-10 px-4"
              onClick={() => {
                setAsking(false);
              }}
            >
              Cancel
            </Button>
            <Button
              type="button"
              className="h-10 px-4"
              disabled={reveal.isPending}
              onClick={() => {
                reveal.mutate(undefined, {
                  onSuccess: () => {
                    setAsking(false);
                  },
                });
              }}
            >
              Show candidate name
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/**
 * Assign interviewers: search the interviewer accounts not yet assigned and assign with one
 * click; assigned people are rows with a Remove. The server owns the assigned list, so it is
 * read from the cache and never copied into state.
 */
export function Assignments({ candidateId }: { candidateId: string }) {
  const interviewers = useQuery(interviewersQueryOptions());
  const assigned = useQuery(assignmentsQueryOptions(candidateId));
  const assign = useAssign(candidateId);
  const unassign = useUnassign(candidateId);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [done, setDone] = useState("");

  let body;
  if (interviewers.isPending || assigned.isPending) {
    body = <Loading label="Loading interviewers" />;
  } else if (interviewers.isError || assigned.isError) {
    body = <ErrorNotice error={interviewers.error ?? assigned.error} />;
  } else {
    const taken = new Set(assigned.data.map((p) => p.id));
    const needle = search.trim().toLowerCase();
    const available = interviewers.data.filter(
      (p) => !taken.has(p.id) && p.name.toLowerCase().includes(needle),
    );
    const allTaken = interviewers.data.every((p) => taken.has(p.id));
    body = (
      <>
        {interviewers.data.length === 0 ? (
          <Notice tone="info">No interviewer accounts exist yet.</Notice>
        ) : (
          <Popover
            open={open}
            onOpenChange={(next) => {
              setOpen(next);
              if (!next) setSearch("");
            }}
          >
            <PopoverTrigger asChild>
              <Button
                type="button"
                variant="outline"
                className="h-10 w-fit px-4"
                disabled={allTaken}
              >
                <UserPlus aria-hidden="true" />
                Add interviewer
              </Button>
            </PopoverTrigger>
            <PopoverContent align="start" className="flex w-72 flex-col gap-2 p-2">
              <Input
                aria-label="Search interviewers"
                placeholder="Search by name"
                autoComplete="off"
                className="h-10"
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                }}
              />
              {available.length === 0 ? (
                <p className="px-2 py-3 text-sm text-muted-foreground">
                  No interviewer matches that name.
                </p>
              ) : (
                <ul className="flex max-h-60 flex-col overflow-y-auto">
                  {available.map((p) => (
                    <li key={p.id} className="flex items-center justify-between gap-2 pl-2">
                      <span className="truncate text-sm">{p.name}</span>
                      <Button
                        type="button"
                        variant="ghost"
                        className="h-10 px-3"
                        aria-label={`Assign ${p.name}`}
                        disabled={assign.isPending}
                        onClick={() => {
                          setDone("");
                          assign.mutate(p.id, {
                            onSuccess: () => {
                              setDone(`${p.name} assigned.`);
                            },
                          });
                        }}
                      >
                        {assign.isPending && assign.variables === p.id ? "Assigning" : "Assign"}
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </PopoverContent>
          </Popover>
        )}
        <p role="status" className="text-sm text-muted-foreground empty:hidden">
          {done}
        </p>
        {assigned.data.length === 0 ? (
          <Notice tone="info">No interviewers assigned. Pick someone to ask for feedback.</Notice>
        ) : (
          <ul className="flex flex-col divide-y rounded-lg border bg-card">
            {assigned.data.map((p) => (
              <li key={p.id} className="flex items-center justify-between gap-3 py-1 pr-1 pl-3">
                <span className="text-sm">{p.name}</span>
                <Button
                  type="button"
                  variant="ghost"
                  className="h-10 px-3"
                  aria-label={`Remove ${p.name}`}
                  disabled={unassign.isPending}
                  onClick={() => {
                    setDone("");
                    unassign.mutate(p.id, {
                      onSuccess: () => {
                        setDone(`${p.name} removed.`);
                      },
                    });
                  }}
                >
                  <UserMinus aria-hidden="true" />
                  {unassign.isPending && unassign.variables === p.id ? "Removing" : "Remove"}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </>
    );
  }

  return (
    <Section id="assign-heading" title="Interviewers">
      {body}
      {assign.error && <ErrorNotice error={assign.error} />}
      {unassign.error && <ErrorNotice error={unassign.error} />}
    </Section>
  );
}

function describe(event: AuditEvent): string {
  switch (event.kind) {
    case "score_override":
      return `Score changed on ${event.criterion_name ?? "a criterion"}: ${event.old_score ?? "none"} to ${event.new_score ?? "none"}`;
    case "stage_change":
      return `Hiring stage ${event.from_stage ? STAGE_LABEL[event.from_stage] : "none"} to ${event.to_stage ? STAGE_LABEL[event.to_stage] : "none"}`;
    case "identity_reveal":
      return "Candidate name shown";
    case "feedback_edit_approved":
      return "Edit of interviewer feedback approved";
    case "feedback_edited":
      return "Interviewer feedback edited";
    case "scored":
      return "Scored by the AI";
    case "override":
      return "Score changed";
    case "stage":
      return "Hiring stage changed";
    default: {
      const words = event.kind.replaceAll("_", " ");
      return words.charAt(0).toUpperCase() + words.slice(1);
    }
  }
}

/** Hiring stage and score change history (Design.md 8.4), newest first, as the API sends it. */
export function AuditHistory({ events }: { events: AuditEvent[] }) {
  return (
    <Section id="history-heading" title="History">
      {events.length === 0 ? (
        <p className="text-muted-foreground">No hiring stage moves or score changes yet.</p>
      ) : (
        <ul className="flex flex-col divide-y">
          {events.map((e) => (
            <li key={e.id} className="flex flex-col gap-0.5 py-2">
              <span>
                {describe(e)}
                {e.note && <span className="text-muted-foreground"> ({e.note})</span>}
              </span>
              <span className="mono font-mono text-xs text-muted-foreground">{e.created_at}</span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
