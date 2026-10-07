import { useBlocker } from "@tanstack/react-router";
import {
  Check,
  ChevronDown,
  Circle,
  CircleDashed,
  CircleCheck,
  CircleDot,
  ListChecks,
  Lock,
  Minus,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";

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

import { ErrorNotice } from "../../components/ErrorNotice";
import { Notice } from "../../components/Notice";
import { StatusTag } from "../../components/StatusTag";
import { type Question, type RoleCriterion } from "../kit/api";

import { type FeedbackRow } from "./api";
import { useSubmitFeedback } from "./hooks";
import {
  type Draft,
  announce,
  isComplete,
  missingCount,
  nextStep,
  prevStep,
  startStep,
  summary,
} from "./steps";

const LEVELS = [0, 1, 2, 3, 4];

/** The segmented progress: one button per criterion plus the review step, icon and text, no scrolling. */
function Stepper({
  criteria,
  draft,
  step,
  onGo,
}: {
  criteria: RoleCriterion[];
  draft: Draft;
  step: number;
  onGo: (step: number) => void;
}) {
  const items = [...criteria.map((c) => c.name), "Review and submit"];
  return (
    <nav aria-label="Criteria">
      <ol className="flex gap-1">
        {items.map((name, i) => {
          const review = i === criteria.length;
          const current = i === step;
          const done = !review && isComplete(draft, criteria[i]?.id ?? "");
          const started =
            !review &&
            !done &&
            (draft.scores[criteria[i]?.id ?? ""] !== undefined ||
              (draft.comments[criteria[i]?.id ?? ""] ?? "").trim() !== "");
          const Icon = review ? ListChecks : current ? CircleDot : started ? CircleDashed : Circle;
          const state = current
            ? "current"
            : done
              ? "done"
              : started
                ? "needs score and comment"
                : review
                  ? ""
                  : "not done";
          return (
            <li key={name} className="min-w-0 flex-1">
              <button
                type="button"
                aria-current={current ? "step" : undefined}
                aria-label={review ? "Review step" : `Criterion ${i + 1}, ${name}, ${state}`}
                onClick={() => {
                  onGo(i);
                }}
                className="flex h-10 w-full cursor-pointer flex-col justify-between rounded-sm py-1 outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <span
                  className={cn(
                    "h-1.5 w-full rounded-full",
                    current ? "bg-primary" : done ? "bg-primary/50" : "bg-input/60",
                  )}
                />
                {done ? (
                  <span
                    aria-hidden="true"
                    className={cn(
                      "mx-auto flex size-4 items-center justify-center rounded-full bg-primary text-primary-foreground",
                      current && "ring-2 ring-primary/30 ring-offset-1",
                    )}
                  >
                    <Check className="size-3" strokeWidth={3} />
                  </span>
                ) : (
                  <Icon
                    aria-hidden="true"
                    className={cn(
                      "mx-auto size-4",
                      current || started ? "text-primary" : "text-muted-foreground",
                    )}
                  />
                )}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/** The kit questions for one criterion, once, each opening to its Strong and Weak answers. */
function AskList({ questions }: { questions: Question[] }) {
  return (
    <section aria-labelledby="ask-heading" className="flex flex-col gap-2">
      <h3 id="ask-heading" className="text-base font-medium">
        Ask
      </h3>
      <ul className="flex flex-col divide-y rounded-lg border">
        {questions.map((q) => (
          <li key={q.id}>
            <details className="group">
              <summary className="flex min-h-10 cursor-pointer list-none items-center gap-3 rounded-lg px-3 py-2 outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
                <span className="flex-1 text-sm">{q.question_text}</span>
                <span className="sr-only">Show strong and weak answers</span>
                <ChevronDown
                  aria-hidden="true"
                  className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
                />
              </summary>
              <div className="grid gap-3 px-3 pt-1 pb-3 sm:grid-cols-2">
                <div className="flex flex-col gap-1 rounded-md border bg-muted/50 p-3">
                  <p className="flex items-center gap-1.5 text-sm font-medium">
                    <Check aria-hidden="true" className="size-4" /> Strong answer
                  </p>
                  <p className="text-sm">{q.strong_answer}</p>
                </div>
                <div className="flex flex-col gap-1 rounded-md border border-dashed p-3">
                  <p className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                    <Minus aria-hidden="true" className="size-4" /> Weak answer
                  </p>
                  <p className="text-sm text-muted-foreground">{q.weak_answer}</p>
                </div>
              </div>
            </details>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Five radio cards, each with its number and rubric descriptor together. Keys 0 to 4 pick a level. */
function ScoreCards({
  criterion,
  value,
  onChange,
}: {
  criterion: RoleCriterion;
  value: number | undefined;
  onChange: (score: number) => void;
}) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-base font-medium">Your score</h3>
      <div
        role="radiogroup"
        aria-label={`Score for ${criterion.name}`}
        className="flex flex-col gap-2"
      >
        {LEVELS.map((n) => {
          const descriptor = criterion.rubric.find((l) => l.level === n)?.descriptor;
          const checked = value === n;
          return (
            <div key={n} className="relative">
              <input
                type="radio"
                id={`score-${criterion.id}-${n}`}
                name={`score-${criterion.id}`}
                className="peer sr-only"
                checked={checked}
                onChange={() => {
                  onChange(n);
                }}
                onKeyDown={(e) => {
                  if (e.altKey || e.ctrlKey || e.metaKey || !/^[0-4]$/.test(e.key)) return;
                  e.preventDefault();
                  onChange(Number(e.key));
                }}
              />
              <label
                htmlFor={`score-${criterion.id}-${n}`}
                className={cn(
                  "flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border bg-background px-3 py-2 text-sm peer-focus-visible:ring-3 peer-focus-visible:ring-ring/50 hover:bg-muted",
                  checked && "border-primary bg-accent hover:bg-accent",
                )}
              >
                <span
                  className={cn(
                    "flex size-8 shrink-0 items-center justify-center rounded-md border font-mono text-base font-medium",
                    checked && "border-primary bg-primary text-primary-foreground",
                  )}
                >
                  {n}
                </span>{" "}
                <span className="flex-1">{descriptor}</span>
                {checked && <Check aria-hidden="true" className="size-4 shrink-0 text-primary" />}
              </label>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function KindTag({ kind }: { kind: RoleCriterion["kind"] }) {
  const Icon = kind === "must_have" ? CircleCheck : Sparkles;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
      <Icon aria-hidden="true" className="size-3.5" />
      {kind === "must_have" ? "Must-have" : "Nice-to-have"}
    </span>
  );
}

/** The final step, and the read-only view after submit: each criterion with its score and comment. */
function ReviewTable({
  criteria,
  draft,
  onEdit,
}: {
  criteria: RoleCriterion[];
  draft: Draft;
  onEdit?: (index: number) => void;
}) {
  const rows = summary(criteria, draft);
  return (
    <table className="w-full text-sm">
      <caption className="sr-only">Your feedback by criterion</caption>
      <thead className="sr-only">
        <tr>
          <th scope="col">Criterion</th>
          <th scope="col">Score</th>
          {onEdit && <th scope="col">Action</th>}
        </tr>
      </thead>
      <tbody className="divide-y">
        {rows.map((r, i) => (
          <tr key={r.id}>
            <th scope="row" className="py-3 pr-3 text-left align-top font-normal">
              <span className="block font-medium">{r.name}</span>
              {r.missing ? (
                <span className="mt-0.5 flex items-center gap-1 text-warn">
                  <TriangleAlert aria-hidden="true" className="size-4 shrink-0" />
                  Needs a {r.missing}
                </span>
              ) : (
                <span className="mt-0.5 block text-muted-foreground">{r.preview}</span>
              )}
            </th>
            <td className="py-3 pr-3 align-top font-mono whitespace-nowrap">
              {r.score === undefined ? "Not scored" : `${r.score} / 4`}
            </td>
            {onEdit && (
              <td className="py-1.5 text-right align-top">
                <Button
                  type="button"
                  variant="ghost"
                  className="h-10 px-3"
                  aria-label={`Edit ${r.name}`}
                  onClick={() => {
                    onEdit(i);
                  }}
                >
                  Edit
                </Button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * Interviewer feedback (Design.md 8.6): one criterion at a time, then a review step with the
 * one submit. The draft lives in this component, so moving between steps keeps it; there is no
 * draft endpoint, so a reload starts again from what the server holds.
 */
export function FeedbackFlow({
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
  const [draft, setDraft] = useState<Draft>(() => ({
    scores: Object.fromEntries(rows.map((r) => [r.criterion_id, r.score])),
    comments: Object.fromEntries(rows.map((r) => [r.criterion_id, r.comment])),
  }));
  const [step, setStep] = useState(() => startStep(criteria, draft));
  const [direction, setDirection] = useState(1);
  const [message, setMessage] = useState("");
  const headingRef = useRef<HTMLHeadingElement>(null);
  const moved = useRef(false);

  const n = criteria.length;
  const readOnly = rows.length > 0 && rows.every((r) => r.locked);
  const missing = missingCount(criteria, draft);
  const dirty =
    !readOnly &&
    !submit.isSuccess &&
    criteria.some((c) => {
      const saved = rows.find((r) => r.criterion_id === c.id);
      return (
        draft.scores[c.id] !== saved?.score ||
        (draft.comments[c.id] ?? "") !== (saved?.comment ?? "")
      );
    });
  const blocker = useBlocker({
    shouldBlockFn: () => dirty,
    enableBeforeUnload: () => dirty,
    disabled: !dirty,
    withResolver: true,
  });

  // Focus moves to the new step's heading after a step change, never on first render.
  useEffect(() => {
    if (moved.current) headingRef.current?.focus();
  }, [step]);

  const go = (to: number) => {
    if (to === step) return;
    moved.current = true;
    setDirection(to > step ? 1 : -1);
    setStep(to);
    setMessage(announce(criteria, to));
  };

  if (readOnly) {
    return (
      <Card className="gap-4 px-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-medium">Your feedback</h2>
          <StatusTag tone="success">Submitted</StatusTag>
        </div>
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Lock aria-hidden="true" className="size-4" /> Submitted and locked. A recruiter can
          approve an edit.
        </p>
        <ReviewTable criteria={criteria} draft={draft} />
      </Card>
    );
  }

  const criterion = criteria[step];
  const done = n - missing;
  const asked = criterion
    ? questions
        .filter((q) => q.criterion_id === criterion.id)
        .sort((a, b) => a.position - b.position)
    : [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <div className="flex items-baseline justify-between gap-3 text-sm">
          <p className="font-medium">
            {criterion ? `Criterion ${step + 1} of ${n}` : "Review and submit"}
          </p>
          <p className="text-muted-foreground">
            {done} of {n} complete
          </p>
        </div>
        <Stepper criteria={criteria} draft={draft} step={step} onGo={go} />
        <p role="status" className="sr-only">
          {message}
        </p>
      </div>
      <div className="overflow-x-clip">
        <motion.div
          key={step}
          initial={{ opacity: 0, x: direction * 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
        >
          <Card className="gap-6 px-5 py-6 sm:px-7">
            {criterion ? (
              <>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <h2
                    ref={headingRef}
                    tabIndex={-1}
                    className="scroll-mt-20 text-xl font-medium outline-none"
                  >
                    {criterion.name}
                  </h2>
                  <KindTag kind={criterion.kind} />
                </div>
                {asked.length > 0 && <AskList questions={asked} />}
                <ScoreCards
                  criterion={criterion}
                  value={draft.scores[criterion.id]}
                  onChange={(score) => {
                    setDraft({ ...draft, scores: { ...draft.scores, [criterion.id]: score } });
                  }}
                />
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor={`comment-${criterion.id}`} className="text-base font-medium">
                    Comment on {criterion.name}
                  </Label>
                  {draft.scores[criterion.id] !== undefined &&
                    (draft.comments[criterion.id] ?? "").trim() === "" && (
                      <p className="text-sm text-muted-foreground">
                        Add a comment to mark this criterion complete.
                      </p>
                    )}
                  <Textarea
                    id={`comment-${criterion.id}`}
                    className="min-h-24"
                    value={draft.comments[criterion.id] ?? ""}
                    onChange={(e) => {
                      setDraft({
                        ...draft,
                        comments: { ...draft.comments, [criterion.id]: e.target.value },
                      });
                    }}
                  />
                </div>
              </>
            ) : (
              <>
                <h2
                  ref={headingRef}
                  tabIndex={-1}
                  className="scroll-mt-20 text-xl font-medium outline-none"
                >
                  Review and submit
                </h2>
                <ReviewTable criteria={criteria} draft={draft} onEdit={go} />
                {submit.error && <ErrorNotice error={submit.error} />}
                <Notice id="submit-hint">
                  {missing > 0
                    ? `${missing} ${missing === 1 ? "criterion still needs" : "criteria still need"} a score and a comment. `
                    : ""}
                  Locked after submit; a recruiter can approve an edit.
                </Notice>
              </>
            )}
            <div className="flex items-center justify-between gap-3 border-t pt-5">
              <Button
                type="button"
                variant="outline"
                className="h-10 px-4"
                disabled={step === 0}
                onClick={() => {
                  go(prevStep(step));
                }}
              >
                Previous
              </Button>
              {criterion ? (
                <Button
                  type="button"
                  className="h-10 px-4"
                  onClick={() => {
                    go(nextStep(step, n));
                  }}
                >
                  {step === n - 1 ? "Review and submit" : "Save and next"}
                </Button>
              ) : (
                <Button
                  type="button"
                  className="h-10 px-4"
                  aria-describedby="submit-hint"
                  disabled={missing > 0 || submit.isPending}
                  onClick={() => {
                    submit.mutate({
                      items: criteria.map((c) => ({
                        criterion_id: c.id,
                        score: draft.scores[c.id] ?? 0,
                        comment: (draft.comments[c.id] ?? "").trim(),
                      })),
                      isEdit: rows.length > 0,
                    });
                  }}
                >
                  Submit feedback
                </Button>
              )}
            </div>
          </Card>
        </motion.div>
      </div>
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
    </div>
  );
}
