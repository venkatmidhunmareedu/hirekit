import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  ArrowDown,
  ArrowUp,
  Check,
  ChevronLeft,
  Minus,
  Pencil,
  Printer,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import { ErrorNotice } from "../../components/ErrorNotice";
import { EmptyState } from "../../components/EmptyState";
import { Loading } from "../../components/Loading";
import { Notice } from "../../components/Notice";
import { PageHeader } from "../../components/PageHeader";
import { Section } from "../../components/Section";
import { RoleHeader } from "../roles/RoleHeader";
import { sessionQueryOptions } from "../auth/hooks";

import { type Question, type RoleCriterion } from "./api";
import {
  isJobDone,
  kitQueryOptions,
  roleCriteriaQueryOptions,
  useDeleteQuestion,
  useEditQuestion,
  useGenerateKit,
  useJobWatch,
  useRegenerate,
  useSwap,
} from "./hooks";

function QuestionCard({
  question,
  neighbours,
  roleId,
  recruiter,
  onJob,
}: {
  question: Question;
  neighbours: { prev: Question | null; next: Question | null };
  roleId: string;
  recruiter: boolean;
  onJob: (id: number) => void;
}) {
  const edit = useEditQuestion(roleId);
  const remove = useDeleteQuestion(roleId);
  const swap = useSwap(roleId);
  const regenerate = useRegenerate();
  const [draft, setDraft] = useState<Question | null>(null);
  const failure = edit.error ?? remove.error ?? swap.error ?? regenerate.error;

  if (draft) {
    return (
      <li>
        <Card className="px-5">
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              edit.mutate(
                {
                  id: question.id,
                  patch: {
                    question_text: draft.question_text.trim(),
                    strong_answer: draft.strong_answer.trim(),
                    weak_answer: draft.weak_answer.trim(),
                  },
                },
                {
                  onSuccess: () => {
                    setDraft(null);
                  },
                },
              );
            }}
          >
            {(
              [
                ["question_text", "Question"],
                ["strong_answer", "Strong answer"],
                ["weak_answer", "Weak answer"],
              ] as const
            ).map(([field, label]) => (
              <div className="flex flex-col gap-1.5" key={field}>
                <Label htmlFor={`${field}-${question.id}`}>{label}</Label>
                <Textarea
                  id={`${field}-${question.id}`}
                  rows={3}
                  required
                  value={draft[field]}
                  onChange={(e) => {
                    setDraft({ ...draft, [field]: e.target.value });
                  }}
                />
              </div>
            ))}
            {edit.error && <ErrorNotice error={edit.error} />}
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                className="h-10 px-4"
                onClick={() => {
                  setDraft(null);
                }}
              >
                Cancel
              </Button>
              <Button type="submit" className="h-10 px-4" disabled={edit.isPending}>
                Save question
              </Button>
            </div>
          </form>
        </Card>
      </li>
    );
  }

  return (
    <li>
      <Card className="@container gap-4 px-5">
        <h3 className="text-lg font-medium">{question.question_text}</h3>
        <div className="grid gap-3 @md:grid-cols-2">
          <div className="flex flex-col gap-1 rounded-md border bg-muted/50 p-3">
            <p className="flex items-center gap-1.5 text-sm font-medium">
              <Check aria-hidden="true" className="size-4" /> Strong answer
            </p>
            <p className="text-sm">{question.strong_answer}</p>
          </div>
          <div className="flex flex-col gap-1 rounded-md border border-dashed p-3">
            <p className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
              <Minus aria-hidden="true" className="size-4" /> Weak answer
            </p>
            <p className="text-sm text-muted-foreground">{question.weak_answer}</p>
          </div>
        </div>
        {failure && <ErrorNotice error={failure} />}
        {recruiter && (
          <div className="flex flex-wrap items-center gap-2 print:hidden">
            <Button
              type="button"
              variant="ghost"
              className="h-10 px-3"
              disabled={!neighbours.prev || swap.isPending}
              onClick={() => {
                if (neighbours.prev) swap.mutate([question, neighbours.prev]);
              }}
            >
              <ArrowUp aria-hidden="true" />
              Move up
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="h-10 px-3"
              disabled={!neighbours.next || swap.isPending}
              onClick={() => {
                if (neighbours.next) swap.mutate([question, neighbours.next]);
              }}
            >
              <ArrowDown aria-hidden="true" />
              Move down
            </Button>
            <Button
              type="button"
              variant="outline"
              className="h-10 px-3"
              onClick={() => {
                setDraft(question);
              }}
            >
              <Pencil aria-hidden="true" />
              Edit
            </Button>
            <Button
              type="button"
              variant="outline"
              className="h-10 px-3"
              disabled={regenerate.isPending}
              onClick={() => {
                regenerate.mutate(question.id, { onSuccess: onJob });
              }}
            >
              <RefreshCw aria-hidden="true" />
              Regenerate
            </Button>
            <Button
              type="button"
              variant="destructive"
              className="h-10 px-3"
              disabled={remove.isPending}
              onClick={() => {
                remove.mutate(question.id);
              }}
            >
              <Trash2 aria-hidden="true" />
              Delete
            </Button>
          </div>
        )}
      </Card>
    </li>
  );
}

