import { afterEach, describe, expect, it, vi } from "vitest";

import { applyTheme, readTheme } from "./theme";

afterEach(() => {
  vi.restoreAllMocks();
  document.documentElement.removeAttribute("data-theme");
  localStorage.clear();
});

describe("theme", () => {
  it("sets data-theme, persists it and clears both for system", () => {
    applyTheme("dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(readTheme()).toBe("dark");
    applyTheme("system");
    expect(document.documentElement).not.toHaveAttribute("data-theme");
    expect(readTheme()).toBe("system");
  });

  it("still applies and reads when storage throws", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => {
      applyTheme("light");
    }).not.toThrow();
    expect(document.documentElement).toHaveAttribute("data-theme", "light");
    expect(readTheme()).toBe("system");
  });
});
