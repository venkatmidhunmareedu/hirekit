import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { setCsrfToken } from "../../lib/api";
import { CRIT_A, CRIT_B } from "../../test/fixtures";
import { json, session, stubFetch } from "../../test/fetch";
import { renderApp } from "../../test/renderApp";

afterEach(() => {
  setCsrfToken(null);
});

const fb = (id: string, score: number) => ({
  interviewer_id: id,
  criterion_id: CRIT_A,
  score,
  comment: `comment ${score}`,
  locked: true,
});
const comparison = {
  criteria: [
    { id: CRIT_A, name: "Backend experience", kind: "must_have" },
    { id: CRIT_B, name: "Mentoring", kind: "nice_to_have" },
  ],
  candidates: [
    {
      candidate_id: "c1",
      candidate_no: 1,
      cells: [
        {
          criterion_id: CRIT_A,
          model_score: 3,
          override_score: null,
          feedback: [fb("i1", 4), fb("i2", 1)],
          disagreement: true,
        },
      ],
    },
    {
      candidate_id: "c2",
      candidate_no: 2,
      cells: [
        {
          criterion_id: CRIT_A,
          model_score: 2,
          override_score: 4,
          feedback: [],
          disagreement: false,
        },
        {
          criterion_id: CRIT_B,
          model_score: null,
          override_score: null,
          feedback: [],
          disagreement: false,
        },
      ],
    },
  ],
};

describe("compare", () => {
  it("shows candidates as columns, criteria as rows and flags interviewer disagreement", async () => {
    const { calls } = stubFetch({
      "GET /v1/auth/me": () => json(200, session),
      "GET /v1/compare?ids=c1%2Cc2": () => json(200, comparison),
    });
    renderApp("/compare?ids=c1,c2");

    expect(await screen.findByRole("columnheader", { name: "C-001" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "C-002" })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: /Backend experience/ })).toBeInTheDocument();
    expect(screen.getByText("Interviewers disagree")).toBeInTheDocument();
    expect(screen.getAllByText("4 / 4", { selector: ".mono" })).toHaveLength(2);
    expect(screen.getByText("No data")).toBeInTheDocument();
    expect(calls.filter((c) => !c.path.includes("cost-log"))).toHaveLength(2);
  });

  it("asks for two to four candidates when the link has fewer", async () => {
    const { calls } = stubFetch({ "GET /v1/auth/me": () => json(200, session) });
    renderApp("/compare?ids=c1");

    expect(
      await screen.findByText("Choose two to four candidates to compare."),
    ).toBeInTheDocument();
    expect(calls.filter((c) => !c.path.includes("cost-log"))).toHaveLength(1);
  });

  it("explains a comparison that cannot be loaded", async () => {
    stubFetch({
      "GET /v1/auth/me": () => json(200, session),
      "GET /v1/compare?ids=c1%2Cc2": () =>
        json(404, { error: { code: "not_found", message: "x", details: {} } }),
    });
    renderApp("/compare?ids=c1,c2");

    expect(await screen.findByRole("alert")).toHaveTextContent("missing or you cannot see it");
  });
});
