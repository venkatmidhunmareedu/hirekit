import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import { MotionGlobalConfig } from "motion/react";

// jsdom has no layout; the router calls scrollTo on navigation.
Object.defineProperty(window, "scrollTo", { value: () => undefined, writable: true });

// jsdom lacks what Radix primitives call: pointer capture, scrollIntoView, ResizeObserver.
Element.prototype.hasPointerCapture = () => false;
Element.prototype.setPointerCapture = () => undefined;
Element.prototype.releasePointerCapture = () => undefined;
Element.prototype.scrollIntoView = () => undefined;
Element.prototype.scrollTo = () => undefined;
class ResizeObserverStub {
  observe() {
    return undefined;
  }
  unobserve() {
    return undefined;
  }
  disconnect() {
    return undefined;
  }
}
globalThis.ResizeObserver = ResizeObserverStub;

afterEach(() => {
  cleanup();
});

// jsdom has no matchMedia: every query is false (the narrow layout) unless a test stubs it.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }),
});

// Motion would animate opacity and position in jsdom; jump to the end state so tests never wait on it.
MotionGlobalConfig.skipAnimations = true;

// ProseMirror (the rich text editor) measures text ranges and hit-tests; jsdom has no layout.
const emptyRect = { x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0 };
Range.prototype.getClientRects = () => [] as unknown as DOMRectList;
Range.prototype.getBoundingClientRect = () => ({ ...emptyRect, toJSON: () => emptyRect });
Element.prototype.getClientRects = () => [] as unknown as DOMRectList;
document.elementFromPoint = () => null;
