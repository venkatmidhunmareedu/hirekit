import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { CircleCheck, ClipboardList, Hourglass, Send, type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { PageHeader } from "../../components/PageHeader";
import { StatusTag } from "../../components/StatusTag";
import { candidateLabel } from "../candidates/api";
import { myCandidatesQueryOptions } from "../candidates/hooks";
import { queueProgress } from "../candidates/queue";

import { GrowBar } from "./Charts";

function Count({ icon: Icon, value, label }: { icon: LucideIcon; value: number; label: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border bg-background p-4">
      <Icon aria-hidden="true" className="size-4 text-muted-foreground" />
      <p className="font-display text-3xl leading-none font-medium tabular-nums">{value}</p>
      <p className="text-sm font-medium">{label}</p>
    </div>
  );
}

/** The interviewer's overview: how much feedback is done, the next candidate, and everyone assigned. */
export function InterviewerDashboard() {
  const mine = useQuery(myCandidatesQueryOptions);
  const { total, submitted, next } = queueProgress(mine.data ?? []);
  const remaining = total - submitted;
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <PageHeader
        title="Dashboard"
        purpose="Your feedback queue. AI scores stay hidden until you submit your own."
      />
      {mine.isPending && (
        <div aria-busy="true" className="flex flex-col gap-4">
          <p role="status" className="sr-only">
            Loading your candidates
          </p>
          <Skeleton className="h-28" />
          <Skeleton className="h-40" />
        </div>
      )}
      {mine.isError && (
        <ErrorNotice
          error={mine.error}
          retry={() => {
            void mine.refetch();
          }}
        />
      )}
      {mine.data?.length === 0 && (
        <EmptyState message="No candidates are assigned to you yet. A recruiter assigns them. When one is assigned, it appears here." />
      )}
      {mine.data && mine.data.length > 0 && (
        <>
          <section
            aria-label="Your progress"
            className="flex flex-col gap-4 rounded-lg border bg-card p-5"
          >
            <div className="grid grid-cols-3 gap-3">
              <Count icon={ClipboardList} value={total} label="Assigned" />
              <Count icon={Send} value={submitted} label="Submitted" />
              <Count icon={Hourglass} value={remaining} label="Remaining" />
            </div>
            <GrowBar percent={Math.round((submitted / total) * 100)} label="Feedback submitted" />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p role="status" className="text-sm text-muted-foreground">
                {submitted} of {total} submitted
              </p>
              {next ? (
                <Button asChild className="h-10 px-4">
                  <Link to="/candidates/$candidateId" params={{ candidateId: next.candidate_id }}>
                    {submitted === 0
                      ? "Start feedback"
                      : `Continue with ${candidateLabel(next.candidate_no)}`}
                  </Link>
                </Button>
              ) : (
                <StatusTag tone="success">All feedback submitted</StatusTag>
              )}
            </div>
          </section>
          <section aria-labelledby="assigned" className="flex flex-col gap-3">
            <div className="flex items-center justify-between gap-3">
              <h2 id="assigned">Assigned to you</h2>
              <Link
                to="/me/candidates"
                className="text-sm font-medium text-primary underline-offset-4 hover:underline"
              >
                Open My candidates
              </Link>
            </div>
            <ul className="rounded-lg border bg-card">
              {mine.data.map((c) => (
                <li
                  key={c.candidate_id}
                  className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b px-4 py-3 last:border-b-0"
                >
                  <Link
                    to="/candidates/$candidateId"
                    params={{ candidateId: c.candidate_id }}
                    className="font-mono font-medium underline-offset-4 hover:underline"
                  >
                    {candidateLabel(c.candidate_no)}
                  </Link>
                  <span className="min-w-0 flex-1 text-sm text-muted-foreground">
                    {c.role_title}
                  </span>
                  <StatusTag tone={c.has_submitted ? "success" : "neutral"}>
                    {c.has_submitted ? "Submitted" : "Not started"}
                  </StatusTag>
                </li>
              ))}
            </ul>
          </section>
          {remaining === 0 && (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <CircleCheck aria-hidden="true" className="size-4 text-ok" />
              Nothing left to do. A recruiter may assign more.
            </p>
          )}
        </>
      )}
    </div>
  );
}
