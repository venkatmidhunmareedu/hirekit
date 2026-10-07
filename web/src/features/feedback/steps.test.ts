import { describe, expect, it } from "vitest";

import {
  type Draft,
  announce,
  firstIncomplete,
  isComplete,
  missingCount,
  nextStep,
  prevStep,
  startStep,
  summary,
} from "./steps";

const criteria = [
  { id: "a", name: "Backend", kind: "must_have" as const },
  { id: "b", name: "Testing", kind: "must_have" as const },
  { id: "c", name: "Mentoring", kind: "nice_to_have" as const },
];
const draft = (scores: Record<string, number>, comments: Record<string, string>): Draft => ({
  scores,
  comments,
});

describe("feedback steps", () => {
  it("moves forward to the review step and stops there", () => {
    expect(nextStep(0, 3)).toBe(1);
    expect(nextStep(2, 3)).toBe(3);
    expect(nextStep(3, 3)).toBe(3);
  });

  it("moves back and stops at the first criterion", () => {
    expect(prevStep(2)).toBe(1);
    expect(prevStep(0)).toBe(0);
  });

  it("counts a criterion as complete only with a score and a non-blank comment", () => {
    const d = draft({ a: 0, b: 2 }, { a: "ok", b: "  " });

    expect(isComplete(d, "a")).toBe(true);
    expect(isComplete(d, "b")).toBe(false);
    expect(isComplete(d, "c")).toBe(false);
    expect(missingCount(criteria, d)).toBe(2);
  });

  it("finds the first incomplete criterion, or the review step when all are done", () => {
    const some = draft({ a: 1 }, { a: "x" });
    const all = draft({ a: 1, b: 1, c: 1 }, { a: "x", b: "x", c: "x" });

    expect(firstIncomplete(criteria, some)).toBe(1);
    expect(firstIncomplete(criteria, all)).toBe(-1);
    expect(startStep(criteria, some)).toBe(1);
    expect(startStep(criteria, all)).toBe(3);
  });

  it("summarises each criterion with its score, a one-line preview and what is missing", () => {
    const long = `First line\nsecond ${"x".repeat(200)}`;
    const rows = summary(criteria, draft({ a: 3, b: 2 }, { a: long, c: "nice" }));

    expect(rows[0]).toMatchObject({ id: "a", score: 3, missing: null });
    expect(rows[0]?.preview).toBe("First line");
    expect(rows[1]).toMatchObject({ id: "b", score: 2, preview: "", missing: "comment" });
    expect(rows[2]).toMatchObject({ id: "c", score: undefined, missing: "score" });
    expect(summary(criteria, draft({}, {}))[0]?.missing).toBe("score and comment");
  });

  it("truncates a long first line", () => {
    const rows = summary(criteria, draft({ a: 1 }, { a: "y".repeat(200) }));

    expect(rows[0]?.preview.length).toBeLessThanOrEqual(90);
    expect(rows[0]?.preview.endsWith("...")).toBe(true);
  });

  it("announces a criterion by position and name, and the review step", () => {
    expect(announce(criteria, 1)).toBe("Criterion 2 of 3: Testing");
    expect(announce(criteria, 3)).toBe("Review and submit");
  });
});
