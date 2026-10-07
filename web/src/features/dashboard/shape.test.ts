import { describe, expect, it } from "vitest";

import { type RankedCandidate, type ScoreCell } from "../candidates/api";

import {
  binTotals,
  budgetPercent,
  rolesByStatus,
  stageCounts,
  summarizeRows,
  sumSummaries,
} from "./shape";

const cell = (patch: Partial<ScoreCell> = {}): ScoreCell => ({
  criterion_id: "c",
  criterion_name: "Backend",
  kind: "must_have",
  status: "scored",
  model_score: 3,
  override_score: null,
  source: "model_suggestion",
  stale: false,
  quote: "q",
  flag_reason: null,
  override_note: null,
  ...patch,
});

const row = (patch: Partial<RankedCandidate> = {}): RankedCandidate => ({
  id: "x",
  candidate_no: 1,
  stage: "new",
  processing_status: "done",
  failure_reason: null,
  total: 5,
  must_have_covered: 1,
  must_have_total: 1,
  stale: false,
  duplicate_of_candidate_no: null,
  scores: [cell()],
  ...patch,
});

describe("binTotals", () => {
  it("returns no bins for no totals", () => {
    expect(binTotals([], 4)).toEqual([]);
  });

  it("makes one bin when every total is equal", () => {
    const bins = binTotals([7, 7, 7], 4);
    expect(bins).toHaveLength(1);
    expect(bins[0]).toMatchObject({ from: 7, to: 7, count: 3 });
  });

  it("splits the range into equal bins and counts the maximum in the last bin", () => {
    const bins = binTotals([0, 1, 5, 9, 10], 5);
    expect(bins.map((b) => b.count)).toEqual([2, 0, 1, 0, 2]);
    expect(bins[0]).toMatchObject({ from: 0, to: 2 });
    expect(bins[4]).toMatchObject({ from: 8, to: 10 });
  });

  it("keeps every total: counts sum to the input length", () => {
    const totals = [3.2, 4.4, 4.5, 8.8, 9.1, 9.9, 12];
    expect(binTotals(totals, 6).reduce((n, b) => n + b.count, 0)).toBe(totals.length);
  });
});

describe("stageCounts", () => {
  it("lists every stage in pipeline order, zero included", () => {
    const counts = stageCounts([
      row({ stage: "new" }),
      row({ stage: "new" }),
      row({ stage: "offer" }),
    ]);
    expect(counts.map((c) => c.stage)).toEqual([
      "new",
      "screened",
      "interview",
      "offer",
      "hired",
      "rejected",
      "withdrawn",
    ]);
    expect(counts.find((c) => c.stage === "new")?.count).toBe(2);
    expect(counts.find((c) => c.stage === "offer")?.count).toBe(1);
    expect(counts.find((c) => c.stage === "hired")?.count).toBe(0);
  });
});

describe("summarizeRows", () => {
  it("counts scored, need a look, changed by recruiter and out of date", () => {
    const summary = summarizeRows([
      row(),
      row({ scores: [cell({ flag_reason: "quote not in text" })] }),
      row({ scores: [cell({ source: "recruiter_override", override_score: 2 })] }),
      row({ stale: true }),
      row({ processing_status: "scoring" }),
    ]);
    expect(summary).toEqual({ scored: 4, needLook: 1, changed: 1, outOfDate: 1 });
  });

  it("counts a candidate once however many scores are flagged", () => {
    const summary = summarizeRows([
      row({ scores: [cell({ flag_reason: "a" }), cell({ flag_reason: "b" })] }),
    ]);
    expect(summary.needLook).toBe(1);
  });
});

describe("sumSummaries", () => {
  it("adds field by field", () => {
    const total = sumSummaries([
      { scored: 2, needLook: 1, changed: 0, outOfDate: 1 },
      { scored: 3, needLook: 0, changed: 2, outOfDate: 0 },
    ]);
    expect(total).toEqual({ scored: 5, needLook: 1, changed: 2, outOfDate: 1 });
  });
});

describe("rolesByStatus", () => {
  it("counts draft and approved roles", () => {
    expect(
      rolesByStatus([{ status: "draft" }, { status: "approved" }, { status: "approved" }]),
    ).toEqual({
      draft: 1,
      approved: 2,
    });
  });
});

describe("budgetPercent", () => {
  it("rounds, clamps to 100 and tolerates a zero limit", () => {
    expect(budgetPercent(5.42, 8)).toBe(68);
    expect(budgetPercent(9, 8)).toBe(100);
    expect(budgetPercent(1, 0)).toBe(0);
  });
});
