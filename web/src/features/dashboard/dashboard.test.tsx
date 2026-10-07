import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { setCsrfToken } from "../../lib/api";
import { INTERVIEWER, ROLE, role } from "../../test/fixtures";
import { json, networkDown, session, stubFetch } from "../../test/fetch";
import { renderApp } from "../../test/renderApp";

afterEach(() => {
  setCsrfToken(null);
});

const row = (n: number, total: number, extra: Record<string, unknown> = {}) => ({
  id: `c${String(n)}`,
  candidate_no: n,
  stage: n === 3 ? "interview" : "new",
  processing_status: "done",
  failure_reason: null,
  total,
  must_have_covered: 1,
  must_have_total: 1,
  stale: false,
  duplicate_of_candidate_no: null,
  scores: [],
  ...extra,
});

const routes = {
  "GET /v1/auth/me": () => json(200, session),
  "GET /v1/roles": () => json(200, { data: [role] }),
  [`GET /v1/roles/${ROLE}/queue`]: () => json(200, { waiting: 0, running: 2 }),
  [`GET /v1/roles/${ROLE}/candidates?limit=100&offset=0`]: () =>
    json(200, {
      data: [row(1, 4), row(2, 8), row(3, 12, { stale: true })],
      page: { limit: 100, offset: 0, total: 3 },
    }),
  "GET /v1/cost-log?limit=1": () =>
    json(200, {
      budget: { spent_usd: "2.00", limit_usd: "8.00", model_actions_allowed: true },
      data: [],
      page: { next_cursor: null, has_more: false },
    }),
};

describe("recruiter dashboard", () => {
  it("shows counts, the budget, stage counts and a histogram with a text alternative", async () => {
    stubFetch(routes);
    renderApp("/");

    const main = within(await screen.findByRole("main"));
    const overview = within(await main.findByRole("region", { name: "Overview" }));
    expect(await overview.findByText("Candidates scored")).toBeInTheDocument();
    expect(overview.getByText("of 3 uploaded")).toBeInTheDocument();
    expect(await main.findByRole("progressbar", { name: "Budget used" })).toHaveAttribute(
      "aria-valuenow",
      "25",
    );
    expect(await main.findByText(/Covers all 3 candidates/)).toBeInTheDocument();
    expect(
      await main.findByRole("table", { name: /Weighted totals of 3 scored/ }),
    ).toBeInTheDocument();
    expect(main.getByText("Interview")).toBeInTheDocument();
  });

  it("says when the first page is all it counted", async () => {
    stubFetch({
      ...routes,
      [`GET /v1/roles/${ROLE}/candidates?limit=100&offset=0`]: () =>
        json(200, { data: [row(1, 4)], page: { limit: 100, offset: 0, total: 250 } }),
    });
    renderApp("/");
    expect(await screen.findByText(/Covers the first 1 of 250 candidates/)).toBeInTheDocument();
  });

  it("offers a retry when the roles cannot be loaded", async () => {
    stubFetch({ ...routes, "GET /v1/roles": networkDown });
    renderApp("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach the server");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("has an honest empty state with no roles", async () => {
    stubFetch({ ...routes, "GET /v1/roles": () => json(200, { data: [] }) });
    renderApp("/");
    expect(await screen.findByText(/No roles yet/)).toBeInTheDocument();
  });
});

describe("interviewer dashboard", () => {
  it("shows submitted against remaining and one next action", async () => {
    stubFetch({
      "GET /v1/auth/me": () => json(200, INTERVIEWER),
      "GET /v1/me/candidates": () =>
        json(200, {
          data: [1, 2].map((n) => ({
            candidate_id: `c${String(n)}`,
            candidate_no: n,
            role_id: ROLE,
            role_title: "Backend engineer",
            has_submitted: n === 1,
          })),
        }),
    });
    renderApp("/");
    expect(await screen.findByRole("link", { name: "Continue with C-002" })).toHaveAttribute(
      "href",
      "/candidates/c2",
    );
    expect(screen.getByText("1 of 2 submitted")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Feedback submitted" })).toHaveAttribute(
      "aria-valuenow",
      "50",
    );
  });
});
