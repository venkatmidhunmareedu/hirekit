import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { setCsrfToken } from "../../lib/api";
import { CAND, CRIT_A, ROLE, candidate, role } from "../../test/fixtures";
import { json, session, stubFetch } from "../../test/fetch";
import { renderApp } from "../../test/renderApp";

afterEach(() => {
  setCsrfToken(null);
});

const INT = "00000000-0000-4000-8000-000000000002";
const row = (locked: boolean) => ({
  interviewer_id: INT,
  criterion_id: CRIT_A,
  score: 3,
  comment: "good systems sense",
  locked,
});

describe("feedback, recruiter", () => {
  it("shows every interviewer's feedback and approves an edit", async () => {
    let locked = true;
    const { calls } = stubFetch({
      "GET /v1/auth/me": () => json(200, session),
      [`GET /v1/candidates/${CAND}`]: () => json(200, candidate),
      [`GET /v1/candidates/${CAND}/text`]: () => json(200, { raw_text: "r", anonymized_text: "a" }),
      [`GET /v1/roles/${ROLE}`]: () => json(200, role),
      [`GET /v1/candidates/${CAND}/feedback`]: () => json(200, { data: [row(locked)] }),
      [`POST /v1/candidates/${CAND}/feedback/${INT}:approve-edit`]: () => {
        locked = false;
        return json(200, { data: [row(false)] });
      },
    });
    renderApp(`/candidates/${CAND}`);

    await userEvent.click(await screen.findByRole("tab", { name: /^Feedback/ }));
    expect(await screen.findByText("good systems sense", { exact: false })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Approve edit/ }));

    expect(await screen.findByText("Unlocked for an edit")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST")).toBe(true);
  });
});
