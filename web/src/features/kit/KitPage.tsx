import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ErrorNotice } from "../../components/ErrorNotice";
import { EmptyState } from "../../components/EmptyState";
import { Icon } from "../../components/Icon";
import { Loading } from "../../components/Loading";
import { PageHeader } from "../../components/PageHeader";
import { sessionQueryOptions } from "../auth/hooks";

import { type Question } from "./api";
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
      <li className="card">
        <form
          className="stack"
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
            <div className="field" key={field}>
              <label htmlFor={`${field}-${question.id}`}>{label}</label>
              <textarea
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
          <div className="actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setDraft(null);
              }}
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={edit.isPending}>
              Save question
            </button>
          </div>
        </form>
      </li>
    );
  }

  return (
    <li className="card stack">
      <h3>{question.question_text}</h3>
      <div className="answer-pair">
        <div className="answer">
          <p className="tag">
            <Icon name="check" /> Strong answer
          </p>
          <p>{question.strong_answer}</p>
        </div>
        <div className="answer">
          <p className="tag">
            <Icon name="minus" /> Weak answer
          </p>
          <p>{question.weak_answer}</p>
        </div>
      </div>
      {failure && <ErrorNotice error={failure} />}
      {recruiter && (
        <div className="actions no-print">
          <button
            type="button"
            className="btn btn-ghost"
            disabled={!neighbours.prev || swap.isPending}
            onClick={() => {
              if (neighbours.prev) swap.mutate([question, neighbours.prev]);
            }}
          >
            Move up
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={!neighbours.next || swap.isPending}
            onClick={() => {
              if (neighbours.next) swap.mutate([question, neighbours.next]);
            }}
          >
            Move down
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setDraft(question);
            }}
          >
            Edit
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={regenerate.isPending}
            onClick={() => {
              regenerate.mutate(question.id, { onSuccess: onJob });
            }}
          >
            Regenerate
          </button>
          <button
            type="button"
            className="btn btn-destructive"
            disabled={remove.isPending}
            onClick={() => {
              remove.mutate(question.id);
            }}
          >
            Delete
          </button>
        </div>
      )}
    </li>
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
    <div className="stack">
      <PageHeader
        title={`Interview kit: ${role.data.title}`}
        action={
          recruiter ? (
            <button
              type="button"
              className="btn btn-primary"
              disabled={draftRole || running || generate.isPending}
              onClick={() => {
                generate.mutate(undefined, { onSuccess: setJobId });
              }}
            >
              {hasQuestions ? "Regenerate kit" : "Generate kit"}
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                window.print();
              }}
            >
              Print kit
            </button>
          )
        }
      />
      {draftRole && (
        <p role="status" className="notice notice-info">
          Approve the criteria to start generating the kit.
        </p>
      )}
      {kit.data.stale && (
        <p role="status" className="notice notice-warning">
          <Icon name="triangle" color="var(--warning)" />
          <span>
            This kit was generated for older criteria. Regenerate it to match the current ones.
          </span>
        </p>
      )}
      {running && <Loading label="Generating, this can take a minute" />}
      {job.data && isJobDone(job.data.status) && job.data.status !== "succeeded" && (
        <p role="alert" className="notice notice-danger">
          The generation job ended as {job.data.status}. Try again.
        </p>
      )}
      {generate.error && <ErrorNotice error={generate.error} />}
      {!hasQuestions && !draftRole && (
        <EmptyState
          message={
            recruiter
              ? "No kit yet. Generate the kit to see questions."
              : "The kit is not ready yet."
          }
        />
      )}
      {criteria.map((crit) => {
        const questions = kit.data.questions
          .filter((q) => q.criterion_id === crit.id)
          .sort((a, b) => a.position - b.position);
        if (questions.length === 0) return null;
        return (
          <section key={crit.id} aria-label={crit.name} className="section">
            <h2>{crit.name}</h2>
            <ul className="plain-list stack">
              {questions.map((q, i) => (
                <QuestionCard
                  key={q.id}
                  question={q}
                  neighbours={{ prev: questions[i - 1] ?? null, next: questions[i + 1] ?? null }}
                  roleId={roleId}
                  recruiter={recruiter}
                  onJob={setJobId}
                />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
