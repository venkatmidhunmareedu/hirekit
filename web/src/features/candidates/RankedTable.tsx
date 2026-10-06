import { Link } from "@tanstack/react-router";

import { type RankedCandidate, type ScoreCell, candidateLabel } from "./api";
import { ScoreChip } from "./components/ScoreParts";

const STAGE_LABEL: Record<RankedCandidate["stage"], string> = {
  new: "New",
  screened: "Screened",
  interview: "Interview",
  offer: "Offer",
  hired: "Hired",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

const PROCESSING_LABEL: Record<RankedCandidate["processing_status"], string> = {
  queued: "Queued",
  parsing: "Parsing",
  anonymizing: "Anonymizing",
  scoring: "Scoring",
  done: "Done",
  failed: "Failed",
};

/** A score cell: the shared chip labelled by source, or the plain no-score state. */
function ScoreCellView({ cell }: { cell: ScoreCell }) {
  if (cell.status === "failed") return <span>Scoring failed</span>;
  const value = cell.override_score ?? cell.model_score;
  if (cell.status === "no_evidence" || value === null) return <span>No evidence found</span>;
  return (
    <span className="chip-cell">
      <ScoreChip model={cell.model_score} override={cell.override_score} />
      <small className="muted">
        {cell.override_score !== null ? "Recruiter override" : "Model suggestion"}
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

  return (
    <div className="table-wrap">
      <table className="ranked">
        <caption className="visually-hidden">
          Candidates ranked by weighted total, highest first
        </caption>
        <thead>
          <tr>
            <th scope="col" className="num">
              Rank
            </th>
            <th scope="col">Candidate</th>
            <th scope="col">Select</th>
            <th scope="col" className="num" aria-sort="descending">
              Weighted score
            </th>
            <th scope="col">Must-have coverage</th>
            {[...criteria].map(([id, name]) => (
              <th scope="col" key={id}>
                {name}
              </th>
            ))}
            <th scope="col" className="num">
              Flags
            </th>
            <th scope="col">Stage</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((candidate, index) => {
            const flags = candidate.scores.filter((s) => s.flag_reason !== null).length;
            const ready = candidate.processing_status === "done";
            return (
              <tr key={candidate.id}>
                <td className="num">{offset + index + 1}</td>
                <th scope="row">
                  <Link to="/candidates/$candidateId" params={{ candidateId: candidate.id }}>
                    {candidateLabel(candidate.candidate_no)}
                  </Link>
                  {candidate.duplicate_of_candidate_no !== null && (
                    <small className="muted">
                      {" "}
                      Possible duplicate of {candidateLabel(candidate.duplicate_of_candidate_no)}
                    </small>
                  )}
                </th>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Select ${candidateLabel(candidate.candidate_no)} to compare`}
                    checked={selected.includes(candidate.id)}
                    onChange={() => {
                      onToggle(candidate.id);
                    }}
                  />
                </td>
                <td className="num">
                  {ready
                    ? candidate.total.toFixed(1)
                    : PROCESSING_LABEL[candidate.processing_status]}
                  {candidate.stale && <small className="muted"> Stale scores</small>}
                </td>
                <td>
                  {ready
                    ? `${candidate.must_have_covered} of ${candidate.must_have_total}`
                    : "Not scored yet"}
                </td>
                {[...criteria.keys()].map((id) => {
                  const cell = candidate.scores.find((s) => s.criterion_id === id);
                  return (
                    <td key={id}>{cell ? <ScoreCellView cell={cell} /> : "Not scored yet"}</td>
                  );
                })}
                <td className="num">{flags}</td>
                <td>{STAGE_LABEL[candidate.stage]}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
