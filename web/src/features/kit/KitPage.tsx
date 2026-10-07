import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  ChevronLeft,
  ChevronsDownUp,
  ChevronsUpDown,
  CircleCheck,
  Printer,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { type ReactNode, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { Label } from "@/components/ui/label";

import { ErrorNotice } from "../../components/ErrorNotice";
import { EmptyState } from "../../components/EmptyState";
import { Loading } from "../../components/Loading";
import { Notice } from "../../components/Notice";
import { PageHeader } from "../../components/PageHeader";
import { type NavItem, SectionNav } from "../../components/SectionNav";
import { scrollBehavior, useScrollSpy } from "../../lib/scrollSpy";
import { RoleHeader } from "../roles/RoleHeader";
import { sessionQueryOptions } from "../auth/hooks";

import { type Question, type RoleCriterion } from "./api";
import {
  isJobDone,
  kitQueryOptions,
  roleCriteriaQueryOptions,
  useGenerateKit,
  useJobWatch,
} from "./hooks";
import { KitQuestionCard } from "./KitQuestionCard";

export const kitSectionId = (criterionId: string) => `kit-${criterionId}`;

const kindLabel = (crit: RoleCriterion) =>
  crit.kind === "must_have" ? "Must-have" : "Nice-to-have";
const kindIcon = (crit: RoleCriterion) => (crit.kind === "must_have" ? CircleCheck : Sparkles);

/** The criteria that have questions, with the question count, for the section navigator. */
export function kitNavItems(criteria: RoleCriterion[], questions: Question[]): NavItem[] {
  return criteria
    .map((crit) => ({
      id: kitSectionId(crit.id),
      label: crit.name,
      meta: kindLabel(crit),
      count: questions.filter((q) => q.criterion_id === crit.id).length,
      icon: kindIcon(crit),
    }))
    .filter((item) => item.count > 0);
}

/** Which questions have their answers open. Held by the page so "Expand all" can reach every card. */
function useOpenAnswers(questions: Question[]) {
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());
  const all = questions.length > 0 && questions.every((q) => open.has(q.id));
  return {
    open,
    all,
    toggle: (id: string) => {
      const next = new Set(open);
      if (!next.delete(id)) next.add(id);
      setOpen(next);
    },
    setAll: (value: boolean) => {
      setOpen(value ? new Set(questions.map((q) => q.id)) : new Set());
    },
  };
}

type OpenAnswers = ReturnType<typeof useOpenAnswers>;

function QuestionGroups({
  roleId,
  criteria,
  questions: all,
  recruiter,
  answers,
  onJob,
}: {
  roleId: string;
  criteria: RoleCriterion[];
  questions: Question[];
  recruiter: boolean;
  answers: OpenAnswers;
  onJob: (id: number) => void;
}) {
  const groups = criteria
    .map((crit) => ({
      crit,
      questions: all
        .filter((q) => q.criterion_id === crit.id)
        .sort((a, b) => a.position - b.position),
    }))
    .filter((g) => g.questions.length > 0);
  return groups.map(({ crit, questions }, g) => {
    const Icon = kindIcon(crit);
    const before = groups.slice(0, g).reduce((sum, p) => sum + p.questions.length, 0);
    return (
      <section
        key={crit.id}
        id={kitSectionId(crit.id)}
        aria-labelledby={`${kitSectionId(crit.id)}-title`}
        className="flex scroll-below-header flex-col gap-3"
      >
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border-b bg-muted px-3 py-2">
          <Icon aria-hidden="true" className="size-5 text-primary" />
          <h2 id={`${kitSectionId(crit.id)}-title`}>{crit.name}</h2>
          <span className="ml-auto flex items-center gap-3 text-sm text-muted-foreground">
            <span>{kindLabel(crit)}</span>
            <span className="font-mono">
              {questions.length} {questions.length === 1 ? "question" : "questions"}
            </span>
          </span>
        </div>
        <ul className="flex flex-col gap-3">
          {questions.map((q, i) => (
            <KitQuestionCard
              key={q.id}
              question={q}
              number={before + i + 1}
              neighbours={{ prev: questions[i - 1] ?? null, next: questions[i + 1] ?? null }}
              roleId={roleId}
              recruiter={recruiter}
              open={answers.open.has(q.id)}
              onToggle={() => {
                answers.toggle(q.id);
              }}
              onJob={onJob}
            />
          ))}
        </ul>
      </section>
    );
  });
}

