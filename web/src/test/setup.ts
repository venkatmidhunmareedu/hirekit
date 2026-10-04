import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom has no layout; the router calls scrollTo on navigation.
Object.defineProperty(window, "scrollTo", { value: () => undefined, writable: true });

afterEach(() => {
  cleanup();
});
