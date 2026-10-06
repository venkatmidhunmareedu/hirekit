import { useQuery } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { useState } from "react";

import { Icon } from "../../components/Icon";
import { ErrorNotice } from "../../components/ErrorNotice";
import { type RoleCriterion } from "../kit/api";
import { roleCriteriaQueryOptions } from "../kit/hooks";

import { type FeedbackRow } from "./api";
import { feedbackQueryOptions, useApproveEdit, useSubmitFeedback } from "./hooks";

/** Interviewer feedback form (Design.md 8.6): one section per criterion, radio scores. */
function FeedbackForm({
  candidateId,
  criteria,
  rows,
}: {
  candidateId: string;
  criteria: RoleCriterion[];
  rows: FeedbackRow[];
}) {
  const submit = useSubmitFeedback(candidateId);
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
  useBlocker({
    shouldBlockFn: () =>
      dirty && !window.confirm("Leave this page? Your feedback is not submitted."),
    enableBeforeUnload: () => dirty,
    disabled: !dirty,
  });

  return (
    <form
      className="stack"
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
      <p role="status">
        {done} of {criteria.length} criteria scored
      </p>
      {readOnly && (
        <p className="tag muted">
          <Icon name="lock" /> Submitted and locked. A recruiter can approve an edit.
        </p>
      )}
      {criteria.map((c) => (
        <fieldset key={c.id} className="criterion-box" disabled={readOnly}>
          <legend>{c.name}</legend>
          <div
            className="radio-row"
            role="radiogroup"
            aria-label={`Score for ${c.name}`}
            aria-describedby={`rubric-${c.id}`}
          >
            {[0, 1, 2, 3, 4].map((n) => (
              <label key={n} className="radio">
                <input
                  type="radio"
                  name={`score-${c.id}`}
                  checked={scores[c.id] === n}
                  onChange={() => {
                    setScores({ ...scores, [c.id]: n });
                  }}
                />
                <span className="mono">{n}</span>
              </label>
            ))}
          </div>
          <ul id={`rubric-${c.id}`} className="plain-list muted">
            {[0, 1, 2, 3, 4].map((n) => {
              const descriptor = c.rubric.find((l) => l.level === n)?.descriptor;
              return (
                descriptor && (
                  <li key={n} className={scores[c.id] === n ? "rubric-selected" : undefined}>
                    <span className="mono">{n}</span> {descriptor}
                  </li>
                )
              );
            })}
          </ul>
          <div className="field">
            <label htmlFor={`comment-${c.id}`}>Comment on {c.name}</label>
            <textarea
              id={`comment-${c.id}`}
              rows={2}
              value={comments[c.id] ?? ""}
              onChange={(e) => {
                setComments({ ...comments, [c.id]: e.target.value });
              }}
            />
          </div>
        </fieldset>
      ))}
      {submit.error && <ErrorNotice error={submit.error} />}
      {!readOnly && (
        <div className="stack">
          <p id="submit-hint" className="muted">
            {missing > 0
              ? `${missing} ${missing === 1 ? "criterion still needs" : "criteria still need"} a score and a comment. `
              : ""}
            Locked after submit; a recruiter can approve an edit.
          </p>
          <div className="actions">
            <button
              type="submit"
              className="btn btn-primary"
              aria-describedby="submit-hint"
              disabled={missing > 0 || submit.isPending}
            >
              Submit feedback
            </button>
          </div>
        </div>
      )}
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
  if (interviewers.length === 0) return <p className="muted">No feedback submitted yet.</p>;
  return (
    <div className="stack">
      {approve.error && <ErrorNotice error={approve.error} />}
      {interviewers.map((id) => {
        const mine = rows.filter((r) => r.interviewer_id === id);
        const locked = mine.every((r) => r.locked);
        return (
          <section
            key={id}
            className="criterion-box"
            aria-label={`Feedback from interviewer ${id}`}
          >
            <div className="row-between">
              <h3>
                Interviewer <span className="mono">{id.slice(0, 8)}</span>
              </h3>
              {locked ? (
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={approve.isPending}
                  onClick={() => {
                    approve.mutate(id);
                  }}
                >
                  Approve edit for {id.slice(0, 8)}
                </button>
              ) : (
                <span className="tag muted">Unlocked for an edit</span>
              )}
            </div>
            <ul className="plain-list">
              {mine.map((r) => (
                <li key={r.criterion_id}>
                  <strong>
                    {criteria.find((c) => c.id === r.criterion_id)?.name ?? "Criterion"}
                  </strong>
                  : <span className="mono">{r.score} / 4</span> {r.comment}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

export function FeedbackPanel({
  candidateId,
  roleId,
  viewer,
}: {
  candidateId: string;
  roleId: string;
  viewer: "recruiter" | "interviewer";
}) {
  const role = useQuery(roleCriteriaQueryOptions(roleId));
  const feedback = useQuery(feedbackQueryOptions(candidateId));
  if (role.isPending || feedback.isPending) return <p role="status">Loading feedback</p>;
  if (role.isError) return <ErrorNotice error={role.error} />;
  if (feedback.isError) return <ErrorNotice error={feedback.error} />;
  const criteria = [...role.data.criteria].sort((a, b) => a.position - b.position);

  return (
    <section aria-labelledby="feedback-heading" className="section">
      <h2 id="feedback-heading">Interviewer feedback</h2>
      {viewer === "recruiter" ? (
        <RecruiterFeedback candidateId={candidateId} criteria={criteria} rows={feedback.data} />
      ) : (
        <FeedbackForm
          key={feedback.data.map((r) => (r.locked ? "1" : "0")).join("")}
          candidateId={candidateId}
          criteria={criteria}
          rows={feedback.data}
        />
      )}
    </section>
  );
}
