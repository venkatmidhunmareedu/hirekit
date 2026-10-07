import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SectionNav } from "./SectionNav";

const items = [
  { id: "a", label: "Backend", count: 2, meta: "Must-have" },
  { id: "b", label: "Testing", count: 1, meta: "Nice-to-have" },
];

describe("SectionNav, column", () => {
  it("stacks entries without a horizontal scroller and shows the marker text", () => {
    render(
      <SectionNav
        label="Criteria"
        items={items}
        active="a"
        onSelect={vi.fn()}
        orientation="column"
      />,
    );

    const list = screen.getByRole("list");
    expect(list.className).toContain("flex-col");
    expect(list.className).not.toContain("overflow-x");
    expect(screen.getByText("Must-have")).toBeInTheDocument();
    expect(screen.getByText("Nice-to-have")).toBeInTheDocument();
  });

  it("marks the active entry with aria-current and reports a click", async () => {
    const onSelect = vi.fn();
    render(
      <SectionNav
        label="Criteria"
        items={items}
        active="a"
        onSelect={onSelect}
        orientation="column"
      />,
    );

    const first = screen.getByRole("button", { name: /Backend/ });
    const second = screen.getByRole("button", { name: /Testing/ });
    expect(first).toHaveAttribute("aria-current", "true");
    expect(second).not.toHaveAttribute("aria-current");
    await userEvent.click(second);
    expect(onSelect).toHaveBeenCalledWith("b");
  });
});
