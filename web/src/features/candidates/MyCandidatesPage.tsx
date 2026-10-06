import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { PageHeader } from "../../components/PageHeader";
import { StatusTag } from "../../components/StatusTag";

import { candidateLabel } from "./api";
import { myCandidatesQueryOptions } from "./hooks";

/** The interviewer's assigned candidates (US-00-014). Anonymized ids only. */
export function MyCandidatesPage() {
  const mine = useQuery(myCandidatesQueryOptions);
  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="My candidates"
        purpose="Give feedback on each candidate you interviewed. AI scores stay hidden until you submit."
      />
      {mine.data && mine.data.length > 0 && (
        <p role="status" className="text-sm text-muted-foreground">
          {mine.data.filter((c) => !c.has_submitted).length} to review,{" "}
          {mine.data.filter((c) => c.has_submitted).length} submitted
        </p>
      )}
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
        <div className="rounded-lg border bg-card">
          <Table>
            <TableCaption className="sr-only">Candidates assigned to you</TableCaption>
            <TableHeader className="bg-muted/60">
              <TableRow className="hover:bg-transparent">
                <TableHead scope="col">Candidate</TableHead>
                <TableHead scope="col">Role</TableHead>
                <TableHead scope="col">Your feedback</TableHead>
                <TableHead scope="col">
                  <span className="sr-only">Action</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mine.data.map((c) => (
                <TableRow key={c.candidate_id}>
                  <TableCell className="font-mono">
                    <Link
                      to="/candidates/$candidateId"
                      params={{ candidateId: c.candidate_id }}
                      className="underline-offset-4 hover:underline"
                    >
                      {candidateLabel(c.candidate_no)}
                    </Link>
                  </TableCell>
                  <TableCell>{c.role_title}</TableCell>
                  <TableCell>
                    <StatusTag tone={c.has_submitted ? "success" : "neutral"}>
                      {c.has_submitted ? "Submitted" : "Not submitted"}
                    </StatusTag>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      asChild
                      variant={c.has_submitted ? "outline" : "default"}
                      className="h-10 px-4"
                    >
                      <Link
                        to="/candidates/$candidateId"
                        params={{ candidateId: c.candidate_id }}
                        aria-label={`${c.has_submitted ? "View feedback" : "Give feedback"} for ${candidateLabel(c.candidate_no)}`}
                      >
                        {c.has_submitted ? "View feedback" : "Give feedback"}
                      </Link>
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
