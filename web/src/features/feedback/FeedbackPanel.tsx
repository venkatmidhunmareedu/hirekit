import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { Check, Lock } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { Notice } from "../../components/Notice";
import { ProgressBar } from "../../components/ProgressBar";
import { Section } from "../../components/Section";
import { StatusTag } from "../../components/StatusTag";
import { type Question, type RoleCriterion } from "../kit/api";
import { kitQueryOptions, roleCriteriaQueryOptions } from "../kit/hooks";

import { type FeedbackRow } from "./api";
import { feedbackQueryOptions, useApproveEdit, useSubmitFeedback } from "./hooks";

const LEVELS = [0, 1, 2, 3, 4];

/** The segmented 0 to 4 score for one criterion: native radios, so arrow keys and labels just work. */
function ScoreSelector({
  criterion,
  value,
  onChange,
}: {
  criterion: RoleCriterion;
  value: number | undefined;
  onChange: (score: number) => void;
}) {
  const levels = [...criterion.rubric].sort((a, b) => a.level - b.level);
  return (
    <div className="flex flex-col gap-3">
      <div
        role="radiogroup"
        aria-label={`Score for ${criterion.name}`}
        className="grid max-w-md grid-cols-5 gap-1.5"
      >
        {LEVELS.map((n) => (
          <div key={n} className="relative">
            <input
              type="radio"
              id={`score-${criterion.id}-${n}`}
              name={`score-${criterion.id}`}
              className="peer sr-only"
              checked={value === n}
              onChange={() => {
                onChange(n);
              }}
            />
            <label
              htmlFor={`score-${criterion.id}-${n}`}
              className="flex h-10 cursor-pointer items-center justify-center rounded-md border bg-background font-mono text-base font-medium peer-checked:border-primary peer-checked:bg-primary peer-checked:text-primary-foreground peer-focus-visible:ring-3 peer-focus-visible:ring-ring/50 peer-disabled:cursor-default hover:bg-muted peer-checked:hover:bg-primary"
            >
              {n}
            </label>
          </div>
        ))}
      </div>
      {levels.length > 0 && (
        <ul className="flex flex-col gap-1 text-sm">
          {levels.map((l) => (
            <li
              key={l.level}
              className={cn(
                "flex items-start gap-2",
                value === l.level ? "font-medium text-foreground" : "text-muted-foreground",
              )}
            >
              <span className="mono w-4 shrink-0 font-mono">{l.level}</span>
              <span className="flex-1">{l.descriptor}</span>
              {value === l.level && (
                <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-primary" />
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Interviewer feedback form (Design.md 8.6): one block per criterion, a segmented score and a comment. */
function FeedbackForm({
  candidateId,
  criteria,
  rows,
  questions,
  onSubmitted,
}: {
  candidateId: string;
  criteria: RoleCriterion[];
  rows: FeedbackRow[];
  questions: Question[];
  onSubmitted: () => void;
}) {
  const submit = useSubmitFeedback(candidateId, onSubmitted);
  const [scores, setScores] = useState<Record<string, number>>(() =>
    Object.fromEntries(rows.map((r) => [r.criterion_id, r.score])),
  );
  const [comments, setComments] = useState<Record<string, string>>(() =>
    Object.fromEntries(rows.map((r) => [r.criterion_id, r.comment])),
  );
  const readOnly = rows.length > 0 && rows.every((r) => r.locked);
  const isDone = (c: RoleCriterion) =>
    scores[c.id] !== undefined && (comments[c.id] ?? "").trim() !== "";
  const done = criteria.filter(isDone).length;
  const missing = criteria.length - done;
  // Unsaved input: anything that differs from what the server holds. Leaving asks first.
  const dirty =
    !readOnly &&
    !submit.isSuccess &&
    criteria.some((c) => {
      const saved = rows.find((r) => r.criterion_id === c.id);
      return scores[c.id] !== saved?.score || (comments[c.id] ?? "") !== (saved?.comment ?? "");
    });
  const blocker = useBlocker({
    shouldBlockFn: () => dirty,
    enableBeforeUnload: () => dirty,
    disabled: !dirty,
    withResolver: true,
  });

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        const items = criteria.map((c) => ({
          criterion_id: c.id,
          score: scores[c.id] ?? 0,
          comment: (comments[c.id] ?? "").trim(),
        }));
        submit.mutate({ items, isEdit: rows.length > 0 });
      }}
    >
      <div className="sticky top-0 z-10 -mx-1 flex flex-col gap-2 border-b bg-background px-1 pt-2 pb-3 sm:top-14">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p role="status" className="text-sm font-medium">
            {done} of {criteria.length} criteria scored
          </p>
          {readOnly && <StatusTag tone="success">Submitted</StatusTag>}
        </div>
        <ProgressBar value={done} max={criteria.length} label="Criteria scored" />
      </div>
      {readOnly && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Lock aria-hidden="true" className="size-4" /> Submitted and locked. A recruiter can
          approve an edit.
        </p>
      )}
      {criteria.map((c) => {
        const asked = questions
          .filter((q) => q.criterion_id === c.id)
          .sort((a, b) => a.position - b.position);
        return (
          <Card key={c.id} className="px-5">
            <fieldset disabled={readOnly} className="flex min-w-0 flex-col gap-4">
              <legend className="mb-3 text-lg font-medium">{c.name}</legend>
              {asked.length > 0 && (
                <div className="flex flex-col gap-1">
                  <p className="text-sm font-medium">Questions to ask</p>
                  <ul className="list-disc pl-5 text-sm text-muted-foreground">
                    {asked.map((q) => (
                      <li key={q.id}>{q.question_text}</li>
                    ))}
                  </ul>
                </div>
              )}
              <ScoreSelector
                criterion={c}
                value={scores[c.id]}
                onChange={(score) => {
                  setScores({ ...scores, [c.id]: score });
                }}
              />
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`comment-${c.id}`}>Comment on {c.name}</Label>
                <Textarea
                  id={`comment-${c.id}`}
                  rows={2}
                  value={comments[c.id] ?? ""}
                  onChange={(e) => {
                    setComments({ ...comments, [c.id]: e.target.value });
                  }}
                />
              </div>
            </fieldset>
          </Card>
        );
      })}
      {submit.error && <ErrorNotice error={submit.error} />}
      {!readOnly && (
        <div className="flex flex-col items-start gap-3">
          <Notice id="submit-hint">
            {missing > 0
              ? `${missing} ${missing === 1 ? "criterion still needs" : "criteria still need"} a score and a comment. `
              : ""}
            Locked after submit; a recruiter can approve an edit.
          </Notice>
          <Button
            type="submit"
            className="h-10 px-4"
            aria-describedby="submit-hint"
            disabled={missing > 0 || submit.isPending}
          >
            Submit feedback
          </Button>
        </div>
      )}
      <Dialog
        open={blocker.status === "blocked"}
        onOpenChange={(open) => {
          if (!open) blocker.reset?.();
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-2xl font-medium">Leave this page?</DialogTitle>
            <DialogDescription>Your feedback is not submitted.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              className="h-10 px-4"
              onClick={() => blocker.reset?.()}
            >
              Stay on this page
            </Button>
            <Button type="button" className="h-10 px-4" onClick={() => blocker.proceed?.()}>
              Leave page
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </form>
  );
}

/** A recruiter sees every interviewer's feedback and can unlock one for an edit. */
function RecruiterFeedback({
  candidateId,
  criteria,
  rows,
}: {
  candidateId: string;
  criteria: RoleCriterion[];
  rows: FeedbackRow[];
}) {
  const approve = useApproveEdit(candidateId);
  const interviewers = [...new Set(rows.map((r) => r.interviewer_id))];
  if (interviewers.length === 0) return <EmptyState message="No feedback submitted yet." />;
  return (
    <div className="flex flex-col gap-4">
      {approve.error && <ErrorNotice error={approve.error} />}
      {interviewers.map((id, index) => {
        const mine = rows.filter((r) => r.interviewer_id === id);
        const locked = mine.every((r) => r.locked);
        return (
          <Card
            key={id}
            role="region"
            aria-label={`Feedback from interviewer ${index + 1}`}
            className="gap-3 px-5"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-lg font-medium">Interviewer {index + 1}</h3>
              {locked ? (
                <Button
                  type="button"
                  variant="outline"
                  className="h-10 px-4"
                  disabled={approve.isPending}
                  onClick={() => {
                    approve.mutate(id);
                  }}
                >
                  Approve edit for interviewer {index + 1}
                </Button>
              ) : (
                <StatusTag tone="info">Unlocked for an edit</StatusTag>
              )}
            </div>
            <ul className="flex flex-col gap-2">
              {mine.map((r) => (
                <li key={r.criterion_id}>
                  <strong className="font-medium">
                    {criteria.find((c) => c.id === r.criterion_id)?.name ?? "Criterion"}
                  </strong>
                  : <span className="mono font-mono">{r.score} / 4</span> {r.comment}
                </li>
              ))}
            </ul>
          </Card>
        );
      })}
    </div>
  );
}

export function FeedbackPanel({
  candidateId,
  roleId,
  viewer,
  onSubmitted = () => undefined,
}: {
  candidateId: string;
  roleId: string;
  viewer: "recruiter" | "interviewer";
  /** Called once, right after this visit's submit succeeds (not on a revisit). */
  onSubmitted?: () => void;
}) {
  const role = useQuery(roleCriteriaQueryOptions(roleId));
  const kit = useQuery({ ...kitQueryOptions(roleId), enabled: viewer === "interviewer" });
  const feedback = useQuery(feedbackQueryOptions(candidateId));
  if (role.isPending || feedback.isPending) return <Loading label="Loading feedback" />;
  if (role.isError) return <ErrorNotice error={role.error} />;
  if (feedback.isError) return <ErrorNotice error={feedback.error} />;
  const criteria = [...role.data.criteria].sort((a, b) => a.position - b.position);

  return (
    <Section id="feedback-heading" title="Interviewer feedback">
      {viewer === "recruiter" ? (
        <RecruiterFeedback candidateId={candidateId} criteria={criteria} rows={feedback.data} />
      ) : (
        <FeedbackForm
          key={feedback.data.map((r) => (r.locked ? "1" : "0")).join("")}
          candidateId={candidateId}
          criteria={criteria}
          rows={feedback.data}
          questions={kit.data?.questions ?? []}
          onSubmitted={onSubmitted}
        />
      )}
    </Section>
  );
}
