import { useQuery } from "@tanstack/react-query";

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
  if (!cell) return <span className="muted">No data</span>;
  return (
    <div className="stack">
      <div>
        <span className="muted">Resume </span>
        <ScoreChip model={cell.model_score} override={cell.override_score} />
      </div>
      <div>
        <span className="muted">Interviewers </span>
        {cell.feedback.length === 0 ? (
          <span className="muted">none yet</span>
        ) : (
          cell.feedback.map((f) => (
            <span key={f.interviewer_id} className="chip mono" title={f.comment}>
              {f.score} / 4
            </span>
          ))
        )}
      </div>
      {cell.disagreement && <StatusTag tone="warning">Interviewers disagree</StatusTag>}
      {cell.feedback.map((f) => (
        <p key={f.interviewer_id} className="muted">
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
      <div className="stack">
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
    <div className="stack">
      <PageHeader
        title="Compare candidates"
        purpose="Scores are model suggestions and recruiter overrides. Interviewer scores sit beside them."
      />
      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Criterion</th>
              {candidates.map((c) => (
                <th key={c.candidate_id} scope="col" className="mono">
                  {candidateLabel(c.candidate_no)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {criteria.map((crit) => (
              <tr key={crit.id}>
                <th scope="row">
                  {crit.name}
                  <div className="muted">
                    {crit.kind === "must_have" ? "Must-have" : "Nice-to-have"}
                  </div>
                </th>
                {candidates.map((cand) => (
                  <td key={cand.candidate_id}>
                    <Cell cell={cand.cells.find((x) => x.criterion_id === crit.id)} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
