import { describe, expect, it } from "vitest";

import { nextUp } from "./nextUp";

describe("nextUp", () => {
  it("asks for criteria on a draft role that has none", () => {
    expect(nextUp({ status: "draft", criteria: 0 })).toEqual({
      label: "Propose criteria",
      step: "criteria",
      kind: "action",
    });
  });

  it("asks for approval on a draft role with criteria, or with an unknown count", () => {
    expect(nextUp({ status: "draft", criteria: 4 }).label).toBe("Approve criteria");
    expect(nextUp({ status: "draft" }).label).toBe("Approve criteria");
  });

  it("asks for resumes on an approved role with no candidates", () => {
    expect(nextUp({ status: "approved", criteria: 3, candidates: 0, processing: 0 })).toEqual({
      label: "Upload resumes",
      step: "candidates",
      kind: "action",
    });
  });

  it("reports processing as a status, not an action", () => {
    expect(nextUp({ status: "approved", candidates: 5, processing: 2 })).toEqual({
      label: "Processing 2 resumes",
      step: "candidates",
      kind: "status",
    });
    expect(nextUp({ status: "approved", candidates: 1, processing: 1 }).label).toBe(
      "Processing 1 resume",
    );
  });

  it("sends the recruiter to review once candidates are scored", () => {
    expect(nextUp({ status: "approved", candidates: 5, processing: 0 })).toEqual({
      label: "Review candidates",
      step: "candidates",
      kind: "action",
    });
  });

  it("opens the candidates when counts are unknown (role list)", () => {
    expect(nextUp({ status: "approved" })).toEqual({
      label: "Open candidates",
      step: "candidates",
      kind: "action",
    });
  });
});
