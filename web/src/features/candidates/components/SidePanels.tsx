import { useQuery } from "@tanstack/react-query";
import { Eye, UserMinus, UserPlus } from "lucide-react";
import { type SubmitEvent, useState } from "react";

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
import { Label } from "@/components/ui/label";

import { ErrorNotice } from "../../../components/ErrorNotice";
import { Loading } from "../../../components/Loading";
import { Section } from "../../../components/Section";
import { type AuditEvent, type Identity } from "../api";
import { STAGE_LABEL } from "../labels";
import { anonymizedTextQueryOptions, useAssign, useReveal, useUnassign } from "../hooks";

/** Split text around the quote, matching on whitespace-normalized words only (PRD: no fuzzy match). */
export function splitAtQuote(text: string, quote: string | null): [string, string, string] | null {
  const words = quote?.trim().split(/\s+/) ?? [];
  if (words.length === 0 || words[0] === "") return null;
  const pattern = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+");
  const hit = new RegExp(pattern).exec(text);
  if (!hit) return null;
  return [text.slice(0, hit.index), hit[0], text.slice(hit.index + hit[0].length)];
}

/** The anonymized resume text, with the selected criterion's quote highlighted (Design.md 8.4). */
export function ResumeText({ candidateId, quote }: { candidateId: string; quote: string | null }) {
  const text = useQuery(anonymizedTextQueryOptions(candidateId));
  if (text.isPending) return <Loading label="Loading the resume text" />;
  if (text.isError) return <ErrorNotice error={text.error} />;
  const parts = splitAtQuote(text.data, quote);
  return (
    <Section
      id="resume-heading"
      title="Anonymized resume text"
      description="Identity signals are removed by code. Some signals, such as schools or career gaps, can remain."
    >
      <div className="max-h-120 max-w-prose overflow-auto rounded-lg border bg-card p-4 whitespace-pre-wrap">
        {parts ? (
          <>
            {parts[0]}
            <mark className="rounded-sm bg-mark px-0.5 text-mark-foreground">{parts[1]}</mark>
            {parts[2]}
          </>
        ) : (
          text.data
        )}
      </div>
    </Section>
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
 * Assign interviewers. The contract has no call that lists users or a candidate's
 * assignments, so this takes an interviewer's user id and lists what was assigned
 * in this visit (see docs/progress/noticed.md).
 */
export function Assignments({ candidateId }: { candidateId: string }) {
  const assign = useAssign(candidateId);
  const unassign = useUnassign(candidateId);
  const [userId, setUserId] = useState("");
  const [assigned, setAssigned] = useState<string[]>([]);

  function onSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const id = userId.trim();
    assign.mutate(id, {
      onSuccess: () => {
        setAssigned((prev) => (prev.includes(id) ? prev : [...prev, id]));
        setUserId("");
      },
    });
  }

  return (
    <Section id="assign-heading" title="Interviewers">
      <form onSubmit={onSubmit} className="flex flex-col items-start gap-3">
        <div className="flex w-full flex-col gap-1.5">
          <Label htmlFor="assign-user">Interviewer user id</Label>
          <span className="text-sm text-muted-foreground">
            Paste the interviewer's account id. The app cannot list users yet.
          </span>
          <Input
            id="assign-user"
            className="h-10 font-mono"
            value={userId}
            required
            onChange={(e) => {
              setUserId(e.target.value);
            }}
          />
        </div>
        <Button type="submit" variant="outline" className="h-10 px-4" disabled={assign.isPending}>
          <UserPlus aria-hidden="true" />
          Assign interviewer
        </Button>
      </form>
      {assign.error && <ErrorNotice error={assign.error} />}
      {unassign.error && <ErrorNotice error={unassign.error} />}
      {assigned.length > 0 && (
        <ul className="flex flex-col divide-y rounded-lg border bg-card">
          {assigned.map((id) => (
            <li key={id} className="flex items-center justify-between gap-3 py-1 pr-1 pl-3">
              <span className="mono font-mono text-sm break-all">{id}</span>
              <Button
                type="button"
                variant="ghost"
                className="h-10 px-3"
                aria-label={`Remove interviewer ${id}`}
                disabled={unassign.isPending}
                onClick={() => {
                  unassign.mutate(id, {
                    onSuccess: () => {
                      setAssigned((prev) => prev.filter((p) => p !== id));
                    },
                  });
                }}
              >
                <UserMinus aria-hidden="true" />
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}
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
    default:
      return event.kind.replaceAll("_", " ");
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
