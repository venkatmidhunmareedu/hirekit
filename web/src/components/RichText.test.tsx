import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { Markdown, MarkdownEditor } from "@/components/RichText";

function Harness({ initial = "" }: { initial?: string }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <MarkdownEditor id="jd" label="Job description" value={initial} onChange={setValue} />
      <output data-testid="md">{value}</output>
    </>
  );
}

function paste(target: HTMLElement, text: string) {
  const event = new Event("paste", { bubbles: true, cancelable: true });
  Object.defineProperty(event, "clipboardData", {
    value: { getData: (type: string) => (type === "text/plain" ? text : "") },
  });
  target.dispatchEvent(event);
}

describe("MarkdownEditor", () => {
  it("is empty as an empty string and reports typed text as markdown", async () => {
    render(<Harness />);
    const box = await screen.findByRole("textbox", { name: "Job description" });
    expect(screen.getByTestId("md")).toHaveTextContent("");
    await userEvent.click(box);
    await userEvent.keyboard("Build things");
    expect(screen.getByTestId("md")).toHaveTextContent("Build things");
  });

  it("toggles formatting from the toolbar with aria-pressed", async () => {
    render(<Harness />);
    const box = await screen.findByRole("textbox", { name: "Job description" });
    await userEvent.click(box);
    const bullets = screen.getByRole("button", { name: "Bulleted list" });
    expect(bullets).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(bullets);
    await userEvent.keyboard("one");
    expect(bullets).toHaveAttribute("aria-pressed", "true");
    expect(box.querySelectorAll("ul > li")).toHaveLength(1);
    await userEvent.click(bullets);
    expect(bullets).toHaveAttribute("aria-pressed", "false");
  });

  it("turns pasted plain text bullets and headings into real blocks", async () => {
    render(<Harness />);
    const box = await screen.findByRole("textbox", { name: "Job description" });
    await userEvent.click(box);
    paste(box, "## Duties\n\n- Build APIs\n- Review code");
    expect(box.querySelector("h2")).toHaveTextContent("Duties");
    expect(box.querySelectorAll("li")).toHaveLength(2);
    await waitFor(() => {
      expect(screen.getByTestId("md").textContent).toBe("## Duties\n\n- Build APIs\n- Review code");
    });
  });
});

describe("Markdown", () => {
  it("renders headings and bullets, and never raw HTML", async () => {
    const { container } = render(
      <Markdown value={"## Duties\n\n- Build APIs\n\n<img src=x onerror=alert(1)>"} />,
    );
    expect(await screen.findByRole("heading", { name: "Duties" })).toBeInTheDocument();
    expect(screen.getByText("Build APIs").closest("li")).not.toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });
});
