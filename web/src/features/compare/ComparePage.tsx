import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ChevronLeft, CircleCheck, Equal, Pencil, Sparkles, Trophy } from "lucide-react";
import { motion } from "motion/react";

import { Badge } from "@/components/ui/badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { cn } from "@/lib/utils";
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
import { candidateQueryOptions } from "../candidates/hooks";
import { roleCriteriaQueryOptions } from "../kit/hooks";
import { ScoreChip } from "../candidates/components/ScoreParts";

import { type CompareCell } from "./api";
import { compareQueryOptions } from "./hooks";
import { type Marker, highestCounts, markersFor, shownScore } from "./highlights";

/** A short bar, score out of 4, so the eye can compare cells without reading numbers. */
function ScoreBar({ score }: { score: number }) {
  return (
    <div aria-hidden="true" className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
      <motion.div
        className="h-full origin-left rounded-full bg-primary"
        initial={{ scaleX: 0 }}
        animate={{ scaleX: score / 4 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
      />
    </div>
  );
}

function MarkerTag({ marker }: { marker: Marker }) {
  if (marker === "none") return null;
  const highest = marker === "highest";
  const Icon = highest ? Trophy : Equal;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        highest ? "bg-primary text-primary-foreground" : "border bg-background text-foreground",
      )}
    >
      <Icon aria-hidden="true" className="size-3.5" />
      {highest ? "Highest" : "Tied"}
    </span>
  );
}

function Cell({ cell, marker }: { cell: CompareCell | undefined; marker: Marker }) {
  if (!cell) return <span className="text-muted-foreground">No data</span>;
  const score = shownScore(cell);
  return (
    <div className="flex flex-col items-start gap-2 whitespace-normal">
      <div className="flex flex-wrap items-center gap-2">
        <span className="w-20 text-muted-foreground">Resume</span>
        <ScoreChip model={cell.model_score} override={cell.override_score} />
        <MarkerTag marker={marker} />
      </div>
      {score !== null && <ScoreBar score={score} />}
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

const GROUPS: { kind: Kind; title: string; icon: typeof CircleCheck }[] = [
  { kind: "must_have", title: "Must-have", icon: CircleCheck },
  { kind: "nice_to_have", title: "Nice-to-have", icon: Sparkles },
];

/** Side-by-side comparison of two to four candidates (Design.md 8.7). Ids come from the URL. */
export function ComparePage({ ids }: { ids: string[] }) {
  const valid = ids.length >= 2 && ids.length <= 4;
  const comparison = useQuery({ ...compareQueryOptions(ids), enabled: valid });
  // The role gives the page its context and its way back; the page works without it.
  const first = useQuery({ ...candidateQueryOptions(ids[0] ?? ""), enabled: valid });
  const roleId = first.data?.role_id ?? "";
  const role = useQuery({ ...roleCriteriaQueryOptions(roleId), enabled: roleId !== "" });

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
  const counts = highestCounts(
    candidates,
    criteria.map((c) => c.id),
  );

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Compare candidates"
        purpose="Resume scores sit beside interviewer scores. Open a candidate to see the evidence."
        breadcrumb={
          <div className="flex flex-col gap-1">
            {roleId !== "" && (
              <Breadcrumb>
                <BreadcrumbList>
                  <BreadcrumbItem>
                    <BreadcrumbLink asChild>
                      <Link to="/roles">Roles</Link>
                    </BreadcrumbLink>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    <BreadcrumbLink asChild>
                      <Link to="/roles/$roleId/candidates" params={{ roleId }}>
                        {role.data?.title ?? "This role"}
                      </Link>
                    </BreadcrumbLink>
                  </BreadcrumbItem>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    <BreadcrumbPage>Compare</BreadcrumbPage>
                  </BreadcrumbItem>
                </BreadcrumbList>
              </Breadcrumb>
            )}
            {roleId !== "" && (
              <Link
                to="/roles/$roleId/candidates"
                params={{ roleId }}
                className="inline-flex min-h-10 items-center gap-1 hover:text-foreground"
              >
                <ChevronLeft aria-hidden="true" className="size-4" />
                Back to ranked candidates
              </Link>
            )}
          </div>
        }
      />
      <section aria-label="Highest scores per candidate" className="flex flex-col gap-2">
        <ul className="flex flex-wrap gap-3">
          {candidates.map((c) => (
            <li
              key={c.candidate_id}
              className="flex min-w-40 items-center gap-3 rounded-lg border bg-card px-4 py-3"
            >
              <Trophy aria-hidden="true" className="size-5 text-primary" />
              <div>
                <p className="font-mono text-base font-semibold">
                  {candidateLabel(c.candidate_no)}
                </p>
                <p className="text-sm text-muted-foreground">
                  Highest on {counts[c.candidate_id] ?? 0}{" "}
                  {counts[c.candidate_id] === 1 ? "criterion" : "criteria"}
                </p>
              </div>
            </li>
          ))}
        </ul>
        <p className="text-sm text-muted-foreground">
          Highest means the highest AI-suggested or recruiter-changed score on that criterion.
          People decide.
        </p>
      </section>
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
          {GROUPS.map(({ kind, title, icon: Icon }) => {
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
                    <div className="sticky left-0 flex w-fit items-center gap-2">
                      <Icon aria-hidden="true" className="size-4 text-primary" />
                      {title}
                      <span
                        aria-hidden="true"
                        className="font-mono text-xs font-normal text-muted-foreground"
                      >
                        {rows.length}
                      </span>
                    </div>
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
                    {candidates.map((cand) => {
                      const marker = markersFor(candidates, crit.id)[cand.candidate_id] ?? "none";
                      return (
                        <TableCell
                          key={cand.candidate_id}
                          className={cn(
                            "min-w-56 border-b py-3 align-top",
                            marker === "highest" && "bg-primary/10",
                          )}
                        >
                          <Cell
                            cell={cand.cells.find((x) => x.criterion_id === crit.id)}
                            marker={marker}
                          />
                        </TableCell>
                      );
                    })}
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
