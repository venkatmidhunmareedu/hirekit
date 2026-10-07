import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  Briefcase,
  CircleAlert,
  Eye,
  FileClock,
  Hourglass,
  Info,
  Pencil,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useState, type ReactNode } from "react";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { PageHeader } from "../../components/PageHeader";
import { StatusTag } from "../../components/StatusTag";
import { PAGE_SIZE } from "../candidates/api";
import { STAGE_LABEL } from "../candidates/labels";
import { budgetQueryOptions } from "../cost/hooks";
import { RoleAction } from "../roles/RolesPage";

import { GrowBar, Histogram, StageBars } from "./Charts";
import { usePortfolio } from "./hooks";
import { binTotals, budgetPercent, rolesByStatus, stageCounts, sumSummaries } from "./shape";

const BIN_COUNT = 6;

function Tile({
  icon: Icon,
  value,
  label,
  hint,
}: {
  icon: LucideIcon;
  value: ReactNode;
  label: string;
  hint?: string;
}) {
  return (
    <motion.div
      variants={{ hidden: { opacity: 0, y: 8 }, show: { opacity: 1, y: 0 } }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="flex flex-col gap-1 rounded-lg border bg-card p-4"
    >
      <Icon aria-hidden="true" className="size-4 text-muted-foreground" />
      <p className="font-display text-3xl leading-none font-medium tabular-nums">{value}</p>
      <p className="text-sm font-medium">{label}</p>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </motion.div>
  );
}

function Panel({
  id,
  title,
  note,
  children,
}: {
  id: string;
  title: string;
  note?: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4 rounded-lg border bg-card p-5">
      <div className="flex flex-col gap-1">
        <h2 id={id}>{title}</h2>
        {note && <p className="text-xs text-muted-foreground">{note}</p>}
      </div>
      {children}
    </section>
  );
}

function BudgetBody({ spent, limit, allowed }: { spent: number; limit: number; allowed: boolean }) {
  const percent = budgetPercent(spent, limit);
  const reached = !allowed || spent >= limit;
  const warn = !reached && spent >= limit * 0.75;
  return (
    <div className="flex flex-col gap-2">
      <p className="flex flex-wrap items-baseline gap-x-2">
        <span className="font-mono text-2xl tabular-nums">USD {spent.toFixed(2)}</span>
        <span className="text-sm text-muted-foreground">
          of {limit.toFixed(2)} ({percent}%)
        </span>
      </p>
      <GrowBar percent={percent} label="Budget used" />
      {(reached || warn) && (
        <p
          className={
            reached
              ? "flex items-center gap-1.5 text-sm text-bad"
              : "flex items-center gap-1.5 text-sm text-warn"
          }
        >
          <CircleAlert aria-hidden="true" className="size-4" />
          {reached ? "Budget reached. Model actions are paused." : "Nearly used."}
        </p>
      )}
    </div>
  );
}

function BudgetPanel() {
  const budget = useQuery(budgetQueryOptions);
  return (
    <Panel
      id="budget"
      title="Model budget"
      note="Spend on model calls against the limit set for this install."
    >
      {budget.isPending && <Skeleton className="h-12 w-full" />}
      {budget.isError && (
        <ErrorNotice
          error={budget.error}
          retry={() => {
            void budget.refetch();
          }}
        />
      )}
      {budget.data && (
        <BudgetBody
          spent={budget.data.spent_usd}
          limit={budget.data.limit_usd}
          allowed={budget.data.model_actions_allowed}
        />
      )}
    </Panel>
  );
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true">
      <PageHeader title="Dashboard" />
      <p role="status" className="sr-only">
        Loading the dashboard
      </p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Skeleton className="h-64 lg:col-span-2" />
        <Skeleton className="h-64" />
      </div>
    </div>
  );
}

