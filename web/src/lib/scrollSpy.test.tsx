import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { revealIn, useScrollSpy } from "./scrollSpy";

type Callback = (
  entries: { target: Element; isIntersecting: boolean; boundingClientRect: { top: number } }[],
) => void;
let callback: Callback = () => undefined;
const observed: Element[] = [];
const disconnect = vi.fn();

class FakeObserver {
  constructor(cb: Callback) {
    callback = cb;
  }
  observe(el: Element) {
    observed.push(el);
  }
  unobserve() {
    return undefined;
  }
  disconnect() {
    disconnect();
  }
}

beforeEach(() => {
  observed.length = 0;
  for (const id of ["a", "b", "c"]) {
    const el = document.createElement("section");
    el.id = id;
    document.body.append(el);
  }
  vi.stubGlobal("IntersectionObserver", FakeObserver);
});
afterEach(() => {
  document.body.replaceChildren();
  vi.unstubAllGlobals();
});

const see = (id: string, isIntersecting: boolean, top = 0) => {
  const target = document.getElementById(id);
  if (!target) throw new Error(id);
  act(() => {
    callback([{ target, isIntersecting, boundingClientRect: { top } }]);
  });
};

describe("useScrollSpy", () => {
  it("starts on the first id and observes every section", () => {
    const { result } = renderHook(() => useScrollSpy(["a", "b", "c"]));
    expect(result.current[0]).toBe("a");
    expect(observed.map((e) => e.id)).toEqual(["a", "b", "c"]);
  });

  it("follows the first section in view, in list order", () => {
    const { result } = renderHook(() => useScrollSpy(["a", "b", "c"]));
    see("b", true);
    expect(result.current[0]).toBe("b");
    see("c", true);
    expect(result.current[0]).toBe("b");
    see("b", false);
    expect(result.current[0]).toBe("c");
  });

  it("keeps the last active id when nothing is in view and lets a click set it", () => {
    const { result } = renderHook(() => useScrollSpy(["a", "b"]));
    see("b", true);
    see("b", false);
    expect(result.current[0]).toBe("b");
    act(() => {
      result.current[1]("a");
    });
    expect(result.current[0]).toBe("a");
  });

  it("goes back to the first section when scrolled above all of them", () => {
    const { result } = renderHook(() => useScrollSpy(["a", "b"]));
    see("b", true);
    see("b", false, 500);
    expect(result.current[0]).toBe("b");
    see("a", true);
    see("a", false, 500);
    expect(result.current[0]).toBe("a");
  });

  it("ignores the sections passed on the way to a clicked one", () => {
    const { result } = renderHook(() => useScrollSpy(["a", "b", "c"]));
    act(() => {
      result.current[1]("c");
    });
    see("a", true);
    see("a", false);
    see("b", true);
    expect(result.current[0]).toBe("c");
  });

  it("disconnects on unmount", () => {
    const { unmount } = renderHook(() => useScrollSpy(["a"]));
    unmount();
    expect(disconnect).toHaveBeenCalled();
  });
});

describe("revealIn", () => {
  it("scrolls the region so the target sits in the middle, without moving the page", () => {
    const region = document.createElement("div");
    const target = document.createElement("mark");
    region.append(target);
    document.body.append(region);
    const scrollTo = vi.fn();
    region.scrollTo = scrollTo;
    Object.defineProperty(region, "clientHeight", { value: 200 });
    region.getBoundingClientRect = () => new DOMRect(0, 100, 300, 200);
    target.getBoundingClientRect = () => new DOMRect(0, 600, 100, 20);
    revealIn(region, target);
    expect(scrollTo).toHaveBeenCalledWith({ top: 410, behavior: "smooth" });
  });
});
