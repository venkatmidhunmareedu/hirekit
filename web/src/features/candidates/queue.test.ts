import { describe, expect, it } from "vitest";

import { type MyCandidate } from "./api";
import { nextAfter, queueProgress } from "./queue";

const c = (n: number, has_submitted: boolean): MyCandidate => ({
  candidate_id: `c${n}`,
  candidate_no: n,
  role_id: "r",
  role_title: "Backend",
  has_submitted,
});

describe("queueProgress", () => {
  it("counts submitted and picks the first unsubmitted as next", () => {
    expect(queueProgress([c(1, true), c(2, false), c(3, false)])).toEqual({
      total: 3,
      submitted: 1,
      next: c(2, false),
    });
  });

  it("has no next when all are submitted or none are assigned", () => {
    expect(queueProgress([c(1, true)]).next).toBeUndefined();
    expect(queueProgress([])).toEqual({ total: 0, submitted: 0, next: undefined });
  });
});

describe("nextAfter", () => {
  it("skips the current candidate and submitted ones", () => {
    const list = [c(1, false), c(2, true), c(3, false)];
    expect(nextAfter(list, "c1")?.candidate_id).toBe("c3");
    expect(nextAfter(list, "c3")?.candidate_id).toBe("c1");
  });

  it("is undefined when nothing else is left", () => {
    expect(nextAfter([c(1, false)], "c1")).toBeUndefined();
  });
});
