import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { candidateKeys } from "../hooks";
import { ResumeText } from "./SidePanels";

const TEXT = "Pune\na@b.com\n\nEXPERIENCE\nLed the platform\nteam well.\n\n- Shipped billing";

function show(marks: { id: string; quote: string }[], onMarkClick = vi.fn()) {
  const client = new QueryClient();
  client.setQueryData(candidateKeys.text("c1"), TEXT);
  render(
    <QueryClientProvider client={client}>
      <ResumeText
        candidateId="c1"
        marks={marks}
        activeId="a"
        onMarkClick={onMarkClick}
        stickyFrom="lg"
      />
    </QueryClientProvider>,
  );
  return onMarkClick;
}

describe("ResumeText", () => {
  it("renders headings, paragraphs and list items", () => {
    show([]);
    expect(screen.getByRole("heading", { level: 3, name: "EXPERIENCE" })).toBeInTheDocument();
    expect(screen.getByText("Led the platform team well.")).toBeInTheDocument();
    expect(screen.getByRole("listitem")).toHaveTextContent("Shipped billing");
  });

  it("highlights a quote that wraps a line and one that spans blocks", async () => {
    const click = show([
      { id: "a", quote: "platform team" },
      { id: "b", quote: "team well. Shipped" },
    ]);
    // "team" is shared, so the later partial overlap is dropped; the first still shows.
    const first = screen.getByRole("button", { name: /platform team/ });
    expect(first).toHaveTextContent("platform team");
    await userEvent.click(first);
    expect(click).toHaveBeenCalledWith("a");
  });

  it("highlights each piece of a quote that crosses a block boundary", () => {
    show([{ id: "a", quote: "well. - Shipped" }]);
    const pieces = screen.getAllByRole("button", { name: /Show scoring card/ });
    expect(pieces.map((p) => p.textContent)).toEqual(["well.", "Shipped"]);
    expect(pieces.every((p) => p.getAttribute("data-ids") === "a")).toBe(true);
  });
});
