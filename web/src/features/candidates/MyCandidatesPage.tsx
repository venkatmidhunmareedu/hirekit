import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";

import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { PageHeader } from "../../components/PageHeader";
import { ProgressBar } from "../../components/ProgressBar";
import { StatusTag } from "../../components/StatusTag";

import { candidateLabel } from "./api";
import { myCandidatesQueryOptions } from "./hooks";
import { queueProgress } from "./queue";

/** The interviewer's queue (US-00-014): progress, the next candidate, then everyone assigned. Anonymized ids only. */
export function MyCandidatesPage() {
  const mine = useQuery(myCandidatesQueryOptions);
  const { total, submitted, next } = queueProgress(mine.data ?? []);
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <PageHeader
        title="My candidates"
        purpose="Give feedback on each candidate you interviewed. AI scores stay hidden until you submit."
      />
      {mine.isPending && <Loading label="Loading your candidates" />}
      {mine.isError && (
        <ErrorNotice
          error={mine.error}
          retry={() => {
            void mine.refetch();
          }}
        />
      )}
      {mine.data?.length === 0 && (
        <EmptyState message="No candidates are assigned to you yet. A recruiter assigns them. When one is assigned, it appears here with a Give feedback button." />
      )}
      {mine.data && mine.data.length > 0 && (
        <>
          <section
            aria-label="Your progress"
            className="flex flex-col gap-4 rounded-lg border bg-card p-5"
          >
            <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
              <p role="status" className="text-lg font-semibold">
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
            <ProgressBar value={submitted} max={total} label="Feedback submitted" />
          </section>
          <ul aria-label="Candidates assigned to you" className="rounded-lg border bg-card">
            {mine.data.map((c) => (
              <li
                key={c.candidate_id}
                className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b px-4 py-3 last:border-b-0"
              >
                <Link
                  to="/candidates/$candidateId"
                  params={{ candidateId: c.candidate_id }}
                  className="font-mono text-base font-medium underline-offset-4 hover:underline max-sm:flex-1"
                >
                  {candidateLabel(c.candidate_no)}
                </Link>
                <span className="min-w-0 flex-1 text-sm text-muted-foreground max-sm:order-last max-sm:basis-full">
                  {c.role_title}
                </span>
                <StatusTag tone={c.has_submitted ? "success" : "neutral"}>
                  {c.has_submitted ? "Submitted" : "Not started"}
                </StatusTag>
                <Button asChild variant="outline" className="h-10 px-3">
                  <Link
                    to="/candidates/$candidateId"
                    params={{ candidateId: c.candidate_id }}
                    aria-label={`${c.has_submitted ? "View feedback" : "Give feedback"} for ${candidateLabel(c.candidate_no)}`}
                  >
                    {c.has_submitted ? "View" : "Give feedback"}
                    <ChevronRight aria-hidden="true" />
                  </Link>
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
