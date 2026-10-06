import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ChevronLeft, Pencil, TextSearch } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { Notice } from "../../components/Notice";
import { PageHeader } from "../../components/PageHeader";
import { Section } from "../../components/Section";
import { sessionQueryOptions } from "../auth/hooks";
import { FeedbackPanel } from "../feedback/FeedbackPanel";
import { KitQuestions } from "../kit/KitPage";

import { type Kind, type ScoreCell, candidateLabel } from "./api";
import { OverrideDialog } from "./components/OverrideDialog";
import { EvidenceBlock, ScoreChip, sourceLabel } from "./components/ScoreParts";
import { Assignments, AuditHistory, ResumeText, RevealIdentity } from "./components/SidePanels";
import { StageControl } from "./components/StageControl";
import { processingLabel } from "./labels";
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
      <p className="text-sm text-muted-foreground">
        {sourceLabel(cell)}
        {cell.stale && " (scores are out of date)"}
      </p>
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

/** Candidate detail (Design.md 8.4): evidence per criterion, changed scores, hiring stage, history, feedback. */
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
    <Section id="scores-heading" title="Scores">
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
    </Section>
  );

  if (!recruiter) {
    const submitted = mine.data?.find((m) => m.candidate_id === c.id)?.has_submitted ?? false;
    const nextToReview = mine.data?.find((m) => !m.has_submitted && m.candidate_id !== c.id);
    return (
      <div className="flex flex-col gap-8">
        <PageHeader
          title={`Candidate ${candidateLabel(c.candidate_no)}`}
          purpose="Use the interview kit, then score each criterion with a comment."
          breadcrumb={
            <Link
              to="/me/candidates"
              className="inline-flex items-center gap-1 hover:text-foreground"
            >
              <ChevronLeft aria-hidden="true" className="size-4" />
              Back to My candidates
            </Link>
          }
        />
        {submitted && (
          <Notice
            tone="success"
            action={
              nextToReview ? (
                <Button asChild className="h-10 px-4">
                  <Link
                    to="/candidates/$candidateId"
                    params={{ candidateId: nextToReview.candidate_id }}
                  >
                    Next candidate to review
                  </Link>
                </Button>
              ) : (
                <Button asChild variant="outline" className="h-10 px-4">
                  <Link to="/me/candidates">Back to My candidates</Link>
                </Button>
              )
            }
          >
            Feedback submitted. Thank you.
          </Notice>
        )}
        <div className="grid gap-x-10 gap-y-8 lg:grid-cols-5">
          <div className="flex min-w-0 flex-col gap-8 lg:col-span-3">
            <FeedbackPanel key={c.id} candidateId={c.id} roleId={c.role_id} viewer="interviewer" />
            {scores}
          </div>
          <div className="min-w-0 lg:col-span-2">
            <KitQuestions roleId={c.role_id} />
          </div>
        </div>
      </div>
    );
  }

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
      <Card
        role="region"
        aria-label="Decision"
        className="flex-row flex-wrap items-end justify-between gap-x-8 gap-y-4 px-5"
      >
        <StageControl candidateId={c.id} stage={c.stage} />
        <RevealIdentity key={c.id} candidateId={c.id} />
      </Card>
      <div className="grid gap-x-10 gap-y-8 lg:grid-cols-5">
        <div className="flex min-w-0 flex-col gap-8 lg:col-span-3">
          {scores}
          <FeedbackPanel key={c.id} candidateId={c.id} roleId={c.role_id} viewer="recruiter" />
        </div>
        <div className="flex min-w-0 flex-col gap-8 lg:col-span-2">
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
