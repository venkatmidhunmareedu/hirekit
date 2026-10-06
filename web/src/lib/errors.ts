import { ApiError } from "./api";

const BY_CODE: Record<string, string> = {
  unauthenticated: "Your session has ended. Sign in again.",
  forbidden: "Your role cannot do this.",
  not_found: "This record is missing or you cannot see it.",
  role_not_approved: "The role is still a draft. Approve its criteria first.",
  scores_stale: "These scores belong to older criteria. Re-run scoring first.",
  same_stage: "The candidate is already in that stage.",
  feedback_locked: "This feedback is already submitted and locked.",
  job_already_open: "A job for this is already running. Wait for it to finish.",
  budget_reached: "The model budget has been reached. No new model calls can be made.",
  incomplete_feedback: "Every criterion needs a score and a comment.",
  validation_error: "Some of what you entered is not valid. Check it and try again.",
};

/** Plain-language copy for a failed call (Design.md section 10: what happened, what next). */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return "Could not reach the server. Check your connection and try again.";
    }
    const known = BY_CODE[error.code];
    if (known) return known;
  }
  return "Something went wrong. Try again in a moment.";
}
