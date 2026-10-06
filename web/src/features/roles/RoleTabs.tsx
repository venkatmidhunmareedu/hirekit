import { Link } from "@tanstack/react-router";
import { Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type Step = "criteria" | "candidates" | "kit";

/**
 * Role workflow as a numbered stepper. A step is done, current or locked; a locked step is
 * plain text with the reason beside it. Compare needs a selection, so it is never a link here.
 */
export function RoleTabs({
  roleId,
  status,
  current,
}: {
  roleId: string;
  status: "draft" | "approved";
  current: Step;
}) {
  const approved = status === "approved";
  const locked = approved ? null : "Locked until criteria are approved";
  const steps = [
    { id: "criteria", label: "Criteria", done: approved, lock: null },
    { id: "candidates", label: "Candidates", done: false, lock: locked },
    { id: "kit", label: "Interview kit", done: false, lock: locked },
    {
      id: "compare",
      label: "Compare",
      done: false,
      lock: "Tick 2 to 4 candidates on the Candidates step",
    },
  ] as const;

  return (
    <nav aria-label="Role">
      <ol className="flex flex-wrap items-start gap-x-2 gap-y-1 border-b pb-3">
        {steps.map((step, index) => {
          const isCurrent = step.id === current;
          const done = !step.lock && step.done;
          const number = (
            <Badge
              variant={isCurrent && !step.lock ? "default" : "outline"}
              className="size-5 justify-center rounded-full p-0 font-mono"
            >
              {done ? <Check aria-hidden="true" /> : index + 1}
            </Badge>
          );
          return (
            <li key={step.id} className="flex flex-col">
              {step.lock ? (
                <>
                  <span
                    aria-disabled="true"
                    className="flex h-9 cursor-not-allowed items-center gap-2 px-2.5 text-sm font-medium text-muted-foreground"
                  >
                    {number} {step.label}
                  </span>
                  <small className="px-2.5 text-xs text-muted-foreground">{step.lock}</small>
                </>
              ) : (
                <Button
                  asChild
                  variant={isCurrent ? "secondary" : "ghost"}
                  className="h-9 gap-2 px-2.5"
                >
                  <Link
                    to={
                      step.id === "criteria"
                        ? "/roles/$roleId"
                        : step.id === "candidates"
                          ? "/roles/$roleId/candidates"
                          : "/roles/$roleId/kit"
                    }
                    params={{ roleId }}
                    aria-current={isCurrent ? "step" : undefined}
                  >
                    {number} {step.label}
                    {done && <span className="sr-only"> (done)</span>}
                  </Link>
                </Button>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
