import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { Section } from "../../components/Section";
import { StatusTag } from "../../components/StatusTag";
import { type RoleCriterion } from "../kit/api";
import { kitQueryOptions, roleCriteriaQueryOptions } from "../kit/hooks";

import { type FeedbackRow } from "./api";
import { FeedbackFlow } from "./FeedbackFlow";
import { feedbackQueryOptions, useApproveEdit } from "./hooks";

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

  if (viewer === "interviewer") {
    return (
      <FeedbackFlow
        key={feedback.data.map((r) => (r.locked ? "1" : "0")).join("")}
        candidateId={candidateId}
        criteria={criteria}
        rows={feedback.data}
        questions={kit.data?.questions ?? []}
        onSubmitted={onSubmitted}
      />
    );
  }
  return (
    <Section id="feedback-heading" title="Interviewer feedback">
      <RecruiterFeedback candidateId={candidateId} criteria={criteria} rows={feedback.data} />
    </Section>
  );
}
