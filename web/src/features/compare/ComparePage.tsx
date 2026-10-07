import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Pencil } from "lucide-react";

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
import { type Kind, candidateLabel } from "../candidates/api";
import { ScoreChip } from "../candidates/components/ScoreParts";

import { type CompareCell } from "./api";
import { compareQueryOptions } from "./hooks";

function Cell({ cell }: { cell: CompareCell | undefined }) {
  if (!cell) return <span className="text-muted-foreground">No data</span>;
  return (
    <div className="flex flex-col items-start gap-2 whitespace-normal">
      <div className="flex flex-wrap items-center gap-2">
        <span className="w-20 text-muted-foreground">Resume</span>
        <ScoreChip model={cell.model_score} override={cell.override_score} />
      </div>
      {cell.override_score !== null && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Pencil aria-hidden="true" className="size-3" /> Changed by recruiter
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <span className="w-20 text-muted-foreground">Interviewers</span>
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
        <p key={f.interviewer_id} className="max-w-prose text-xs text-muted-foreground">
          {f.comment}
        </p>
      ))}
    </div>
  );
}

const GROUPS: { kind: Kind; title: string }[] = [
  { kind: "must_have", title: "Must-have" },
  { kind: "nice_to_have", title: "Nice-to-have" },
];

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
        purpose="Resume scores sit beside interviewer scores. Open a candidate to see the evidence."
      />
      <p className="text-sm text-muted-foreground md:hidden">
        Scroll sideways to see every candidate; the criterion column stays in view.
      </p>
      <div
        role="region"
        aria-label="Candidate comparison table"
        tabIndex={0}
        className="review-rail overflow-auto rounded-lg border bg-card focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none *:data-[slot=table-container]:overflow-visible"
      >
        <Table className="border-separate border-spacing-0">
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead
                scope="col"
                className="sticky top-0 left-0 z-30 border-r border-b bg-muted text-foreground"
              >
                Criterion
              </TableHead>
              {candidates.map((c) => (
                <TableHead
                  key={c.candidate_id}
                  scope="col"
                  className="sticky top-0 z-20 border-b bg-muted"
                >
                  <Link
                    to="/candidates/$candidateId"
                    params={{ candidateId: c.candidate_id }}
                    className="mono inline-flex min-h-10 items-center font-mono text-base font-semibold text-foreground underline-offset-4 hover:underline"
                  >
                    {candidateLabel(c.candidate_no)}
                  </Link>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          {GROUPS.map(({ kind, title }) => {
            const rows = criteria.filter((crit) => crit.kind === kind);
            if (rows.length === 0) return null;
            return (
              <TableBody key={kind}>
                <TableRow className="hover:bg-transparent">
                  <TableHead
                    scope="rowgroup"
                    colSpan={candidates.length + 1}
                    className="h-9 border-b bg-muted/60 text-foreground"
                  >
                    <div className="sticky left-0 w-fit">{title}</div>
                  </TableHead>
                </TableRow>
                {rows.map((crit) => (
                  <TableRow key={crit.id} className="align-top">
                    <TableHead
                      scope="row"
                      className="sticky left-0 z-10 h-auto min-w-40 border-r border-b bg-card py-3 align-top whitespace-normal"
                    >
                      {crit.name}
                    </TableHead>
                    {candidates.map((cand) => (
                      <TableCell
                        key={cand.candidate_id}
                        className="min-w-56 border-b py-3 align-top"
                      >
                        <Cell cell={cand.cells.find((x) => x.criterion_id === crit.id)} />
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            );
          })}
        </Table>
      </div>
    </div>
  );
}
