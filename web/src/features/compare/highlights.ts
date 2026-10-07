import type { CompareCell, Comparison } from "./api";

export type Marker = "highest" | "tied" | "none";

type Candidates = Comparison["candidates"];

/** The score a recruiter sees on a cell: their change if there is one, else the AI suggestion. */
export function shownScore(cell: CompareCell | undefined): number | null {
  return cell ? (cell.override_score ?? cell.model_score) : null;
}

/**
 * Highest and tied markers for one criterion. This describes the scores only, never the people:
 * it needs two or more scored candidates, and a shared top score is Tied, not Highest.
 */
export function markersFor(candidates: Candidates, criterionId: string): Record<string, Marker> {
  const scores = candidates.map((c) => ({
    id: c.candidate_id,
    score: shownScore(c.cells.find((x) => x.criterion_id === criterionId)),
  }));
  const scored = scores.filter((s): s is { id: string; score: number } => s.score !== null);
  const top = Math.max(...scored.map((s) => s.score));
  const winners = scored.filter((s) => s.score === top);
  const kind: Marker = winners.length > 1 ? "tied" : "highest";
  return Object.fromEntries(
    scores.map((s): [string, Marker] => [
      s.id,
      scored.length >= 2 && s.score === top ? kind : "none",
    ]),
  );
}

/** Per candidate, on how many criteria they alone have the highest score. */
export function highestCounts(
  candidates: Candidates,
  criterionIds: string[],
): Record<string, number> {
  const counts = Object.fromEntries(candidates.map((c) => [c.candidate_id, 0]));
  for (const id of criterionIds) {
    for (const [cand, marker] of Object.entries(markersFor(candidates, id))) {
      if (marker === "highest") counts[cand] = (counts[cand] ?? 0) + 1;
    }
  }
  return counts;
}
