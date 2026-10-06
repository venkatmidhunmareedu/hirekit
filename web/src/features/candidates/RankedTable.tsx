import { Link } from "@tanstack/react-router";

import type { RankedCandidate, ScoreCell } from "./api";

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

/** Anonymous label (Design.md section 9): the number, never a name. */
export function candidateLabel(no: number): string {
  return `C-${String(no).padStart(3, "0")}`;
}

/** A score chip (Design.md 7.2): neutral, mono numerals, labelled by source, never colored by value. */
function ScoreChip({ cell }: { cell: ScoreCell }) {
  if (cell.status === "failed") return <span>Scoring failed</span>;
  if (cell.status === "no_evidence") return <span>No evidence found</span>;
  const overridden = cell.override_score !== null;
  const value = cell.override_score ?? cell.model_score;
  if (value === null) return <span>No evidence found</span>;
  return (
    <span className="chip-cell">
      <span className="chip">
        {value} / 4
        {overridden && cell.model_score !== null && (
          <s className="muted" aria-label={`model score ${cell.model_score}`}>
            {cell.model_score}
          </s>
        )}
      </span>
      <small className="muted">{overridden ? "Recruiter override" : "Model suggestion"}</small>
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
            <th scope="col">Compare</th>
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
                  return <td key={id}>{cell ? <ScoreChip cell={cell} /> : "Not scored yet"}</td>;
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
