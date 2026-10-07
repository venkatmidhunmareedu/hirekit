import { type RoleCriterion } from "../kit/api";

type Named = Pick<RoleCriterion, "id" | "name" | "kind">;

/** The interviewer's local draft: nothing is saved until the one submit. */
export interface Draft {
  scores: Record<string, number>;
  comments: Record<string, string>;
}

export type Missing = "score" | "comment" | "score and comment";

export interface SummaryRow {
  id: string;
  name: string;
  score: number | undefined;
  preview: string;
  missing: Missing | null;
}

const PREVIEW_MAX = 80;

/** Steps 0 to n-1 are criteria; step n is "Review and submit". */
export const nextStep = (step: number, n: number) => Math.min(step + 1, n);
export const prevStep = (step: number) => Math.max(step - 1, 0);

/** The API needs both a score and a comment for every criterion (incomplete_feedback). */
export const isComplete = (d: Draft, id: string) =>
  d.scores[id] !== undefined && (d.comments[id] ?? "").trim() !== "";

export const missingCount = (criteria: Named[], d: Draft) =>
  criteria.filter((c) => !isComplete(d, c.id)).length;

/** Index of the first incomplete criterion, or -1 when every one is done. */
export const firstIncomplete = (criteria: Named[], d: Draft) =>
  criteria.findIndex((c) => !isComplete(d, c.id));

/** Where to open: the first incomplete criterion, else the review step. */
export function startStep(criteria: Named[], d: Draft): number {
  const at = firstIncomplete(criteria, d);
  return at === -1 ? criteria.length : at;
}

function preview(comment: string): string {
  const line = comment.trim().split("\n")[0] ?? "";
  return line.length > PREVIEW_MAX ? `${line.slice(0, PREVIEW_MAX)}...` : line;
}

export function summary(criteria: Named[], d: Draft): SummaryRow[] {
  return criteria.map((c) => {
    const score = d.scores[c.id];
    const hasComment = (d.comments[c.id] ?? "").trim() !== "";
    let missing: Missing | null = null;
    if (score === undefined && !hasComment) missing = "score and comment";
    else if (score === undefined) missing = "score";
    else if (!hasComment) missing = "comment";
    return { id: c.id, name: c.name, score, preview: preview(d.comments[c.id] ?? ""), missing };
  });
}

/** The polite live-region text when the step changes. */
export function announce(criteria: Named[], step: number): string {
  const c = criteria[step];
  return c ? `Criterion ${step + 1} of ${criteria.length}: ${c.name}` : "Review and submit";
}
