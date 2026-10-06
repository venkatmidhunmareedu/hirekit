import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { ErrorNotice } from "../../components/ErrorNotice";
import { EmptyState } from "../../components/EmptyState";
import { Loading } from "../../components/Loading";
import { PageHeader } from "../../components/PageHeader";
import { StatusTag } from "../../components/StatusTag";
import { candidateLabel } from "../candidates/api";
import { ScoreChip } from "../candidates/components/ScoreParts";

import { type CompareCell } from "./api";
import { compareQueryOptions } from "./hooks";

function Cell({ cell }: { cell: CompareCell | undefined }) {
  if (!cell) return <span className="text-muted-foreground">No data</span>;
  return (
    <div className="flex flex-col items-start gap-2 whitespace-normal">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted-foreground">Resume</span>
        <ScoreChip model={cell.model_score} override={cell.override_score} />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted-foreground">Interviewers</span>
        {cell.feedback.length === 0 ? (
          <span className="text-muted-foreground">none yet</span>
        ) : (
          cell.feedback.map((f) => (
            <Badge
              key={f.interviewer_id}
              variant="outline"
              className="mono h-6 px-2 font-mono text-xs"
            >
              {f.score} / 4
            </Badge>
          ))
        )}
      </div>
      {cell.disagreement && <StatusTag tone="warning">Interviewers disagree</StatusTag>}
      {cell.feedback.map((f) => (
        <p key={f.interviewer_id} className="max-w-prose text-muted-foreground">
          {f.comment}
        </p>
      ))}
    </div>
  );
}

/** Side-by-side comparison of two to four candidates (Design.md 8.7). Ids come from the URL. */
export function ComparePage({ ids }: { ids: string[] }) {
  const valid = ids.length >= 2 && ids.length <= 4;
  const comparison = useQuery({ ...compareQueryOptions(ids), enabled: valid });

  if (!valid) {
    return (
      <div className="flex flex-col gap-8">
        <PageHeader title="Compare candidates" />
        <EmptyState message="Choose two to four candidates to compare." />
      </div>
    );
  }
  if (comparison.isPending) return <Loading label="Loading the comparison" />;
  if (comparison.isError) {
    return (
      <ErrorNotice
        error={comparison.error}
        retry={() => {
          void comparison.refetch();
        }}
      />
    );
  }
  const { criteria, candidates } = comparison.data;

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Compare candidates"
        purpose="Resume scores are AI suggestions or scores changed by a recruiter. Interviewer scores sit beside them."
      />
      <div className="rounded-lg border bg-card">
        <Table>
          <TableHeader className="bg-muted/60">
            <TableRow className="hover:bg-transparent">
              <TableHead scope="col">Criterion</TableHead>
              {candidates.map((c) => (
                <TableHead key={c.candidate_id} scope="col" className="mono font-mono">
                  {candidateLabel(c.candidate_no)}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {criteria.map((crit) => (
              <TableRow key={crit.id} className="align-top">
                <TableHead scope="row" className="h-auto min-w-40 py-3 align-top whitespace-normal">
                  {crit.name}
                  <div className="text-sm font-normal text-muted-foreground">
                    {crit.kind === "must_have" ? "Must-have" : "Nice-to-have"}
                  </div>
                </TableHead>
                {candidates.map((cand) => (
                  <TableCell key={cand.candidate_id} className="min-w-48 py-3 align-top">
                    <Cell cell={cand.cells.find((x) => x.criterion_id === crit.id)} />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
