import { describe, expect, it } from "vitest";

import { isTypingTarget, step, trayState } from "./selection";

describe("step", () => {
  const ids = ["a", "b", "c"];
  it("moves to the neighbour and stops at both ends", () => {
    expect(step(ids, "a", 1)).toBe("b");
    expect(step(ids, "c", 1)).toBe("c");
    expect(step(ids, "a", -1)).toBe("a");
    expect(step(ids, "c", -1)).toBe("b");
  });
  it("starts at the first when nothing, or something off the page, is selected", () => {
    expect(step(ids, null, 1)).toBe("a");
    expect(step(ids, "zzz", -1)).toBe("a");
  });
  it("has no answer for an empty list", () => {
    expect(step([], null, 1)).toBeNull();
  });
});

describe("isTypingTarget", () => {
  it("is true inside fields and dialogs only", () => {
    const input = document.createElement("input");
    const dialog = document.createElement("div");
    dialog.setAttribute("role", "dialog");
    const inner = document.createElement("button");
    dialog.append(inner);
    expect(isTypingTarget(input)).toBe(true);
    expect(isTypingTarget(inner)).toBe(true);
    expect(isTypingTarget(document.createElement("button"))).toBe(false);
    expect(isTypingTarget(document)).toBe(false);
  });
});

describe("trayState", () => {
  it("allows compare for two to four", () => {
    expect([1, 2, 4, 5].map((n) => trayState(n).canCompare)).toEqual([false, true, true, false]);
  });
  it("says what to do at the edges", () => {
    expect(trayState(1).hint).toMatch(/at least one more/);
    expect(trayState(6).hint).toMatch(/Untick 2/);
  });
});