/** The recruiter's overview: counts, spend, each role's next step, and how candidates are spread. */
export function RecruiterDashboard() {
  const { roles, entries, retry } = usePortfolio();
  const reduce = useReducedMotion();
  const [picked, setPicked] = useState<string | null>(null);

  if (roles.isPending) return <DashboardSkeleton />;
  if (roles.isError) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title="Dashboard" />
        <ErrorNotice error={roles.error} retry={retry} />
      </div>
    );
  }

  const status = rolesByStatus(roles.data);
  const total = sumSummaries(entries.flatMap((e) => (e.summary ? [e.summary] : [])));
  const uploaded = entries.reduce((n, e) => n + (e.page?.total ?? 0), 0);
  const processing = entries.reduce((n, e) => n + (e.processing ?? 0), 0);
  const partial = entries.some((e) => e.page && e.page.total > e.page.data.length);
  const failedCount = entries.filter((e) => e.failed).length;

  // The role the charts describe: the one picked, else the first listed role with candidates.
  const withCandidates = entries.filter((e) => e.page && e.page.total > 0);
  const focus = withCandidates.find((e) => e.role.id === picked) ?? withCandidates[0];
  const focusRows = focus?.page?.data ?? [];
  const scoredTotals = focusRows.filter((r) => r.processing_status === "done").map((r) => r.total);
  const bins = binTotals(scoredTotals, BIN_COUNT);
  const focusTotal = focus?.page?.total ?? 0;
  const scopeNote =
    focusTotal > focusRows.length
      ? `Covers the first ${String(focusRows.length)} of ${String(focusTotal)} candidates (the first page of up to ${String(PAGE_SIZE)}).`
      : `Covers all ${String(focusRows.length)} candidates in this role.`;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Dashboard"
        purpose="Where each role stands and what needs you next. Nothing here rejects or hides a candidate."
      />

      {roles.data.length === 0 ? (
        <EmptyState
          message="No roles yet. Create a role, approve its criteria, then upload resumes to see progress here."
          action={
            <Link
              to="/roles"
              className="text-sm font-medium text-primary underline-offset-4 hover:underline"
            >
              Go to Roles
            </Link>
          }
        />
      ) : (
        <>
          <motion.section
            aria-label="Overview"
            className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6"
            initial={reduce ? false : "hidden"}
            animate="show"
            variants={{ show: { transition: { staggerChildren: 0.04 } } }}
          >
            <Tile
              icon={Briefcase}
              value={roles.data.length}
              label="Roles"
              hint={`${String(status.approved)} approved, ${String(status.draft)} draft`}
            />
            <Tile
              icon={UsersRound}
              value={total.scored}
              label="Candidates scored"
              hint={`of ${String(uploaded)} uploaded`}
            />
            <Tile
              icon={Eye}
              value={total.needLook}
              label="Need a look"
              hint="A score was flagged"
            />
            <Tile
              icon={Pencil}
              value={total.changed}
              label="Changed by recruiter"
              hint="At least one score"
            />
            <Tile
              icon={FileClock}
              value={total.outOfDate}
              label="Out of date"
              hint="Criteria changed since"
            />
            <Tile
              icon={Hourglass}
              value={processing}
              label="Processing now"
              hint="Resumes waiting or running"
            />
          </motion.section>

          {(partial || failedCount > 0) && (
            <p role="status" className="flex items-start gap-2 text-sm text-muted-foreground">
              <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              <span>
                {partial &&
                  `Counts cover the first page of up to ${String(PAGE_SIZE)} candidates for each role. `}
                {failedCount > 0 && (
                  <>
                    {String(failedCount)} {failedCount === 1 ? "role" : "roles"} could not be
                    loaded.{" "}
                    <button
                      type="button"
                      className="font-medium text-primary underline underline-offset-4"
                      onClick={retry}
                    >
                      Try again
                    </button>
                  </>
                )}
              </span>
            </p>
          )}

          <div className="grid items-start gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <Panel
                id="role-progress"
                title="Roles at a glance"
                note="Each role with its progress and the next step."
              >
                <ul className="flex flex-col divide-y">
                  {entries.map((e) => {
                    const scored = e.summary?.scored ?? 0;
                    const count = e.page?.total;
                    return (
                      <li
                        key={e.role.id}
                        className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 first:pt-0 last:pb-0"
                      >
                        <div className="flex min-w-0 flex-1 basis-48 flex-col gap-1.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <Link
                              to="/roles/$roleId"
                              params={{ roleId: e.role.id }}
                              className="font-semibold underline-offset-4 hover:underline"
                            >
                              {e.role.title}
                            </Link>
                            <StatusTag tone={e.role.status === "draft" ? "neutral" : "success"}>
                              {e.role.status === "draft" ? "Draft" : "Approved"}
                            </StatusTag>
                          </div>
                          {e.role.status === "draft" ? (
                            <p className="text-xs text-muted-foreground">
                              Criteria not approved yet
                            </p>
                          ) : e.loading ? (
                            <Skeleton className="h-4 w-40" />
                          ) : e.failed ? (
                            <p className="text-xs text-bad">Could not load candidates</p>
                          ) : (
                            <>
                              <GrowBar
                                percent={count ? Math.round((scored / count) * 100) : 0}
                                label={`${e.role.title} scored`}
                              />
                              <p className="text-xs text-muted-foreground">
                                {count === 0
                                  ? "No resumes uploaded"
                                  : `${String(scored)} of ${String(count ?? 0)} scored${e.summary && e.summary.needLook > 0 ? `, ${String(e.summary.needLook)} need a look` : ""}`}
                              </p>
                            </>
                          )}
                        </div>
                        <RoleAction
                          roleId={e.role.id}
                          status={e.role.status}
                          {...(count !== undefined && { candidates: count })}
                          {...(e.processing !== undefined && { processing: e.processing })}
                        />
                      </li>
                    );
                  })}
                </ul>
              </Panel>
            </div>
            <BudgetPanel />
          </div>

          {focus ? (
            <div className="flex flex-col gap-4">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <h2>Candidates in {focus.role.title}</h2>
                {withCandidates.length > 1 && (
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="focus-role" className="text-xs text-muted-foreground">
                      Role shown
                    </Label>
                    <Select value={focus.role.id} onValueChange={setPicked}>
                      <SelectTrigger id="focus-role" className="h-10 min-w-56">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {withCandidates.map((e) => (
                          <SelectItem key={e.role.id} value={e.role.id}>
                            {e.role.title}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>
              <p className="-mt-2 max-w-prose text-xs text-muted-foreground">{scopeNote}</p>
              <div className="grid gap-6 lg:grid-cols-2">
                <Panel
                  id="stages"
                  title="Where candidates are"
                  note="Count per hiring stage. Only a recruiter moves a candidate."
                >
                  <StageBars
                    counts={stageCounts(focusRows).map((c) => ({
                      label: STAGE_LABEL[c.stage],
                      count: c.count,
                    }))}
                  />
                </Panel>
                <Panel
                  id="totals"
                  title="Spread of weighted totals"
                  note="How many scored candidates fall in each range. Bar color carries no meaning. Totals use recruiter changes where there are any."
                >
                  {bins.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No scored candidates yet.</p>
                  ) : (
                    <Histogram
                      bins={bins}
                      caption={`Weighted totals of ${String(scoredTotals.length)} scored candidates in ${focus.role.title}, in ${String(bins.length)} equal ranges.`}
                    />
                  )}
                </Panel>
              </div>
            </div>
          ) : (
            <EmptyState message="No candidates have been uploaded yet, so there is nothing to chart. Upload resumes to an approved role." />
          )}
        </>
      )}
      <p className="max-w-prose text-xs text-muted-foreground">
        Anonymization removes identity details but is not proof of fairness. Schools, clubs, wording
        and career gaps can remain.
      </p>
    </div>
  );
}
