import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";

import { ErrorNotice } from "../../components/ErrorNotice";
import { Icon } from "../../components/Icon";
import { sessionQueryOptions } from "../auth/hooks";
import { FeedbackPanel } from "../feedback/FeedbackPanel";

import { type Kind, type ScoreCell, candidateLabel } from "./api";
import { OverrideDialog } from "./components/OverrideDialog";
import { EvidenceBlock, ScoreChip, sourceLabel } from "./components/ScoreParts";
import { Assignments, AuditHistory, ResumeText, RevealIdentity } from "./components/SidePanels";
import { StageControl } from "./components/StageControl";
import { candidateQueryOptions } from "./hooks";

const GROUPS: { kind: Kind; title: string }[] = [
  { kind: "must_have", title: "Must-have" },
  { kind: "nice_to_have", title: "Nice-to-have" },
];

function CriterionRow({
  cell,
  recruiter,
  selected,
  onSelect,
  onOverride,
}: {
  cell: ScoreCell;
  recruiter: boolean;
  selected: boolean;
  onSelect: () => void;
  onOverride: () => void;
}) {
  return (
    <li className={selected ? "criterion-row criterion-selected" : "criterion-row"}>
      <div className="row-between">
        <h4>{cell.criterion_name}</h4>
        <ScoreChip model={cell.model_score} override={cell.override_score} />
      </div>
      <p className="muted">
        {sourceLabel(cell)}
        {cell.stale && " (older criteria version)"}
      </p>
      {recruiter && <EvidenceBlock cell={cell} />}
      {cell.override_note && <p>Override note: {cell.override_note}</p>}
      {recruiter && (
        <div className="actions">
          <button
            type="button"
            className="btn btn-ghost"
            aria-pressed={selected}
            aria-label={`Show ${cell.criterion_name} in resume`}
            onClick={onSelect}
          >
            Show in resume
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            aria-label={`Override ${cell.criterion_name}`}
            onClick={onOverride}
          >
            <Icon name="pencil" /> Override
          </button>
        </div>
      )}
    </li>
  );
}

/** Candidate detail (Design.md 8.4): evidence per criterion, overrides, stage, history, feedback. */
export function CandidateDetailPage({ candidateId }: { candidateId: string }) {
  const { data: session } = useSuspenseQuery(sessionQueryOptions);
  const recruiter = session.user.role === "recruiter";
  const candidate = useQuery(candidateQueryOptions(candidateId));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [overriding, setOverriding] = useState<ScoreCell | null>(null);

  if (candidate.isPending) return <p role="status">Loading the candidate</p>;
  if (candidate.isError) return <ErrorNotice error={candidate.error} />;
  const c = candidate.data;
  const selected = c.scores.find((s) => s.criterion_id === selectedId) ?? null;

  return (
    <div className="stack">
      <div className="row-between">
        <h1>Candidate {candidateLabel(c.candidate_no)}</h1>
        <Link to="/roles/$roleId/kit" params={{ roleId: c.role_id }} className="btn btn-secondary">
          Interview kit
        </Link>
      </div>
      {c.processing_status && c.processing_status !== "done" && (
        <p role="status" className="notice notice-info">
          Processing status: {c.processing_status}. Scores appear when processing is done.
        </p>
      )}
      {c.scores.some((s) => s.stale) && (
        <p role="status" className="notice notice-warning">
          <Icon name="triangle" color="var(--warning)" />
          <span>Some scores come from older criteria. Re-run scoring from the ranked list.</span>
        </p>
      )}
      {recruiter && (
        <section className="card stack" aria-label="Decision">
          <StageControl candidateId={c.id} stage={c.stage} />
          <RevealIdentity key={c.id} candidateId={c.id} />
        </section>
      )}
      <div className="detail-grid">
        <div className="stack">
          <section className="card" aria-labelledby="scores-heading">
            <h2 id="scores-heading">Scores</h2>
            {c.scores.length === 0 ? (
              <p className="muted">
                {recruiter
                  ? "No scores yet."
                  : "Model scores stay hidden until you submit your feedback, so they do not anchor your view."}
              </p>
            ) : (
              GROUPS.map(({ kind, title }) => {
                const cells = c.scores.filter((s) => s.kind === kind);
                return (
                  cells.length > 0 && (
                    <div key={kind}>
                      <h3>{title}</h3>
                      <ul className="plain-list">
                        {cells.map((cell) => (
                          <CriterionRow
                            key={cell.criterion_id}
                            cell={cell}
                            recruiter={recruiter}
                            selected={cell.criterion_id === selectedId}
                            onSelect={() => {
                              setSelectedId(
                                cell.criterion_id === selectedId ? null : cell.criterion_id,
                              );
                            }}
                            onOverride={() => {
                              setOverriding(cell);
                            }}
                          />
                        ))}
                      </ul>
                    </div>
                  )
                );
              })
            )}
          </section>
          <FeedbackPanel
            key={c.id}
            candidateId={c.id}
            roleId={c.role_id}
            viewer={recruiter ? "recruiter" : "interviewer"}
          />
        </div>
        {recruiter && (
          <div className="stack">
            <ResumeText candidateId={c.id} quote={selected?.quote ?? null} />
            <Assignments key={c.id} candidateId={c.id} />
            <AuditHistory events={c.audit} />
          </div>
        )}
      </div>
      {overriding && (
        <OverrideDialog
          candidateId={c.id}
          cell={overriding}
          onClose={() => {
            setOverriding(null);
          }}
        />
      )}
    </div>
  );
}
