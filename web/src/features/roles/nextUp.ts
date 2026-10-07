export type RoleStep = "criteria" | "candidates" | "kit";

/** What is known about a role. A count that the screen cannot know is left out. */
export interface RoleState {
  status: "draft" | "approved";
  criteria?: number;
  candidates?: number;
  processing?: number;
}

export interface NextUp {
  label: string;
  step: RoleStep;
  /** "status" is information (work in progress), not something the recruiter can do now. */
  kind: "action" | "status";
}

/** The one thing to do next on a role, computed from state alone. */
export function nextUp(state: RoleState): NextUp {
  if (state.status === "draft") {
    return {
      label: state.criteria === 0 ? "Propose criteria" : "Approve criteria",
      step: "criteria",
      kind: "action",
    };
  }
  const processing = state.processing ?? 0;
  if (processing > 0) {
    return {
      label: `Processing ${processing} ${processing === 1 ? "resume" : "resumes"}`,
      step: "candidates",
      kind: "status",
    };
  }
  if (state.candidates === undefined) {
    return { label: "Open candidates", step: "candidates", kind: "action" };
  }
  return {
    label: state.candidates === 0 ? "Upload resumes" : "Review candidates",
    step: "candidates",
    kind: "action",
  };
}
