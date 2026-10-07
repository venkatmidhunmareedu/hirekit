import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { ArrowRight, Check, Lock } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { StatusTag } from "../../components/StatusTag";
import { queueQueryOptions, rankedQueryOptions } from "../candidates/hooks";
import { kitQueryOptions } from "../kit/hooks";

import type { RoleDetail } from "./api";
import { nextUp, type RoleStep } from "./nextUp";

interface StepView {
  id: RoleStep | "compare";
  label: string;
  state: string;
  done?: boolean;
  /** Why the step cannot be opened; a locked step is plain text. */
  lock?: string;
}

function StepLink({
  step,
  roleId,
  className,
  children,
}: {
  step: RoleStep;
  roleId: string;
  className?: string;
  children: ReactNode;
}) {
  const props = {
    params: { roleId },
    className,
  } as const;
  if (step === "criteria")
    return (
      <Link to="/roles/$roleId" {...props}>
        {children}
      </Link>
    );
  if (step === "candidates") {
    return (
      <Link to="/roles/$roleId/candidates" {...props}>
        {children}
      </Link>
    );
  }
  return (
    <Link to="/roles/$roleId/kit" {...props}>
      {children}
    </Link>
  );
}

/**
 * The header every role screen shares (Design.md 8.2): title, status, one next-up action and a
 * progress strip. Counts come from the queries the screens already make; one that is not loaded
 * is left out. `pageHasPrimary` is set by a screen with its own primary button, so the next-up
 * link steps down to outline there.
 */
export function RoleHeader({
  role,
  current,
  pageHasPrimary = false,
}: {
  role: Pick<RoleDetail, "id" | "title" | "status"> & { criteria: readonly unknown[] };
  current: RoleStep;
  pageHasPrimary?: boolean;
}) {
  const approved = role.status === "approved";
  const queue = useQuery({ ...queueQueryOptions(role.id), enabled: approved });
  const processing = queue.data ? queue.data.waiting + queue.data.running : undefined;
  const ranked = useQuery({
    ...rankedQueryOptions(role.id, null, 0, (processing ?? 0) > 0),
    enabled: approved,
  });
  const kit = useQuery({ ...kitQueryOptions(role.id), enabled: approved });

  const rows = ranked.data?.data ?? [];
  const total = ranked.data?.total;
  const scored = rows.filter((c) => c.processing_status === "done").length;
  const look = rows.filter((c) => c.scores.some((s) => s.flag_reason !== null)).length;

  const next = nextUp({
    status: role.status,
    criteria: role.criteria.length,
    ...(total !== undefined && { candidates: total }),
    ...(processing !== undefined && { processing }),
  });

  const candidateState = [
    total === 0 ? "None uploaded" : total !== undefined && `${scored} scored`,
    look > 0 && `${look} need a look`,
    processing !== undefined && processing > 0 && `${processing} processing`,
  ]
    .filter((part): part is string => typeof part === "string")
    .join(", ");
  const kitState = kit.data
    ? kit.data.questions.length === 0
      ? "Not generated"
      : kit.data.stale
        ? "Ready, older criteria"
        : "Ready"
    : "";
  const locked = "Approve criteria first";

  const steps: StepView[] = [
    {
      id: "criteria",
      label: "Criteria",
      done: approved,
      state: approved
        ? `Approved, ${role.criteria.length}`
        : role.criteria.length === 0
          ? "None yet"
          : "Needs approval",
    },
    {
      id: "candidates",
      label: "Candidates",
      state: candidateState,
      ...(!approved && { lock: locked }),
    },
    {
      id: "kit",
      label: "Interview kit",
      done: approved && kit.data !== undefined && kit.data.questions.length > 0,
      state: kitState,
      ...(!approved && { lock: locked }),
    },
    { id: "compare", label: "Compare", state: "", lock: "Tick 2 to 4 candidates" },
  ];

  return (
    <header className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <h1>{role.title}</h1>
          <StatusTag tone={approved ? "success" : "neutral"}>
            {approved ? "Approved" : "Draft"}
          </StatusTag>
        </div>
        <div className="print:hidden">
          {next.kind === "status" ? (
            <p role="status" className="text-sm font-medium text-muted-foreground">
              {next.label}
            </p>
          ) : next.step === current ? (
            <p className="text-sm text-muted-foreground">
              Next up: <span className="font-medium text-foreground">{next.label}</span>
            </p>
          ) : (
            <Button asChild variant={pageHasPrimary ? "outline" : "default"} className="h-10 px-4">
              <StepLink step={next.step} roleId={role.id}>
                {next.label}
                <ArrowRight aria-hidden="true" />
              </StepLink>
            </Button>
          )}
        </div>
      </div>
      <nav aria-label="Role progress" className="print:hidden">
        <ol className="grid gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-4">
          {steps.map((step) => {
            const isCurrent = step.id === current;
            const body = (
              <>
                <span className="flex items-center gap-1.5 text-sm font-medium">
                  {step.lock ? (
                    <Lock aria-hidden="true" className="size-3.5" />
                  ) : step.done ? (
                    <Check aria-hidden="true" className="size-3.5 text-ok" />
                  ) : null}
                  {step.label}
                  {step.done && <span className="sr-only"> (done)</span>}
                </span>
                <span className="text-xs text-muted-foreground">
                  {step.lock ?? (step.state || " ")}
                </span>
              </>
            );
            const cell = cn(
              "flex min-h-14 flex-col justify-center gap-0.5 bg-card px-4 py-2",
              isCurrent && "border-t-2 border-primary",
            );
            return (
              <li key={step.id} className="contents">
                {isCurrent ? (
                  <span aria-current="step" className={cell}>
                    {body}
                  </span>
                ) : step.lock || step.id === "compare" ? (
                  <span className={cn(cell, "text-muted-foreground")}>{body}</span>
                ) : (
                  <StepLink
                    step={step.id}
                    roleId={role.id}
                    className={cn(
                      cell,
                      "hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                    )}
                  >
                    {body}
                  </StepLink>
                )}
              </li>
            );
          })}
        </ol>
      </nav>
    </header>
  );
}
