import { describe, expect, it } from "vitest";

import { highlightsFor, splitAtQuote } from "../features/candidates/components/SidePanels";

import { ApiError } from "./api";
import { errorMessage } from "./errors";
import { Reader } from "./parse";

describe("Reader", () => {
  it("reads typed fields and treats absent optionals as null", () => {
    const r = new Reader({ a: "x", n: 2, b: true, l: [{ k: "v" }] }, "thing");

    expect(r.str("a")).toBe("x");
    expect(r.num("n")).toBe(2);
    expect(r.bool("b")).toBe(true);
    expect(r.optStr("missing")).toBeNull();
    expect(r.optNum("missing")).toBeNull();
    expect(r.optBool("missing")).toBe(false);
    expect(r.optOneOf("missing", ["q"])).toBeNull();
    expect(r.list("l", (i) => i.str("k"))).toEqual(["v"]);
    expect(r.list("missing", (i) => i.str("k"))).toEqual([]);
  });

  it("throws bad_response on a wrong type, a bad enum or a non-object", () => {
    const r = new Reader({ a: 1, e: "z", l: 3 }, "thing");

    expect(() => r.str("a")).toThrow(ApiError);
    expect(() => r.oneOf("e", ["q"])).toThrow(ApiError);
    expect(() => r.list("l", (i) => i)).toThrow(ApiError);
    expect(() => r.optStr("a")).toThrow(ApiError);
    expect(() => r.optNum("e")).toThrow(ApiError);
    expect(() => r.optBool("a")).toThrow(ApiError);
    expect(() => r.num("e")).toThrow(ApiError);
    expect(() => r.bool("a")).toThrow(ApiError);
    expect(() => new Reader([], "thing")).toThrow(ApiError);
  });
});

describe("errorMessage", () => {
  it("maps known codes, network failures and the rest", () => {
    expect(errorMessage(new ApiError(409, "same_stage", "x"))).toContain(
      "already in that hiring stage",
    );
    expect(errorMessage(new ApiError(0, "network", "x"))).toContain("Could not reach");
    expect(errorMessage(new ApiError(500, "internal", "x"))).toContain("Something went wrong");
    expect(errorMessage(new Error("x"))).toContain("Something went wrong");
  });
});

describe("splitAtQuote", () => {
  it("matches across whitespace differences only", () => {
    expect(splitAtQuote("a  led\n a team z", "led a team")).toEqual(["a  ", "led\n a team", " z"]);
    expect(splitAtQuote("a led the team", "led a team")).toBeNull();
    expect(splitAtQuote("text", null)).toBeNull();
    expect(splitAtQuote("a (b) c", "(b)")).toEqual(["a ", "(b)", " c"]);
  });
});

describe("highlightsFor", () => {
  it("finds every quote, merges equal spans and drops partial overlaps", () => {
    const text = "alpha beta gamma delta";
    expect(
      highlightsFor(text, [
        { id: "a", quote: "beta  gamma" },
        { id: "b", quote: "beta gamma" },
        { id: "c", quote: "gamma delta" },
        { id: "d", quote: "missing" },
        { id: "e", quote: "alpha" },
      ]),
    ).toEqual([
      { start: 0, end: 5, ids: ["e"] },
      { start: 6, end: 16, ids: ["a", "b"] },
    ]);
  });
});
