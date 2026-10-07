import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ChevronLeft, CircleCheck, Sparkles, TextSearch } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import { SectionNav } from "../../components/SectionNav";
import { scrollBehavior, useScrollSpy } from "../../lib/scrollSpy";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

import { ErrorNotice } from "../../components/ErrorNotice";
import { Loading } from "../../components/Loading";
import { Notice } from "../../components/Notice";
import { PageHeader } from "../../components/PageHeader";
import { Section } from "../../components/Section";
import { sessionQueryOptions } from "../auth/hooks";
import { FeedbackPanel } from "../feedback/FeedbackPanel";
import { feedbackQueryOptions } from "../feedback/hooks";
import { roleCriteriaQueryOptions } from "../kit/hooks";

import {
  type CandidateDetail,
  type MyCandidate,
  type Kind,
  type RankedCandidate,
  type ScoreCell,
  candidateLabel,
} from "./api";
import { OverrideDialog } from "./components/OverrideDialog";
import { EvidenceBlock, ScoreMeter, verifiedQuote } from "./components/ScoreParts";
import { Assignments, AuditHistory, ResumeText, RevealIdentity } from "./components/SidePanels";
import { StageControl } from "./components/StageControl";
import { processingLabel } from "./labels";
import { nextAfter } from "./queue";
import {
  assignmentsQueryOptions,
  candidateQueryOptions,
  myCandidatesQueryOptions,
  rankedQueryOptions,
  useRoleQueue,
} from "./hooks";

const GROUPS: { kind: Kind; title: string; icon: typeof CircleCheck }[] = [
  { kind: "must_have", title: "Must-have", icon: CircleCheck },
  { kind: "nice_to_have", title: "Nice-to-have", icon: Sparkles },
];

/** " (3)" for a tab label once the number is known. */
const count = (n: number | undefined) => (n === undefined ? "" : ` (${n})`);

const cardId = (id: string) => `criterion-${id}`;

const groupId = (kind: Kind) => `scores-group-${kind}`;

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
  /** Find this criterion's quote in the resume. */
  onSelect: () => void;
  /** Open the change-score flow with the clicked segment chosen. */
  onOverride: (score: number) => void;
}) {
  return (
    <li
      id={cardId(cell.criterion_id)}
      tabIndex={-1}
      className={cn(
        "flex scroll-mt-32 flex-col items-start gap-2 border-b px-3 py-4 outline-none last:border-b-0 focus-visible:ring-3 focus-visible:ring-ring/50",
        selected && "bg-muted",
      )}
    >
      <div className="flex w-full flex-wrap items-center justify-between gap-2">
        <h4 className="text-base font-medium">{cell.criterion_name}</h4>
        <ScoreMeter
          model={cell.model_score}
          override={cell.override_score}
          name={cell.criterion_name}
          onPick={recruiter ? onOverride : undefined}
        />
      </div>
      {(cell.source === "recruiter_override" || cell.source === "failed" || cell.stale) && (
        <p className="text-sm text-muted-foreground">
          {cell.source === "recruiter_override" && "Changed by recruiter"}
          {cell.source === "failed" && "Scoring failed"}
          {cell.stale && " (scores are out of date)"}
        </p>
      )}
      {recruiter && <EvidenceBlock cell={cell} onLocate={onSelect} />}
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
  onSelect: (id: string) => void;
  onOverride: (cell: ScoreCell, score: number) => void;
}) {
  const groups = GROUPS.map((g) => ({
    ...g,
    cells: c.scores.filter((s) => s.kind === g.kind),
  })).filter((g) => g.cells.length > 0);
  // The sticky header is 3.5rem and the navigator about 3rem; the top band of the page is "in view".
  const [active, setActive] = useScrollSpy(
    groups.map((g) => groupId(g.kind)),
    { rootMargin: "-112px 0px -55% 0px" },
  );
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
        <>
          <SectionNav
            label="Score groups"
            className="sticky top-14 z-10 -mx-1 border-b bg-background px-1 py-1"
            active={active}
            items={groups.map((g) => ({
              id: groupId(g.kind),
              label: g.title,
              count: g.cells.length,
              icon: g.icon,
            }))}
            onSelect={(id) => {
              setActive(id);
              document
                .getElementById(id)
                ?.scrollIntoView({ block: "start", behavior: scrollBehavior() });
            }}
          />
          {groups.map(({ kind, title, icon: Icon, cells }) => (
            <div key={kind} id={groupId(kind)} className="flex scroll-below-nav flex-col gap-2">
              <div className="flex items-center gap-2 rounded-md border-b bg-muted px-3 py-2">
                <Icon aria-hidden="true" className="size-5 text-primary" />
                <h3 className="text-lg font-semibold">{title}</h3>
                <span className="ml-auto font-mono text-sm text-muted-foreground">
                  {cells.length} {cells.length === 1 ? "criterion" : "criteria"}
                </span>
              </div>
              <ul className="flex flex-col">
                {cells.map((cell) => (
                  <CriterionRow
                    key={cell.criterion_id}
                    cell={cell}
                    recruiter={recruiter}
                    selected={cell.criterion_id === selectedId}
                    onSelect={() => {
                      onSelect(cell.criterion_id);
                    }}
                    onOverride={(score) => {
                      onOverride(cell, score);
                    }}
                  />
                ))}
              </ul>
            </div>
          ))}
        </>
      )}
    </Section>
  );
}

