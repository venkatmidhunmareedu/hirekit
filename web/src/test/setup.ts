import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom has no layout; the router calls scrollTo on navigation.
Object.defineProperty(window, "scrollTo", { value: () => undefined, writable: true });

// jsdom lacks what Radix primitives call: pointer capture, scrollIntoView, ResizeObserver.
Element.prototype.hasPointerCapture = () => false;
Element.prototype.setPointerCapture = () => undefined;
Element.prototype.releasePointerCapture = () => undefined;
Element.prototype.scrollIntoView = () => undefined;
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
