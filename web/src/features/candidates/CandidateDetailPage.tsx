import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ChevronLeft, Pencil, TextSearch } from "lucide-react";
import { type ReactNode, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { Notice } from "../../components/Notice";
import { PageHeader } from "../../components/PageHeader";
import { Section } from "../../components/Section";
import { sessionQueryOptions } from "../auth/hooks";
import { FeedbackPanel } from "../feedback/FeedbackPanel";
import { KitQuestions } from "../kit/KitPage";

import {
  type CandidateDetail,
  type MyCandidate,
  type Kind,
  type RankedCandidate,
  type ScoreCell,
  candidateLabel,
} from "./api";
import { OverrideDialog } from "./components/OverrideDialog";
import { EvidenceBlock, ScoreChip } from "./components/ScoreParts";
import { Assignments, AuditHistory, ResumeText, RevealIdentity } from "./components/SidePanels";
import { StageControl } from "./components/StageControl";
import { processingLabel } from "./labels";
import { nextAfter } from "./queue";
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
    <li
      className={cn(
        "flex flex-col items-start gap-2 border-b px-3 py-4 last:border-b-0",
        selected && "bg-muted",
      )}
    >
      <div className="flex w-full flex-wrap items-center justify-between gap-2">
        <h4 className="text-base font-medium">{cell.criterion_name}</h4>
        <ScoreChip model={cell.model_score} override={cell.override_score} />
      </div>
      {(cell.source === "recruiter_override" || cell.source === "failed" || cell.stale) && (
        <p className="text-sm text-muted-foreground">
          {cell.source === "recruiter_override" && "Changed by recruiter"}
          {cell.source === "failed" && "Scoring failed"}
          {cell.stale && " (scores are out of date)"}
        </p>
      )}
      {recruiter && <EvidenceBlock cell={cell} />}
      {cell.override_note && <p>Note on the changed score: {cell.override_note}</p>}
      {recruiter && (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            className="h-10 px-3"
            aria-pressed={selected}
            aria-label={`Show ${cell.criterion_name} in resume`}
            onClick={onSelect}
          >
            <TextSearch aria-hidden="true" />
            Show in resume
          </Button>
          <Button
            type="button"
            variant="outline"
            className="h-10 px-3"
            aria-label={`Change score for ${cell.criterion_name}`}
            onClick={onOverride}
          >
            <Pencil aria-hidden="true" />
            Change score
          </Button>
        </div>
      )}
    </li>
  );
}

function ScoresSection({
  c,
  recruiter,
  selectedId,
  onSelect,
  onOverride,
}: {
  c: CandidateDetail;
  recruiter: boolean;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onOverride: (cell: ScoreCell) => void;
}) {
  return (
    <Section
      id="scores-heading"
      title="Scores"
      description={c.scores.length > 0 ? "Scores are AI suggestions." : undefined}
    >
      {c.scores.length === 0 ? (
        <p className="text-muted-foreground">
          {recruiter
            ? "No scores yet."
            : "AI scores stay hidden until you submit your feedback, so they do not anchor your view."}
        </p>
      ) : (
        GROUPS.map(({ kind, title }) => {
          const cells = c.scores.filter((s) => s.kind === kind);
          return (
            cells.length > 0 && (
              <div key={kind} className="flex flex-col gap-1">
                <h3 className="text-lg font-medium">{title}</h3>
                <ul className="flex flex-col">
                  {cells.map((cell) => (
                    <CriterionRow
                      key={cell.criterion_id}
                      cell={cell}
                      recruiter={recruiter}
                      selected={cell.criterion_id === selectedId}
                      onSelect={() => {
                        onSelect(cell.criterion_id === selectedId ? null : cell.criterion_id);
                      }}
                      onOverride={() => {
                        onOverride(cell);
                      }}
                    />
                  ))}
                </ul>
              </div>
            )
          );
        })
      )}
    </Section>
  );
}

/**
 * The recruiter's review of one candidate (Design.md 8.4): total, hiring stage, evidence per
 * criterion, resume, feedback, interviewers and history. It renders in the review pane and on
 * the candidate page; `pane` only changes the heading level and the column break.
 */
