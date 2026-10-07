import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Logo } from "./Logo";

describe("Logo", () => {
  it("names the product once and hides the mark from assistive tech", () => {
    const { container } = render(<Logo />);
    expect(container.textContent).toBe("HireKit");
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("uses the light tile on the inverse variant", () => {
    const { container } = render(<Logo inverse />);
    expect(container.querySelector("rect")).toHaveClass("fill-brand-foreground");
  });

  it("passes classes to the wordmark so the mark can stand alone", () => {
    const { container } = render(<Logo wordmarkClassName="hidden" />);
    expect(container.querySelector("span > span")).toHaveClass("hidden");
  });
});
