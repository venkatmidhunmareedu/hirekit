import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";

import { ErrorNotice } from "../../components/ErrorNotice";
import { Icon } from "../../components/Icon";
import { Loading } from "../../components/Loading";
import { PageHeader } from "../../components/PageHeader";
import { sessionQueryOptions } from "../auth/hooks";
import { FeedbackPanel } from "../feedback/FeedbackPanel";
import { KitQuestions } from "../kit/KitPage";

import { type Kind, type ScoreCell, candidateLabel } from "./api";
import { OverrideDialog } from "./components/OverrideDialog";
import { EvidenceBlock, ScoreChip, sourceLabel } from "./components/ScoreParts";
import { Assignments, AuditHistory, ResumeText, RevealIdentity } from "./components/SidePanels";
import { StageControl } from "./components/StageControl";
import { candidateQueryOptions, myCandidatesQueryOptions, rankedQueryOptions } from "./hooks";

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
    <li className={selected ? "criterion-row criterion-selected flow" : "criterion-row flow"}>
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
  const mine = useQuery({ ...myCandidatesQueryOptions, enabled: !recruiter });
  // The first ranked page is enough to find the next candidate; no match means no link.
  const ranked = useQuery({
    ...rankedQueryOptions(candidate.data?.role_id ?? "", null, 0, false),
    enabled: recruiter && candidate.data !== undefined,
  });

  if (candidate.isPending) return <Loading label="Loading the candidate" />;
  if (candidate.isError) {
    return (
      <ErrorNotice
        error={candidate.error}
        retry={() => {
          void candidate.refetch();
        }}
      />
    );
  }
  const c = candidate.data;
  const list = ranked.data?.data ?? [];
  const next = list[list.findIndex((r) => r.id === c.id) + 1];
  const selected = c.scores.find((s) => s.criterion_id === selectedId) ?? null;

  const scores = (
    <section className="section" aria-labelledby="scores-heading">
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
                        setSelectedId(cell.criterion_id === selectedId ? null : cell.criterion_id);
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
  );

  if (!recruiter) {
    const submitted = mine.data?.find((m) => m.candidate_id === c.id)?.has_submitted ?? false;
    const nextToReview = mine.data?.find((m) => !m.has_submitted && m.candidate_id !== c.id);
    return (
      <div className="stack">
        <PageHeader
          title={`Candidate ${candidateLabel(c.candidate_no)}`}
          purpose="Use the interview kit, then score each criterion with a comment."
          breadcrumb={<Link to="/me/candidates">Back to My candidates</Link>}
        />
        {submitted && (
          <div role="status" className="notice notice-success">
            <span>Feedback submitted. Thank you.</span>
            {nextToReview ? (
              <Link
                to="/candidates/$candidateId"
                params={{ candidateId: nextToReview.candidate_id }}
                className="btn btn-primary"
              >
                Next candidate to review
              </Link>
            ) : (
              <Link to="/me/candidates" className="btn btn-secondary">
                Back to My candidates
              </Link>
            )}
          </div>
        )}
        <div className="detail-grid">
          <div className="stack">
            <FeedbackPanel key={c.id} candidateId={c.id} roleId={c.role_id} viewer="interviewer" />
            {scores}
          </div>
          <KitQuestions roleId={c.role_id} />
        </div>
      </div>
    );
  }

  return (
    <div className="stack">
      <PageHeader
        title={`Candidate ${candidateLabel(c.candidate_no)}`}
        breadcrumb={
          <Link to="/roles/$roleId/candidates" params={{ roleId: c.role_id }}>
            Back to ranked candidates
          </Link>
        }
        action={
          <>
            {next && (
              <Link
                to="/candidates/$candidateId"
                params={{ candidateId: next.id }}
                className="btn btn-secondary"
              >
                Next candidate
              </Link>
            )}
            <Link
              to="/roles/$roleId/kit"
              params={{ roleId: c.role_id }}
              className="btn btn-secondary"
            >
              Interview kit
            </Link>
          </>
        }
      />
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
      <section className="section" aria-label="Decision">
        <StageControl candidateId={c.id} stage={c.stage} />
        <RevealIdentity key={c.id} candidateId={c.id} />
      </section>
      <div className="detail-grid">
        <div className="stack">
          {scores}
          <FeedbackPanel key={c.id} candidateId={c.id} roleId={c.role_id} viewer="recruiter" />
        </div>
        <div className="stack">
          <ResumeText candidateId={c.id} quote={selected?.quote ?? null} />
          <Assignments key={c.id} candidateId={c.id} />
          <AuditHistory events={c.audit} />
        </div>
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