export function CandidateReview({
  c,
  summary,
  pane,
  controls,
}: {
  c: CandidateDetail;
  summary: RankedCandidate | undefined;
  pane: boolean;
  controls?: ReactNode;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [overriding, setOverriding] = useState<ScoreCell | null>(null);
  const selected = c.scores.find((s) => s.criterion_id === selectedId) ?? null;
  return (
    <div className="flex flex-col gap-6">
      <div
        role="region"
        aria-label="Decision"
        className="flex flex-col gap-4 rounded-lg border bg-card px-5 py-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
          {pane ? (
            <h2 className="font-mono text-2xl font-semibold tracking-tight">
              Candidate {candidateLabel(c.candidate_no)}
            </h2>
          ) : (
            <span />
          )}
          {controls}
        </div>
        <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3 border-t pt-4">
          {summary?.processing_status === "done" && (
            <dl className="flex gap-8">
              <div>
                <dt className="text-xs text-muted-foreground">Weighted total</dt>
                <dd className="font-mono text-2xl font-semibold tabular-nums">
                  {summary.total.toFixed(1)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Must-haves covered</dt>
                <dd className="font-mono text-2xl font-semibold tabular-nums">
                  {summary.must_have_covered}{" "}
                  <span className="font-sans text-base font-normal">of</span>{" "}
                  {summary.must_have_total}
                </dd>
              </div>
            </dl>
          )}
          <StageControl candidateId={c.id} stage={c.stage} />
          <RevealIdentity key={c.id} candidateId={c.id} />
        </div>
      </div>
      {c.processing_status && c.processing_status !== "done" && (
        <Notice>
          Processing: {processingLabel(c.processing_status).toLowerCase()}. Scores appear when
          processing is finished.
        </Notice>
      )}
      {c.scores.some((s) => s.stale) && (
        <Notice tone="warning">
          Scores are out of date because the criteria changed. Re-score from the ranked list.
        </Notice>
      )}
      <div className={cn("grid gap-x-8 gap-y-8", pane ? "xl:grid-cols-5" : "lg:grid-cols-5")}>
        <div className={cn("min-w-0", pane ? "xl:col-span-3" : "lg:col-span-3")}>
          <ScoresSection
            c={c}
            recruiter
            selectedId={selectedId}
            onSelect={setSelectedId}
            onOverride={setOverriding}
          />
        </div>
        <div className={cn("min-w-0", pane ? "xl:col-span-2" : "lg:col-span-2")}>
          <ResumeText candidateId={c.id} quote={selected?.quote ?? null} />
        </div>
      </div>
      <FeedbackPanel key={c.id} candidateId={c.id} roleId={c.role_id} viewer="recruiter" />
      <div className={cn("grid gap-x-8 gap-y-8", pane ? "xl:grid-cols-2" : "lg:grid-cols-2")}>
        <Assignments key={c.id} candidateId={c.id} />
        <AuditHistory events={c.audit} />
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

/** The review pane's body: loads the candidate, then shows the review. */
export function ReviewPane({
  candidateId,
  summary,
  controls,
}: {
  candidateId: string;
  summary: RankedCandidate | undefined;
  controls: ReactNode;
}) {
  const candidate = useQuery(candidateQueryOptions(candidateId));
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
  // key: drafts and open dialogs belong to one candidate.
  return (
    <CandidateReview
      key={candidateId}
      c={candidate.data}
      summary={summary}
      pane
      controls={controls}
    />
  );
}

/** Candidate page (Design.md 8.4): the recruiter's review or the interviewer's feedback form. */
export function CandidateDetailPage({ candidateId }: { candidateId: string }) {
  const { data: session } = useSuspenseQuery(sessionQueryOptions);
  const recruiter = session.user.role === "recruiter";
  const candidate = useQuery(candidateQueryOptions(candidateId));
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

  if (!recruiter) {
    return <InterviewerView c={c} mine={mine.data ?? []} />;
  }

  const list = ranked.data?.data ?? [];
  const at = list.findIndex((r) => r.id === c.id);
  const next = list[at + 1];
  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title={`Candidate ${candidateLabel(c.candidate_no)}`}
        breadcrumb={
          <Link
            to="/roles/$roleId/candidates"
            params={{ roleId: c.role_id }}
            className="inline-flex items-center gap-1 hover:text-foreground"
          >
            <ChevronLeft aria-hidden="true" className="size-4" />
            Back to ranked candidates
          </Link>
        }
        action={
          <>
            {next && (
              <Button asChild variant="outline" className="h-10 px-4">
                <Link to="/candidates/$candidateId" params={{ candidateId: next.id }}>
                  Next candidate
                </Link>
              </Button>
            )}
            <Button asChild variant="outline" className="h-10 px-4">
              <Link to="/roles/$roleId/kit" params={{ roleId: c.role_id }}>
                Interview kit
              </Link>
            </Button>
          </>
        }
      />
      <CandidateReview key={c.id} c={c} summary={list[at]} pane={false} />
    </div>
  );
}

/**
 * The interviewer's feedback screen (Design.md 8.6): the form on the left, the interview kit on
 * the right in a sticky scroll region. `justSubmitted` lives here, so the confirmation shows only
 * for a submit made in this visit; a revisit shows the read-only form labelled Submitted.
 */
function InterviewerView({ c, mine }: { c: CandidateDetail; mine: MyCandidate[] }) {
  const [justSubmitted, setJustSubmitted] = useState(false);
  const next = nextAfter(mine, c.id);
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={`Candidate ${candidateLabel(c.candidate_no)}`}
        purpose="Use the interview kit, then score each criterion with a comment."
        breadcrumb={
          <Link
            to="/me/candidates"
            className="inline-flex min-h-10 items-center gap-1 hover:text-foreground"
          >
            <ChevronLeft aria-hidden="true" className="size-4" />
            Back to My candidates
          </Link>
        }
      />
      {justSubmitted && (
        <Notice
          tone="success"
          action={
            next ? (
              <Button asChild className="h-10 px-4">
                <Link to="/candidates/$candidateId" params={{ candidateId: next.candidate_id }}>
                  Next candidate
                </Link>
              </Button>
            ) : (
              <Button asChild className="h-10 px-4">
                <Link to="/me/candidates">Back to My candidates</Link>
              </Button>
            )
          }
        >
          Feedback submitted. Thank you.
          {next ? "" : " That was your last candidate."}
        </Notice>
      )}
      <div className="grid gap-x-10 gap-y-8 lg:grid-cols-5">
        <div className="flex min-w-0 flex-col gap-8 lg:col-span-3">
          <FeedbackPanel
            key={c.id}
            candidateId={c.id}
            roleId={c.role_id}
            viewer="interviewer"
            onSubmitted={() => {
              setJustSubmitted(true);
            }}
          />
          <ScoresSection
            c={c}
            recruiter={false}
            selectedId={null}
            onSelect={() => undefined}
            onOverride={() => undefined}
          />
        </div>
        <div className="min-w-0 lg:sticky lg:top-20 lg:col-span-2 lg:review-rail lg:self-start lg:overflow-y-auto">
          <KitQuestions roleId={c.role_id} />
        </div>
      </div>
    </div>
  );
}
