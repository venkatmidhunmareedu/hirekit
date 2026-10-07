import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setCsrfToken } from "../../lib/api";
import { CAND, ROLE, candidate, role, scores } from "../../test/fixtures";
import { json, session, stubFetch } from "../../test/fetch";
import { renderApp } from "../../test/renderApp";

const PATH = `/roles/${ROLE}/candidates`;
const idOf = (no: number) => `30000000-0000-4000-8000-00000000000${no}`;

function ranked(no: number) {
  return {
    id: idOf(no),
    candidate_no: no,
    stage: "new",
    processing_status: "done",
    failure_reason: null,
    total: 10 - no,
    must_have_covered: 1,
    must_have_total: 2,
    stale: false,
    duplicate_of_candidate_no: null,
    scores: [],
  };
}

function routes() {
  const table: Record<string, () => Response> = {
    "GET /v1/auth/me": () => json(200, session),
    [`GET /v1/roles/${ROLE}`]: () => json(200, { ...role, status: "approved" }),
    [`GET /v1/roles/${ROLE}/queue`]: () => json(200, { data: [], waiting: 0, running: 0 }),
    [`GET /v1/roles/${ROLE}/candidates?limit=100&offset=0`]: () =>
      json(200, { data: [1, 2, 3].map(ranked), page: { limit: 100, offset: 0, total: 3 } }),
    "GET /v1/users?role=interviewer": () => json(200, { data: [] }),
  };
  for (const no of [1, 2, 3]) {
    const id = idOf(no);
    table[`GET /v1/candidates/${id}`] = () =>
      json(200, { ...candidate, id, candidate_no: no, scores });
    table[`GET /v1/candidates/${id}/text`] = () =>
      json(200, { raw_text: "x", anonymized_text: "Resume text" });
    table[`GET /v1/candidates/${id}/feedback`] = () => json(200, { data: [] });
    table[`GET /v1/candidates/${id}/assignments`] = () => json(200, { data: [] });
  }
  return table;
}

beforeEach(() => {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: true,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
});

afterEach(() => {
  setCsrfToken(null);
});

describe("review mode", () => {
  it("opens the top-ranked candidate when the URL names none", async () => {
    stubFetch(routes());
    renderApp(PATH);

    expect(await screen.findByRole("heading", { name: "Candidate C-001" })).toBeInTheDocument();
    const list = screen.getByRole("list", { name: /ranked by weighted/ });
    expect(within(list).getByRole("button", { name: /C-001/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
  });

  it("opens the candidate in the c search param and keeps it on a click", async () => {
    stubFetch(routes());
    const router = renderApp(`${PATH}?c=${idOf(3)}`);

    expect(await screen.findByRole("heading", { name: "Candidate C-003" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /C-002/ }));

    expect(await screen.findByRole("heading", { name: "Candidate C-002" })).toBeInTheDocument();
    expect(router.state.location.search).toEqual({ c: idOf(2) });
    expect(CAND).toBe(idOf(1));
  });

  it("moves with j and k, stops at the ends and ignores typing in a field", async () => {
    stubFetch(routes());
    renderApp(PATH);
    await screen.findByRole("heading", { name: "Candidate C-001" });

    await userEvent.keyboard("j");
    expect(await screen.findByRole("heading", { name: "Candidate C-002" })).toBeInTheDocument();
    expect(screen.getByText("Showing C-002, 2 of 3")).toBeInTheDocument();
    await userEvent.keyboard("jj");
    expect(await screen.findByRole("heading", { name: "Candidate C-003" })).toBeInTheDocument();
    await userEvent.keyboard("k");
    expect(await screen.findByRole("heading", { name: "Candidate C-002" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("combobox", { name: "Filter by stage" }));
    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("heading", { name: "Candidate C-002" })).toBeInTheDocument();
  });

  it("moves with the Next and Previous buttons and says where it is", async () => {
    stubFetch(routes());
    renderApp(PATH);
    await screen.findByRole("heading", { name: "Candidate C-001" });

    expect(screen.getByRole("button", { name: "Previous candidate" })).toBeDisabled();
    expect(screen.getByText("1 of 3 on this page")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next candidate" }));

    expect(await screen.findByRole("heading", { name: "Candidate C-002" })).toBeInTheDocument();
    expect(screen.getByText("2 of 3 on this page")).toBeInTheDocument();
  });

  it("shows the compare tray from one tick, enables Compare at two and clears", async () => {
    stubFetch(routes());
    renderApp(PATH);
    await screen.findByRole("heading", { name: "Candidate C-001" });
    expect(screen.queryByRole("region", { name: "Compare selection" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("checkbox", { name: "Select C-001 to compare" }));
    const tray = screen.getByRole("region", { name: "Compare selection" });
    expect(within(tray).getByText("1 selected")).toBeInTheDocument();
    expect(within(tray).getByRole("button", { name: "Compare" })).toBeDisabled();
    expect(within(tray).getByText(/at least one more/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("checkbox", { name: "Select C-002 to compare" }));
    expect(within(tray).getByRole("button", { name: "Compare" })).toBeEnabled();
    expect(screen.getByText("2 candidates selected for compare")).toBeInTheDocument();

    await userEvent.click(within(tray).getByRole("button", { name: "Clear" }));
    expect(screen.queryByRole("region", { name: "Compare selection" })).not.toBeInTheDocument();
  });
});