/**
 * The recruiter's review of one candidate (Design.md 8.4): total, hiring stage, evidence per
 * criterion and resume, with interviewers, feedback and history in tabs beside the resume. It renders in the review pane and on
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
  // `n` counts requests, so asking for the same quote again scrolls to it again.
  const [located, setLocated] = useState<{ id: string; n: number } | null>(null);
  const [overriding, setOverriding] = useState<{ cell: ScoreCell; score: number } | null>(null);
  const [tab, setTab] = useState("scoring");
  // A click on a highlight in the resume asks for that criterion's card; `n` repeats the request.
  const [cardRequest, setCardRequest] = useState<{ id: string; n: number } | null>(null);
  const selected = c.scores.find((s) => s.criterion_id === located?.id) ?? null;
  // The same queries the tab panels use, so the counts in the tab labels cost no extra request.
  const assigned = useQuery(assignmentsQueryOptions(c.id));
  const feedback = useQuery(feedbackQueryOptions(c.id));
  const marks = c.scores.flatMap((s) => {
    const quote = verifiedQuote(s);
    return quote ? [{ id: s.criterion_id, quote }] : [];
  });
  // Runs after the Scoring tab has mounted, so the card exists when the tab was another one.
  useEffect(() => {
    if (!cardRequest) return;
    const card = document.getElementById(cardId(cardRequest.id));
    card?.focus({ preventScroll: true });
    card?.scrollIntoView({ block: "center", behavior: scrollBehavior() });
  }, [cardRequest]);
  const from = pane ? "xl" : "lg";
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
          <Tabs value={tab} onValueChange={setTab} className="gap-3">
            <TabsList
              variant="line"
              className="h-auto w-full flex-wrap justify-start gap-0 border-b p-0"
            >
              <TabsTrigger
                value="scoring"
                className="h-9 flex-none px-2.5 after:bottom-[-1px] after:h-[3px] after:bg-primary data-[state=active]:font-semibold data-[state=active]:text-primary"
              >
                Scoring
              </TabsTrigger>
              <TabsTrigger
                value="interviewers"
                className="h-9 flex-none px-2.5 after:bottom-[-1px] after:h-[3px] after:bg-primary data-[state=active]:font-semibold data-[state=active]:text-primary"
              >
                Interviewers{count(assigned.data?.length)}
              </TabsTrigger>
              <TabsTrigger
                value="feedback"
                className="h-9 flex-none px-2.5 after:bottom-[-1px] after:h-[3px] after:bg-primary data-[state=active]:font-semibold data-[state=active]:text-primary"
              >
                Feedback
                {count(feedback.data && new Set(feedback.data.map((r) => r.interviewer_id)).size)}
              </TabsTrigger>
              <TabsTrigger
                value="history"
                className="h-9 flex-none px-2.5 after:bottom-[-1px] after:h-[3px] after:bg-primary data-[state=active]:font-semibold data-[state=active]:text-primary"
              >
                History{count(c.audit.length)}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="scoring">
              <ScoresSection
                c={c}
                recruiter
                selectedId={located?.id ?? null}
                onSelect={(id) => {
                  setLocated((now) => ({ id, n: (now?.n ?? 0) + 1 }));
                }}
                onOverride={(cell, score) => {
                  setOverriding({ cell, score });
                }}
              />
            </TabsContent>
            <TabsContent value="interviewers">
              <Assignments candidateId={c.id} />
            </TabsContent>
            <TabsContent value="feedback">
              <FeedbackPanel candidateId={c.id} roleId={c.role_id} viewer="recruiter" />
            </TabsContent>
            <TabsContent value="history">
              <AuditHistory events={c.audit} />
            </TabsContent>
          </Tabs>
        </div>
        <div className={cn("min-w-0", pane ? "xl:col-span-2" : "lg:col-span-2")}>
          <ResumeText
            candidateId={c.id}
            marks={marks}
            activeId={selected?.criterion_id ?? null}
            locate={located?.n ?? 0}
            onMarkClick={(id) => {
              setTab("scoring");
              setLocated((now) => ({ id, n: now?.n ?? 0 }));
              setCardRequest((now) => ({ id, n: (now?.n ?? 0) + 1 }));
            }}
            stickyFrom={from}
          />
        </div>
      </div>
      {overriding && (
        <OverrideDialog
          candidateId={c.id}
          cell={overriding.cell}
          initialScore={overriding.score}
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
  const { working } = useRoleQueue(candidate.data?.role_id ?? "", recruiter);
  // A second observer of the same query polls while scoring jobs are open.
  useQuery({ ...candidateQueryOptions(candidateId, true), enabled: working });
  const mine = useQuery({ ...myCandidatesQueryOptions, enabled: !recruiter });
  // The first ranked page is enough to find the next candidate; no match means no link.
  const ranked = useQuery({
    ...rankedQueryOptions(candidate.data?.role_id ?? "", null, 0, working),
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
 * The interviewer's feedback screen (Design.md 8.6): one centred column, one criterion at a time,
 * one page scroll. `justSubmitted` lives here, so the confirmation shows only for a submit made in
 * this visit; a revisit shows the read-only summary labelled Submitted, with no notice.
 */
function InterviewerView({ c, mine }: { c: CandidateDetail; mine: MyCandidate[] }) {
  const [justSubmitted, setJustSubmitted] = useState(false);
  const next = nextAfter(mine, c.id);
  const role = useQuery(roleCriteriaQueryOptions(c.role_id));
  return (
    <div className="mx-auto flex w-full max-w-180 flex-col gap-6">
      <PageHeader
        title={`Candidate ${candidateLabel(c.candidate_no)}`}
        purpose={role.data?.title}
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
      <FeedbackPanel
        key={c.id}
        candidateId={c.id}
        roleId={c.role_id}
        viewer="interviewer"
        onSubmitted={() => {
          setJustSubmitted(true);
        }}
      />
      {c.scores.length > 0 ? (
        <ScoresSection
          c={c}
          recruiter={false}
          selectedId={null}
          onSelect={() => undefined}
          onOverride={() => undefined}
        />
      ) : (
        <p className="text-sm text-muted-foreground">
          AI scores stay hidden until you submit your feedback, so they do not anchor your view.
        </p>
      )}
    </div>
  );
}