/** The kit's questions for an interviewer, read-only, to sit beside the feedback form. */
export function KitQuestions({ roleId }: { roleId: string }) {
  const role = useQuery(roleCriteriaQueryOptions(roleId));
  const kit = useQuery(kitQueryOptions(roleId));
  const answers = useOpenAnswers(kit.data?.questions ?? []);
  if (role.isPending || kit.isPending) return <Loading label="Loading the interview kit" />;
  if (role.isError) return <ErrorNotice error={role.error} />;
  if (kit.isError) return <ErrorNotice error={kit.error} />;
  if (kit.data.questions.length === 0) {
    return <EmptyState message="The interview kit is not ready yet." />;
  }
  // Same order as the feedback form beside it, so the two stay in step.
  const criteria = [...role.data.criteria].sort((a, b) => a.position - b.position);
  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-xl font-medium">Interview kit</h2>
      <QuestionGroups
        roleId={roleId}
        criteria={criteria}
        questions={kit.data.questions}
        recruiter={false}
        answers={answers}
        onJob={() => undefined}
      />
    </div>
  );
}

/** Regenerating replaces every question, edits included, so it asks first. */
function RegenerateButton({ disabled, onConfirm }: { disabled: boolean; onConfirm: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button" className="h-10 px-4" disabled={disabled}>
          <RefreshCw aria-hidden="true" />
          Regenerate interview kit
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Replace the interview kit?</DialogTitle>
          <DialogDescription>
            Regeneration replaces every question, including the ones you edited, moved or deleted.
            The new questions follow the current criteria.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            className="h-10 px-4"
            onClick={() => {
              setOpen(false);
            }}
          >
            Cancel
          </Button>
          <Button
            type="button"
            className="h-10 px-4"
            onClick={() => {
              setOpen(false);
              onConfirm();
            }}
          >
            Replace the kit
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Rail from lg (sticky list of criteria), a "Jump to criterion" select below; both scroll the page. */
function KitContent({
  navItems,
  actions,
  recruiter,
  ...groups
}: {
  navItems: NavItem[];
  actions: ReactNode;
  roleId: string;
  criteria: RoleCriterion[];
  questions: Question[];
  recruiter: boolean;
  onJob: (id: number) => void;
}) {
  const answers = useOpenAnswers(groups.questions);
  const [active, setActive] = useScrollSpy(
    navItems.map((i) => i.id),
    { rootMargin: "-80px 0px -55% 0px" },
  );
  const jump = (id: string) => {
    setActive(id);
    document.getElementById(id)?.scrollIntoView({ block: "start", behavior: scrollBehavior() });
  };
  const total = groups.questions.length;
  const ToggleIcon = answers.all ? ChevronsDownUp : ChevronsUpDown;
  return (
    <>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="mr-auto flex flex-wrap items-baseline gap-x-3">
          <h2>Interview kit</h2>
          <span className="font-mono text-sm text-muted-foreground">
            {total} {total === 1 ? "question" : "questions"}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 print:hidden">
          <Button
            type="button"
            variant="ghost"
            className="h-10 px-3 text-muted-foreground"
            onClick={() => {
              answers.setAll(!answers.all);
            }}
          >
            <ToggleIcon aria-hidden="true" />
            {answers.all ? "Collapse all answers" : "Expand all answers"}
          </Button>
          {recruiter && (
            <Button
              type="button"
              variant="ghost"
              className="h-10 px-3 text-muted-foreground"
              onClick={() => {
                window.print();
              }}
            >
              <Printer aria-hidden="true" />
              Print
            </Button>
          )}
          {actions}
        </div>
      </div>
      <div className="kit-grid">
        {navItems.length > 1 && (
          <>
            <div className="flex flex-col gap-1.5 lg:hidden print:hidden">
              <Label htmlFor="kit-jump">Jump to criterion</Label>
              <select
                id="kit-jump"
                value={active ?? ""}
                onChange={(e) => {
                  jump(e.target.value);
                }}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                {navItems.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label} ({item.count})
                  </option>
                ))}
              </select>
            </div>
            <div className="sticky top-20 hidden review-rail self-start overflow-y-auto lg:block print:hidden">
              <SectionNav
                label="Criteria in this kit"
                orientation="column"
                active={active}
                items={navItems}
                onSelect={jump}
              />
            </div>
          </>
        )}
        <div className={cn("flex min-w-0 flex-col gap-6", navItems.length < 2 && "col-span-full")}>
          <QuestionGroups {...groups} recruiter={recruiter} answers={answers} />
        </div>
      </div>
    </>
  );
}

