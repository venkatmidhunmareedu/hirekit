import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { setCsrfToken } from "../../lib/api";
import {
  CAND,
  CRIT_A,
  INTERVIEWER,
  QUOTE,
  ROLE,
  candidate,
  role,
  scores,
} from "../../test/fixtures";
import { json, session, stubFetch } from "../../test/fetch";
import { renderApp } from "../../test/renderApp";

afterEach(() => {
  setCsrfToken(null);
});

const text = {
  raw_text: "Jane Doe. Led a team of five engineers on the payments API.",
  anonymized_text: `Summary. ${QUOTE}.  Later text.`,
};

function recruiterRoutes(extra: Record<string, () => Response> = {}) {
  return {
    "GET /v1/auth/me": () => json(200, session),
    [`GET /v1/candidates/${CAND}`]: () => json(200, candidate),
    [`GET /v1/candidates/${CAND}/text`]: () => json(200, text),
    [`GET /v1/roles/${ROLE}`]: () => json(200, withRubric),
    [`GET /v1/roles/${ROLE}/kit`]: () => json(200, { stale: false, questions: [] }),
    [`GET /v1/candidates/${CAND}/feedback`]: () => json(200, { data: [] }),
    "GET /v1/users?role=interviewer": () => json(200, { data: [] }),
    [`GET /v1/candidates/${CAND}/assignments`]: () => json(200, { data: [] }),
    ...extra,
  };
}

