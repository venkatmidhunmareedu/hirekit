import { describe, expect, it } from "vitest";

import type { CompareCell } from "./api";
import { highestCounts, markersFor } from "./highlights";

const cell = (criterion_id: string, model: number | null, override: number | null = null) =>
  ({
    criterion_id,
    model_score: model,
    override_score: override,
    feedback: [],
    disagreement: false,
  }) satisfies CompareCell;

const cands = [
  { candidate_id: "a", candidate_no: 1, cells: [cell("x", 3), cell("y", 2), cell("z", null)] },
  { candidate_id: "b", candidate_no: 2, cells: [cell("x", 2, 4), cell("y", 2), cell("z", 3)] },
  { candidate_id: "c", candidate_no: 3, cells: [cell("x", 3), cell("y", 1), cell("z", null)] },
];

describe("markersFor", () => {
  it("uses the recruiter's changed score over the AI score", () => {
    expect(markersFor(cands, "x")).toEqual({ a: "none", b: "highest", c: "none" });
  });

  it("marks every candidate sharing the top score as tied", () => {
    expect(markersFor(cands, "y")).toEqual({ a: "tied", b: "tied", c: "none" });
  });

  it("marks nothing when fewer than two candidates have a score", () => {
    expect(markersFor(cands, "z")).toEqual({ a: "none", b: "none", c: "none" });
  });
});

describe("highestCounts", () => {
  it("counts only sole highs, so a tie counts for nobody", () => {
    expect(highestCounts(cands, ["x", "y", "z"])).toEqual({ a: 0, b: 1, c: 0 });
  });
});
