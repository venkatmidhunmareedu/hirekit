import { type MyCandidate } from "./api";

/** Progress through an interviewer's assigned candidates, and the one to do next. */
export function queueProgress(mine: MyCandidate[]) {
  return {
    total: mine.length,
    submitted: mine.filter((m) => m.has_submitted).length,
    next: mine.find((m) => !m.has_submitted),
  };
}

/** The next unsubmitted candidate other than the one open now. */
export function nextAfter(mine: MyCandidate[], currentId: string): MyCandidate | undefined {
  return mine.find((m) => !m.has_submitted && m.candidate_id !== currentId);
}
