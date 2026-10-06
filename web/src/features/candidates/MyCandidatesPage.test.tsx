import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { setCsrfToken } from "../../lib/api";
import { INTERVIEWER, ROLE } from "../../test/fixtures";
import { json, stubFetch } from "../../test/fetch";
import { renderApp } from "../../test/renderApp";

afterEach(() => {
  setCsrfToken(null);
});

describe("my candidates", () => {
  it("lists assigned candidates by anonymized id with feedback status", async () => {
    stubFetch({
      "GET /v1/auth/me": () => json(200, INTERVIEWER),
      "GET /v1/me/candidates": () =>
        json(200, {
          data: [
            {
              candidate_id: "c1",
              candidate_no: 3,
              role_id: ROLE,
              role_title: "Backend",
              has_submitted: true,
            },
            {
              candidate_id: "c2",
              candidate_no: 9,
              role_id: ROLE,
              role_title: "Backend",
              has_submitted: false,
            },
          ],
        }),
    });
    renderApp("/me/candidates");

    expect(await screen.findByRole("link", { name: "C-003" })).toHaveAttribute(
      "href",
      "/candidates/c1",
    );
    expect(screen.getByText("1 to review, 1 submitted")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Give feedback for C-009" })).toHaveAttribute(
      "href",
      "/candidates/c2",
    );
    expect(screen.getByText("Submitted")).toBeInTheDocument();
    expect(screen.getByText("Not submitted")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "My candidates" })).toBeInTheDocument();
  });

  it("says so when nothing is assigned", async () => {
    stubFetch({
      "GET /v1/auth/me": () => json(200, INTERVIEWER),
      "GET /v1/me/candidates": () => json(200, { data: [] }),
    });
    renderApp("/me/candidates");

    expect(await screen.findByText(/When one is assigned, it appears here/)).toBeInTheDocument();
  });

  it("explains a failure", async () => {
    stubFetch({
      "GET /v1/auth/me": () => json(200, INTERVIEWER),
      "GET /v1/me/candidates": () =>
        json(500, { error: { code: "internal", message: "x", details: {} } }),
    });
    renderApp("/me/candidates");

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
  });
});