describe("candidate detail, recruiter", () => {
  it("shows a verified quote, no evidence found, a flagged quote and the override", async () => {
    stubFetch(recruiterRoutes());
    renderApp(`/candidates/${CAND}`);

    expect(await screen.findByRole("heading", { name: "Candidate C-014" })).toBeInTheDocument();
    expect(screen.getByText(`“${QUOTE}”`)).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByText("No evidence found")).toBeInTheDocument();
    expect(screen.getByText("Needs a look")).toBeInTheDocument();
    expect(screen.getByText(/replaced with no evidence found/)).toBeInTheDocument();
    expect(screen.getByText("Changed by recruiter")).toBeInTheDocument();
    expect(
      screen.getByText("Note on the changed score: Mentioned in the interview"),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Must-have" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Nice-to-have" })).toBeInTheDocument();
    expect(screen.getByText("Hiring stage New to Screened")).toBeInTheDocument();
  });

  it("highlights the selected criterion's quote in the anonymized text", async () => {
    stubFetch(recruiterRoutes());
    renderApp(`/candidates/${CAND}`);

    await userEvent.click(
      await screen.findByRole("button", { name: "Show Backend experience in resume" }),
    );

    expect((await screen.findByText(QUOTE, { selector: "mark" })).tagName).toBe("MARK");
    expect(screen.queryByText(/Jane/)).not.toBeInTheDocument();
  });

  it("requires a 10 character note, then sends the override and refetches", async () => {
    let overridden = false;
    const { calls } = stubFetch(
      recruiterRoutes({
        [`GET /v1/candidates/${CAND}`]: () =>
          json(200, {
            ...candidate,
            scores: overridden
              ? [
                  { ...scores[0], override_score: 4, source: "recruiter_override" },
                  ...scores.slice(1),
                ]
              : scores,
          }),
        [`PUT /v1/candidates/${CAND}/scores/${CRIT_A}/override`]: () => {
          overridden = true;
          return json(200, { ...scores[0], override_score: 4 });
        },
      }),
    );
    renderApp(`/candidates/${CAND}`);

    await userEvent.click(await screen.findByRole("button", { name: /Change score for Backend/ }));
    const dialog = await screen.findByRole("dialog");
    const save = within(dialog).getByRole("button", { name: "Save score" });
    await userEvent.click(within(dialog).getByLabelText("4"));
    await userEvent.type(within(dialog).getByLabelText(/Note/), "too short");
    expect(save).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText(/Note/), " now long enough");
    await userEvent.click(save);

    await screen.findByText("4 / 4");
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.headers.get("X-CSRF-Token")).toBe("csrf-abc");
    expect(JSON.parse(put?.body ?? "{}")).toEqual({
      override_score: 4,
      note: "too short now long enough",
    });
  });

  it("explains a failed override and keeps the dialog open", async () => {
    stubFetch(
      recruiterRoutes({
        [`PUT /v1/candidates/${CAND}/scores/${CRIT_A}/override`]: () =>
          json(409, { error: { code: "scores_stale", message: "x", details: {} } }),
      }),
    );
    renderApp(`/candidates/${CAND}`);

    await userEvent.click(await screen.findByRole("button", { name: /Change score for Backend/ }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/Note/), "a long enough note");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save score" }));

    expect(await within(dialog).findByRole("alert")).toHaveTextContent("out of date");
  });

  it("moves stage at once, but asks before rejecting", async () => {
    const { calls } = stubFetch(
      recruiterRoutes({
        [`POST /v1/candidates/${CAND}/stage`]: () =>
          json(200, { candidate_id: CAND, from_stage: "screened", to_stage: "interview" }),
      }),
    );
    renderApp(`/candidates/${CAND}`);
    const select = await screen.findByLabelText("Hiring stage");

    await userEvent.click(select);
    await userEvent.click(await screen.findByRole("option", { name: "Interview" }));
    await screen.findByLabelText("Hiring stage");
    expect(JSON.parse(calls.find((c) => c.method === "POST")?.body ?? "{}")).toEqual({
      stage: "interview",
    });

    const before = calls.filter((c) => c.method === "POST").length;
    await userEvent.click(select);
    await userEvent.click(await screen.findByRole("option", { name: "Rejected" }));
    const dialog = await screen.findByRole("dialog");
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(before);
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(before);
  });

  it("sends the reject only after the confirmation, with the reason", async () => {
    const { calls } = stubFetch(
      recruiterRoutes({
        [`POST /v1/candidates/${CAND}/stage`]: () =>
          json(200, { candidate_id: CAND, from_stage: "screened", to_stage: "rejected" }),
      }),
    );
    renderApp(`/candidates/${CAND}`);

    await userEvent.click(await screen.findByLabelText("Hiring stage"));
    await userEvent.click(await screen.findByRole("option", { name: "Rejected" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/Reason/), "role closed");
    await userEvent.click(within(dialog).getByRole("button", { name: "Reject candidate" }));

    await screen.findByRole("heading", { name: "Candidate C-014" });
    expect(JSON.parse(calls.find((c) => c.method === "POST")?.body ?? "{}")).toEqual({
      stage: "rejected",
      reason: "role closed",
    });
  });

  it("reveals the identity only after a confirmation", async () => {
    const { calls } = stubFetch(
      recruiterRoutes({
        [`POST /v1/candidates/${CAND}:reveal-identity`]: () =>
          json(200, { identity_name: "Jane Doe", file_name: "jane.pdf" }),
      }),
    );
    renderApp(`/candidates/${CAND}`);

    await userEvent.click(await screen.findByRole("button", { name: "Show candidate name" }));
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Show candidate name" }));

    expect(await screen.findByText("Jane Doe")).toBeInTheDocument();
  });

  it("assigns an interviewer from the picker and removes them by name", async () => {
    const ian = { id: INTERVIEWER.user.id, name: "Ian" };
    let assigned: { user_id: string; name: string }[] = [];
    const { calls } = stubFetch(
      recruiterRoutes({
        "GET /v1/users?role=interviewer": () => json(200, { data: [ian] }),
        [`GET /v1/candidates/${CAND}/assignments`]: () => json(200, { data: assigned }),
        [`POST /v1/candidates/${CAND}/assignments`]: () => {
          assigned = [{ user_id: ian.id, name: ian.name }];
          return json(201, { candidate_id: CAND, user_id: ian.id });
        },
        [`DELETE /v1/candidates/${CAND}/assignments/${ian.id}`]: () => {
          assigned = [];
          return new Response(null, { status: 204 });
        },
      }),
    );
    renderApp(`/candidates/${CAND}`);

    expect(
      await screen.findByText(
        "No interviewer assigned. They will see this candidate under My candidates.",
      ),
    ).toBeInTheDocument();
    const assignButton = screen.getByRole("button", { name: "Assign interviewer" });
    expect(assignButton).toBeDisabled();
    await userEvent.click(screen.getByLabelText("Interviewer"));
    await userEvent.click(await screen.findByRole("option", { name: "Ian" }));
    await userEvent.click(assignButton);
    await userEvent.click(await screen.findByRole("button", { name: "Remove Ian" }));

    expect(
      await screen.findByText(
        "No interviewer assigned. They will see this candidate under My candidates.",
      ),
    ).toBeInTheDocument();
    expect(JSON.parse(calls.find((c) => c.method === "POST")?.body ?? "{}")).toEqual({
      user_id: ian.id,
    });
    expect(calls.map((c) => c.method).filter((m) => m !== "GET")).toEqual(["POST", "DELETE"]);
    expect(screen.queryByText(ian.id)).not.toBeInTheDocument();
  });

  it("shows the assignments the server already holds, and hides assigned people from the picker", async () => {
    stubFetch(
      recruiterRoutes({
        "GET /v1/users?role=interviewer": () =>
          json(200, {
            data: [
              { id: INTERVIEWER.user.id, name: "Ian" },
              { id: "00000000-0000-4000-8000-000000000003", name: "Ivy" },
            ],
          }),
        [`GET /v1/candidates/${CAND}/assignments`]: () =>
          json(200, { data: [{ user_id: INTERVIEWER.user.id, name: "Ian" }] }),
      }),
    );
    renderApp(`/candidates/${CAND}`);

    expect(await screen.findByRole("button", { name: "Remove Ian" })).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Interviewer"));
    expect(await screen.findByRole("option", { name: "Ivy" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Ian" })).not.toBeInTheDocument();
  });

  it("says so when no interviewer accounts exist yet", async () => {
    stubFetch(recruiterRoutes());
    renderApp(`/candidates/${CAND}`);

    expect(await screen.findByText("No interviewer accounts exist yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Assign interviewer" })).not.toBeInTheDocument();
  });

  it("links back to the ranked list and on to the next ranked candidate", async () => {
    const NEXT = "30000000-0000-4000-8000-000000000002";
    stubFetch(
      recruiterRoutes({
        [`GET /v1/roles/${candidate.role_id}/candidates?limit=100&offset=0`]: () =>
          json(200, {
            data: [CAND, NEXT].map((id, i) => ({
              id,
              candidate_no: i + 1,
              stage: "new",
              processing_status: "done",
              failure_reason: null,
              total: 5,
              must_have_covered: 1,
              must_have_total: 1,
              stale: false,
              duplicate_of_candidate_no: null,
              scores: [],
            })),
            page: { limit: 100, offset: 0, total: 2 },
          }),
      }),
    );
    renderApp(`/candidates/${CAND}`);

    expect(await screen.findByRole("link", { name: "Next candidate" })).toHaveAttribute(
      "href",
      `/candidates/${NEXT}`,
    );
    expect(screen.getByRole("link", { name: "Back to ranked candidates" })).toHaveAttribute(
      "href",
      `/roles/${candidate.role_id}/candidates`,
    );
  });

  it("shows an error when the candidate cannot be loaded", async () => {
    stubFetch({
      "GET /v1/auth/me": () => json(200, session),
      [`GET /v1/candidates/${CAND}`]: () =>
        json(404, { error: { code: "not_found", message: "x", details: {} } }),
    });
    renderApp(`/candidates/${CAND}`);

    expect(await screen.findByRole("alert")).toHaveTextContent("missing or you cannot see it");
  });
});

const withRubric = {
  ...role,
  criteria: role.criteria.map((c, i) =>
    i === 0 ? { ...c, rubric: [{ level: 3, descriptor: "Owns services in production" }] } : c,
  ),
};

describe("candidate detail, interviewer", () => {
  const interviewerRoutes = (extra: Record<string, () => Response> = {}) => ({
    "GET /v1/auth/me": () => json(200, INTERVIEWER),
    [`GET /v1/candidates/${CAND}`]: () =>
      json(200, { id: CAND, candidate_no: 14, role_id: ROLE, has_submitted: false }),
    [`GET /v1/roles/${ROLE}`]: () => json(200, withRubric),
    [`GET /v1/roles/${ROLE}/kit`]: () => json(200, { stale: false, questions: [] }),
    [`GET /v1/candidates/${CAND}/feedback`]: () => json(200, { data: [] }),
    ...extra,
  });

  it("hides AI scores and recruiter controls before feedback", async () => {
    stubFetch(interviewerRoutes());
    renderApp(`/candidates/${CAND}`);

    expect(await screen.findByText(/stay hidden until you submit/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Hiring stage")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show candidate name" })).not.toBeInTheDocument();
    expect(await screen.findByText("0 of 3 criteria scored")).toBeInTheDocument();
  });

  it("shows the rubric text and why submit is disabled", async () => {
    stubFetch(interviewerRoutes());
    renderApp(`/candidates/${CAND}`);

    expect(await screen.findByText("Owns services in production")).toBeVisible();
    expect(screen.getByText(/3 criteria still need a score and a comment/)).toBeInTheDocument();
    expect(screen.getByText(/Locked after submit; a recruiter can approve an edit/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Back to My candidates" })).toHaveAttribute(
      "href",
      "/me/candidates",
    );
    expect(screen.queryByText(/Anonymized resume text/)).not.toBeInTheDocument();
  });

  it("offers the next candidate to review after submitting", async () => {
    let submitted = false;
    const mine = () => [
      {
        candidate_id: CAND,
        candidate_no: 14,
        role_id: ROLE,
        role_title: "Backend",
        has_submitted: submitted,
      },
      {
        candidate_id: "c9",
        candidate_no: 9,
        role_id: ROLE,
        role_title: "Backend",
        has_submitted: false,
      },
    ];
    stubFetch(
      interviewerRoutes({
        "GET /v1/me/candidates": () => json(200, { data: mine() }),
        [`POST /v1/candidates/${CAND}/feedback`]: () => {
          submitted = true;
          return json(201, { data: [] });
        },
      }),
    );
    renderApp(`/candidates/${CAND}`);
    await screen.findByText("0 of 3 criteria scored");
    expect(screen.queryByRole("link", { name: "Next candidate" })).not.toBeInTheDocument();

    for (const name of ["Backend experience", "Incident response", "Mentoring"]) {
      const group = screen.getByRole("radiogroup", { name: `Score for ${name}` });
      await userEvent.click(within(group).getByLabelText("3"));
      await userEvent.type(screen.getByLabelText(`Comment on ${name}`), "solid");
    }
    await userEvent.click(screen.getByRole("button", { name: "Submit feedback" }));

    expect(await screen.findByRole("link", { name: "Next candidate" })).toHaveAttribute(
      "href",
      "/candidates/c9",
    );
    expect(screen.getByText(/Feedback submitted/)).toBeInTheDocument();
  });

  it("keeps submit disabled until every criterion has a score and comment, then submits", async () => {
    const { calls } = stubFetch(
      interviewerRoutes({
        [`POST /v1/candidates/${CAND}/feedback`]: () => json(201, { data: [] }),
      }),
    );
    renderApp(`/candidates/${CAND}`);
    const submit = await screen.findByRole("button", { name: "Submit feedback" });

    for (const name of ["Backend experience", "Incident response", "Mentoring"]) {
      expect(submit).toBeDisabled();
      const group = screen.getByRole("radiogroup", { name: `Score for ${name}` });
      await userEvent.click(within(group).getByLabelText("3"));
      await userEvent.type(screen.getByLabelText(`Comment on ${name}`), "solid");
    }
    expect(screen.getByText("3 of 3 criteria scored")).toBeInTheDocument();
    await userEvent.click(submit);

    await screen.findByRole("button", { name: "Submit feedback" });
    const post = calls.find((c) => c.method === "POST");
    expect((post?.body ?? "").split('"criterion_id"')).toHaveLength(4);
  });

  it("shows submitted feedback read-only and locked", async () => {
    stubFetch(
      interviewerRoutes({
        [`GET /v1/candidates/${CAND}/feedback`]: () =>
          json(200, {
            data: [CRIT_A, "x"].slice(0, 1).map((c) => ({
              interviewer_id: INTERVIEWER.user.id,
              criterion_id: c,
              score: 3,
              comment: "good",
              locked: true,
            })),
          }),
      }),
    );
    renderApp(`/candidates/${CAND}`);

    expect(await screen.findByText(/Submitted and locked/)).toBeInTheDocument();
    expect(screen.getByText("Submitted")).toBeInTheDocument();
    // A revisit is not a fresh submit: no confirmation, no repeated thanks.
    expect(screen.queryByText(/Feedback submitted/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit feedback" })).not.toBeInTheDocument();
  });
});
