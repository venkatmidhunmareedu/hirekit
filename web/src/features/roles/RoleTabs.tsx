import { Link } from "@tanstack/react-router";

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
      <ol className="stepper">
        {steps.map((step, index) => {
          const isCurrent = step.id === current;
          const state = step.lock ? "locked" : step.done ? "done" : isCurrent ? "current" : "open";
          const text = (
            <>
              <span className="step-no">{index + 1}</span> {step.label}
            </>
          );
          return (
            <li key={step.id} className={`step step-${state}`}>
              {step.lock ? (
                <>
                  <span aria-disabled="true">{text}</span>
                  <small className="muted">{step.lock}</small>
                </>
              ) : (
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
                  {text}
                  {state === "done" && <span className="visually-hidden"> (done)</span>}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
