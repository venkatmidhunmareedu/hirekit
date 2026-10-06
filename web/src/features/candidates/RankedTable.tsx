import { Link } from "@tanstack/react-router";

import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { type RankedCandidate, type ScoreCell, candidateLabel } from "./api";
import { ScoreChip } from "./components/ScoreParts";
import { PROCESSING_LABEL, STAGE_LABEL } from "./labels";

/** A score cell: the shared chip labelled by source, or the plain no-score state. */
function ScoreCellView({ cell }: { cell: ScoreCell }) {
  if (cell.status === "failed") return <span>Scoring failed</span>;
  const value = cell.override_score ?? cell.model_score;
  if (cell.status === "no_evidence" || value === null) return <span>No evidence found</span>;
  return (
    <span className="flex flex-col items-start gap-1">
      <ScoreChip model={cell.model_score} override={cell.override_score} />
      <small className="text-xs text-muted-foreground">
        {cell.override_score !== null ? "Changed by recruiter" : "AI suggestion"}
      </small>
    </span>
  );
}

/** Ranked table (Design.md 7.9, 8.3). Every candidate stays listed; rows are never hidden or colored by score. */
export function RankedTable({
  candidates,
  offset,
  selected,
  onToggle,
}: {
  candidates: RankedCandidate[];
  offset: number;
  selected: string[];
  onToggle: (id: string) => void;
}) {
  const criteria = new Map<string, string>();
  for (const candidate of candidates) {
    for (const cell of candidate.scores) criteria.set(cell.criterion_id, cell.criterion_name);
  }

  const NUM = "text-right font-mono tabular-nums";
  return (
    <div className="rounded-lg border bg-card">
      <Table>
        <TableCaption className="sr-only">
          Candidates ranked by weighted total, highest first
        </TableCaption>
        <TableHeader className="bg-muted/60">
          <TableRow className="hover:bg-transparent">
            <TableHead scope="col" className={NUM}>
              Rank
            </TableHead>
            <TableHead scope="col">Candidate</TableHead>
            <TableHead scope="col">Select</TableHead>
            <TableHead scope="col" className={NUM} aria-sort="descending">
              Weighted score
            </TableHead>
            <TableHead scope="col">Must-have coverage</TableHead>
            {[...criteria].map(([id, name]) => (
              <TableHead scope="col" key={id}>
                {name}
              </TableHead>
            ))}
            <TableHead scope="col" className={NUM}>
              Needs a look
            </TableHead>
            <TableHead scope="col">Hiring stage</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {candidates.map((candidate, index) => {
            const flags = candidate.scores.filter((s) => s.flag_reason !== null).length;
            const ready = candidate.processing_status === "done";
            return (
              <TableRow key={candidate.id}>
                <TableCell className={NUM}>{offset + index + 1}</TableCell>
                <TableHead scope="row">
                  <Link
                    to="/candidates/$candidateId"
                    params={{ candidateId: candidate.id }}
                    className="font-mono underline-offset-4 hover:underline"
                  >
                    {candidateLabel(candidate.candidate_no)}
                  </Link>
                  {candidate.duplicate_of_candidate_no !== null && (
                    <small className="block text-xs font-normal text-muted-foreground">
                      Possible duplicate of {candidateLabel(candidate.duplicate_of_candidate_no)}
                    </small>
                  )}
                </TableHead>
                <TableCell>
                  <Checkbox
                    aria-label={`Select ${candidateLabel(candidate.candidate_no)} to compare`}
                    checked={selected.includes(candidate.id)}
                    onCheckedChange={() => {
                      onToggle(candidate.id);
                    }}
                  />
                </TableCell>
                <TableCell className={NUM}>
                  {ready
                    ? candidate.total.toFixed(1)
                    : PROCESSING_LABEL[candidate.processing_status]}
                  {candidate.stale && (
                    <small className="block font-sans text-xs text-muted-foreground">
                      Scores are out of date
                    </small>
                  )}
                </TableCell>
                <TableCell>
                  {ready
                    ? `${candidate.must_have_covered} of ${candidate.must_have_total}`
                    : "Not scored yet"}
                </TableCell>
                {[...criteria.keys()].map((id) => {
                  const cell = candidate.scores.find((s) => s.criterion_id === id);
                  return (
                    <TableCell key={id}>
                      {cell ? <ScoreCellView cell={cell} /> : "Not scored yet"}
                    </TableCell>
                  );
                })}
                <TableCell className={NUM}>{flags}</TableCell>
                <TableCell>{STAGE_LABEL[candidate.stage]}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