/** Interview kit (Design.md 8.5): questions grouped by criterion. Recruiters edit; interviewers print. */
export function KitPage({ roleId }: { roleId: string }) {
  const { data: session } = useSuspenseQuery(sessionQueryOptions);
  const recruiter = session.user.role === "recruiter";
  const role = useQuery(roleCriteriaQueryOptions(roleId));
  const kit = useQuery(kitQueryOptions(roleId));
  const generate = useGenerateKit(roleId);
  const [jobId, setJobId] = useState<number | null>(null);
  const job = useJobWatch(roleId, jobId);
  const running = jobId !== null && !isJobDone(job.data?.status);

  if (role.isPending || kit.isPending) return <Loading label="Loading the interview kit" />;
  if (role.isError) {
    return (
      <ErrorNotice
        error={role.error}
        retry={() => {
          void role.refetch();
        }}
      />
    );
  }
  if (kit.isError) {
    return (
      <ErrorNotice
        error={kit.error}
        retry={() => {
          void kit.refetch();
        }}
      />
    );
  }

  const criteria = [...role.data.criteria].sort(
    (a, b) =>
      Number(b.kind === "must_have") - Number(a.kind === "must_have") || a.position - b.position,
  );
  const hasQuestions = kit.data.questions.length > 0;
  const draftRole = role.data.status === "draft";
  const start = () => {
    generate.mutate(undefined, { onSuccess: setJobId });
  };
  const blocked = draftRole || running || generate.isPending;

  return (
    <div className="flex flex-col gap-6">
      {recruiter ? (
        <RoleHeader role={role.data} current="kit" pageHasPrimary />
      ) : (
        <PageHeader
          title={`Interview kit: ${role.data.title}`}
          breadcrumb={
            <Link
              to="/me/candidates"
              className="inline-flex min-h-10 items-center gap-1 hover:text-foreground"
            >
              <ChevronLeft aria-hidden="true" className="size-4" />
              Back to My candidates
            </Link>
          }
          action={
            <Button
              type="button"
              variant="ghost"
              className="h-10 px-4 text-muted-foreground"
              onClick={() => {
                window.print();
              }}
            >
              <Printer aria-hidden="true" />
              Print interview kit
            </Button>
          }
        />
      )}
      {draftRole && <Notice>Approve the criteria to start generating the interview kit.</Notice>}
      {kit.data.stale && (
        <Notice tone="warning">
          This interview kit was generated for older criteria. Regenerate it to match the current
          ones.
        </Notice>
      )}
      {running && <Loading label="Generating, this can take a minute" />}
      {job.data && isJobDone(job.data.status) && job.data.status !== "succeeded" && (
        <Notice tone="danger">
          Generating the interview kit{" "}
          {job.data.status === "cancelled" ? "was cancelled" : "did not finish"}. Try again.
        </Notice>
      )}
      {generate.error && <ErrorNotice error={generate.error} />}
      {!hasQuestions && (
        <EmptyState
          message={
            recruiter
              ? "No interview kit yet. Generate it to see questions."
              : "The interview kit is not ready yet."
          }
          action={
            recruiter && (
              <>
                <p className="max-w-prose text-sm text-muted-foreground">
                  Writes interview questions for each criterion, each with a strong and a weak
                  answer as guidance for the interviewer.
                </p>
                <Button type="button" className="h-10 px-4" disabled={blocked} onClick={start}>
                  <Sparkles aria-hidden="true" />
                  Generate interview kit
                </Button>
              </>
            )
          }
        />
      )}
      {hasQuestions && (
        <KitContent
          navItems={kitNavItems(criteria, kit.data.questions)}
          roleId={roleId}
          criteria={criteria}
          questions={kit.data.questions}
          recruiter={recruiter}
          onJob={setJobId}
          actions={recruiter && <RegenerateButton disabled={blocked} onConfirm={start} />}
        />
      )}
    </div>
  );
}
