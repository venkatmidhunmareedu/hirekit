import { STAGES, type RankedCandidate, type Stage } from "../candidates/api";

export interface Bin {
  from: number;
  to: number;
  count: number;
}

/**
 * Equal-width bins from the lowest to the highest total. Totals have no fixed scale (they are
 * score times weight, summed), so the range comes from the data. The maximum lands in the last bin.
 */
export function binTotals(totals: number[], binCount: number): Bin[] {
  if (totals.length === 0) return [];
  const min = Math.min(...totals);
  const max = Math.max(...totals);
  if (min === max) return [{ from: min, to: max, count: totals.length }];
  const width = (max - min) / binCount;
  const counts = Array.from({ length: binCount }, () => 0);
  for (const total of totals) {
    const index = Math.min(binCount - 1, Math.floor((total - min) / width));
    counts[index] = (counts[index] ?? 0) + 1;
  }
  const bins: Bin[] = counts.map((count, i) => ({
    from: min + i * width,
    to: min + (i + 1) * width,
    count,
  }));
  return bins;
}

export function stageCounts(rows: RankedCandidate[]): { stage: Stage; count: number }[] {
  return STAGES.map((stage) => ({ stage, count: rows.filter((r) => r.stage === stage).length }));
}

export interface RoleSummary {
  scored: number;
  needLook: number;
  changed: number;
  outOfDate: number;
}

/** What one loaded page of candidates says about its role. Counts candidates, not scores. */
export function summarizeRows(rows: RankedCandidate[]): RoleSummary {
  return {
    scored: rows.filter((r) => r.processing_status === "done").length,
    needLook: rows.filter((r) => r.scores.some((s) => s.flag_reason !== null)).length,
    changed: rows.filter((r) => r.scores.some((s) => s.source === "recruiter_override")).length,
    outOfDate: rows.filter((r) => r.stale).length,
  };
}

export function sumSummaries(list: RoleSummary[]): RoleSummary {
  return list.reduce<RoleSummary>(
    (sum, s) => ({
      scored: sum.scored + s.scored,
      needLook: sum.needLook + s.needLook,
      changed: sum.changed + s.changed,
      outOfDate: sum.outOfDate + s.outOfDate,
    }),
    { scored: 0, needLook: 0, changed: 0, outOfDate: 0 },
  );
}

export function rolesByStatus(roles: { status: "draft" | "approved" }[]) {
  return {
    draft: roles.filter((r) => r.status === "draft").length,
    approved: roles.filter((r) => r.status === "approved").length,
  };
}

export function budgetPercent(spent: number, limit: number): number {
  if (limit <= 0) return 0;
  return Math.min(100, Math.round((spent / limit) * 100));
}