function QuestionGroups({
  roleId,
  criteria,
  questions: all,
  recruiter,
  onJob,
}: {
  roleId: string;
  criteria: RoleCriterion[];
  questions: Question[];
  recruiter: boolean;
  onJob: (id: number) => void;
}) {
  return criteria.map((crit) => {
    const questions = all
      .filter((q) => q.criterion_id === crit.id)
      .sort((a, b) => a.position - b.position);
    if (questions.length === 0) return null;
    return (
      <Section key={crit.id} id={`criterion-${crit.id}`} title={crit.name}>
        <ul className="flex flex-col gap-4">
          {questions.map((q, i) => (
            <QuestionCard
              key={q.id}
              question={q}
              neighbours={{ prev: questions[i - 1] ?? null, next: questions[i + 1] ?? null }}
              roleId={roleId}
              recruiter={recruiter}
              onJob={onJob}
            />
          ))}
        </ul>
      </Section>
    );
  });
}

/** The kit's questions for an interviewer, read-only, to sit beside the feedback form. */
export function KitQuestions({ roleId }: { roleId: string }) {
  const role = useQuery(roleCriteriaQueryOptions(roleId));
  const kit = useQuery(kitQueryOptions(roleId));
  if (role.isPending || kit.isPending) return <Loading label="Loading the interview kit" />;
  if (role.isError) return <ErrorNotice error={role.error} />;
  if (kit.isError) return <ErrorNotice error={kit.error} />;
  if (kit.data.questions.length === 0) {
    return <EmptyState message="The interview kit is not ready yet." />;
  }
  const criteria = [...role.data.criteria].sort(
    (a, b) =>
      Number(b.kind === "must_have") - Number(a.kind === "must_have") || a.position - b.position,
  );
  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-xl font-medium">Interview kit</h2>
      <QuestionGroups
        roleId={roleId}
        criteria={criteria}
        questions={kit.data.questions}
        recruiter={false}
        onJob={() => undefined}
      />
    </div>
  );
}

/** Interview kit (Design.md 8.5): questions grouped by criterion. Recruiters edit; interviewers print. */
export function KitPage({ roleId }: { roleId: string }) {
  const { data: session } = useSuspenseQuery(sessionQueryOptions);
  const recruiter = session.user.role === "recruiter";
  const role = useQuery(roleCriteriaQueryOptions(roleId));
  const kit = useQuery(kitQueryOptions(roleId));
  const generate = useGenerateKit(roleId);
  const [jobId, setJobId] = useState<number | null>(null);
  const job = useJobWatch(roleId, jobId);
  const running = jobId !== null && !isJobDone(job.data?.status);

  if (role.isPending || kit.isPending) return <Loading label="Loading the interview kit" />;
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
  if (kit.isError) {
    return (
      <ErrorNotice
        error={kit.error}
        retry={() => {
          void kit.refetch();
        }}
      />
    );
  }

  const criteria = [...role.data.criteria].sort(
    (a, b) =>
      Number(b.kind === "must_have") - Number(a.kind === "must_have") || a.position - b.position,
  );
  const hasQuestions = kit.data.questions.length > 0;
  const draftRole = role.data.status === "draft";

  return (
    <div className="flex flex-col gap-8">
      {recruiter ? (
        <RoleHeader role={role.data} current="kit" pageHasPrimary />
      ) : (
        <PageHeader
          title={`Interview kit: ${role.data.title}`}
          breadcrumb={
            <Link
              to="/me/candidates"
              className="inline-flex min-h-10 items-center gap-1 hover:text-foreground"
            >
              <ChevronLeft aria-hidden="true" className="size-4" />
              Back to My candidates
            </Link>
          }
          action={
            <Button
              type="button"
              variant="ghost"
              className="h-10 px-4 text-muted-foreground"
              onClick={() => {
                window.print();
              }}
            >
              <Printer aria-hidden="true" />
              Print interview kit
            </Button>
          }
        />
      )}
      {recruiter && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2>Interview kit</h2>
          <Button
            type="button"
            className="h-10 px-4"
            disabled={draftRole || running || generate.isPending}
            onClick={() => {
              generate.mutate(undefined, { onSuccess: setJobId });
            }}
          >
            {hasQuestions ? "Regenerate interview kit" : "Generate interview kit"}
          </Button>
        </div>
      )}
      {draftRole && <Notice>Approve the criteria to start generating the interview kit.</Notice>}
      {kit.data.stale && (
        <Notice tone="warning">
          This interview kit was generated for older criteria. Regenerate it to match the current
          ones.
        </Notice>
      )}
      {running && <Loading label="Generating, this can take a minute" />}
      {job.data && isJobDone(job.data.status) && job.data.status !== "succeeded" && (
        <Notice tone="danger">
          Generating the interview kit{" "}
          {job.data.status === "cancelled" ? "was cancelled" : "did not finish"}. Try again.
        </Notice>
      )}
      {generate.error && <ErrorNotice error={generate.error} />}
      {!hasQuestions && !draftRole && (
        <EmptyState
          message={
            recruiter
              ? "No interview kit yet. Generate it to see questions."
              : "The interview kit is not ready yet."
          }
        />
      )}
      <QuestionGroups
        roleId={roleId}
        criteria={criteria}
        questions={kit.data.questions}
        recruiter={recruiter}
        onJob={setJobId}
      />
    </div>
  );
}
