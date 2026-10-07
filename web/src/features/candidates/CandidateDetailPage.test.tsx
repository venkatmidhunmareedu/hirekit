import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

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
    await userEvent.click(screen.getByRole("tab", { name: /^History/ }));
    expect(screen.getByText("Hiring stage New to Screened")).toBeInTheDocument();
  });

  it("highlights the selected criterion's quote in the anonymized text", async () => {
    stubFetch(recruiterRoutes());
    renderApp(`/candidates/${CAND}`);

    await userEvent.click(
      await screen.findByRole("button", { name: "Show Backend experience in resume" }),
    );

    expect(
      (await screen.findByText(QUOTE, { selector: "mark [role='button']" })).closest("mark"),
    ).not.toBeNull();
    expect(screen.queryByText(/Jane/)).not.toBeInTheDocument();
  });

  it("highlights every verified quote at once and links a highlight to its card", async () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    stubFetch(recruiterRoutes());
    renderApp(`/candidates/${CAND}`);

    const mark = await screen.findByRole("button", { name: /Show scoring card for this quote/ });
    expect(mark).toHaveTextContent(QUOTE);
    expect(screen.getAllByRole("button", { name: /Show scoring card/ })).toHaveLength(1);
    await userEvent.click(mark);

    const card = document.getElementById(`criterion-${CRIT_A}`);
    await waitFor(() => {
      expect(card).toHaveFocus();
    });
    expect(scrollIntoView).toHaveBeenCalled();
    mark.focus();
    await userEvent.keyboard("{Enter}");
    await waitFor(() => {
      expect(card).toHaveFocus();
    });
  });

  it("shows the score as a meter, arrow keys move between segments, and clicking opens the dialog", async () => {
    stubFetch(recruiterRoutes());
    renderApp(`/candidates/${CAND}`);

    const group = await screen.findByRole("radiogroup", { name: /Score 3 of 4/ });
    const three = within(group).getByRole("radio", { name: "Set score to 3" });
    expect(three).toBeChecked();
    expect(screen.queryByRole("button", { name: /Change score for/ })).not.toBeInTheDocument();
    three.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(within(group).getByRole("radio", { name: "Set score to 4" })).toHaveFocus();
    await userEvent.keyboard("{ArrowRight}");
    expect(within(group).getByRole("radio", { name: "Set score to 1" })).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("1")).toBeChecked();
  });

  it("scrolls the resume region to the quote and announces it", async () => {
    const scrollTo = vi.fn();
    Element.prototype.scrollTo = scrollTo;
    stubFetch(recruiterRoutes());
    renderApp(`/candidates/${CAND}`);

    await userEvent.click(
      await screen.findByRole("button", { name: "Show Backend experience in resume" }),
    );

    await screen.findByText(QUOTE, { selector: "mark [role='button']" });
    expect(scrollTo).toHaveBeenCalledTimes(1);
    expect(
      within(screen.getByRole("region", { name: "Anonymized resume" })).getByText(QUOTE),
    ).toBeInTheDocument();
    expect(screen.getByText("Quote located in the resume")).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Show Backend experience in resume" }),
    );
    expect(scrollTo).toHaveBeenCalledTimes(2);
  });

  it("says so when the quote is not in the resume text", async () => {
    stubFetch(
      recruiterRoutes({
        [`GET /v1/candidates/${CAND}/text`]: () =>
          json(200, { raw_text: "x", anonymized_text: "Nothing like it here." }),
      }),
    );
    renderApp(`/candidates/${CAND}`);

    await userEvent.click(
      await screen.findByRole("button", { name: "Show Backend experience in resume" }),
    );

    expect(await screen.findByText(/not found in the resume text/)).toBeInTheDocument();
    expect(screen.queryByText("Quote located in the resume")).not.toBeInTheDocument();
  });

  it("lists the score groups in a navigator with counts", async () => {
    stubFetch(recruiterRoutes());
    renderApp(`/candidates/${CAND}`);

    const nav = await screen.findByRole("navigation", { name: "Score groups" });
    expect(within(nav).getByRole("button", { name: /Must-have/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(within(nav).getByRole("button", { name: /Nice-to-have/ })).toBeInTheDocument();
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

    const group = await screen.findByRole("radiogroup", { name: /change score for Backend/ });
    await userEvent.click(within(group).getByRole("radio", { name: "Set score to 4" }));
    const dialog = await screen.findByRole("dialog");
    const save = within(dialog).getByRole("button", { name: "Save score" });
    expect(within(dialog).getByLabelText("4")).toBeChecked();
    await userEvent.type(within(dialog).getByLabelText(/Note/), "too short");
    expect(save).toBeDisabled();
    expect(within(dialog).getByText("9 of 10 characters")).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/Note/)).toHaveAccessibleDescription("9 of 10 characters");
    await userEvent.type(within(dialog).getByLabelText(/Note/), " now long enough");
    expect(within(dialog).getByText("Ready to save")).toBeInTheDocument();
    await userEvent.click(save);

    await screen.findByRole("radiogroup", { name: /Score 4 of 4/ });
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.headers.get("X-CSRF-Token")).toBe("csrf-abc");
    expect(JSON.parse(put?.body ?? "{}")).toEqual({
      override_score: 4,
      note: "too short now long enough",
    });
  });

  // HK-86 regression: the weighted total comes from the ranked list, so an override must refresh it.
  it("updates the weighted total after a score is overridden", async () => {
    let overridden = false;
    stubFetch(
      recruiterRoutes({
        [`GET /v1/roles/${candidate.role_id}/candidates?limit=100&offset=0`]: () =>
          json(200, {
            data: [
              {
                id: CAND,
                candidate_no: 14,
                stage: "new",
                processing_status: "done",
                failure_reason: null,
                total: overridden ? 12 : 4,
                must_have_covered: 1,
                must_have_total: 1,
                stale: false,
                duplicate_of_candidate_no: null,
                scores: [],
              },
            ],
            page: { limit: 100, offset: 0, total: 1 },
          }),
        [`PUT /v1/candidates/${CAND}/scores/${CRIT_A}/override`]: () => {
          overridden = true;
          return json(200, { ...scores[0], override_score: 4 });
        },
      }),
    );
    renderApp(`/candidates/${CAND}`);

    expect(await screen.findByText("4.0")).toBeInTheDocument();
    const group = await screen.findByRole("radiogroup", { name: /change score for Backend/ });
    await userEvent.click(within(group).getByRole("radio", { name: "Set score to 4" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/Note/), "Confirmed in the interview");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save score" }));

    expect(await screen.findByText("12.0")).toBeInTheDocument();
  });

  // HK-86 regression: scores stayed at the last fetch while a re-score job ran.
  it("refetches the scores once the re-score jobs have finished", async () => {
    let polls = 0;
    stubFetch(
      recruiterRoutes({
        [`GET /v1/roles/${candidate.role_id}/queue`]: () => {
          polls += 1;
          return json(200, polls === 1 ? { waiting: 0, running: 1 } : { waiting: 0, running: 0 });
        },
        [`GET /v1/candidates/${CAND}`]: () =>
          json(200, {
            ...candidate,
            scores: polls > 1 ? [{ ...scores[0], model_score: 4 }, ...scores.slice(1)] : scores,
          }),
      }),
    );
    renderApp(`/candidates/${CAND}`);

    await screen.findByRole("radiogroup", { name: /Score 3 of 4/ });
    expect(
      await screen.findByRole("radiogroup", { name: /Score 4 of 4/ }, { timeout: 6000 }),
    ).toBeInTheDocument();
  }, 10000);

  it("explains a failed override and keeps the dialog open", async () => {
    stubFetch(
      recruiterRoutes({
        [`PUT /v1/candidates/${CAND}/scores/${CRIT_A}/override`]: () =>
          json(409, { error: { code: "scores_stale", message: "x", details: {} } }),
      }),
    );
    renderApp(`/candidates/${CAND}`);

    const group = await screen.findByRole("radiogroup", { name: /change score for Backend/ });
    await userEvent.click(within(group).getByRole("radio", { name: "Set score to 2" }));
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

    await userEvent.click(await screen.findByRole("tab", { name: /^Interviewers/ }));
    expect(
      await screen.findByText("No interviewers assigned. Pick someone to ask for feedback."),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add interviewer" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Search interviewers" }), "zz");
    expect(screen.getByText("No interviewer matches that name.")).toBeInTheDocument();
    await userEvent.clear(screen.getByRole("textbox", { name: "Search interviewers" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Search interviewers" }), "ia");
    await userEvent.click(screen.getByRole("button", { name: "Assign Ian" }));
    expect(await screen.findByText("Ian assigned.")).toBeInTheDocument();
    expect(await screen.findByRole("tab", { name: "Interviewers (1)" })).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    await userEvent.click(await screen.findByRole("button", { name: "Remove Ian" }));

    expect(
      await screen.findByText("No interviewers assigned. Pick someone to ask for feedback."),
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

    await userEvent.click(await screen.findByRole("tab", { name: /^Interviewers/ }));
    expect(await screen.findByRole("button", { name: "Remove Ian" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add interviewer" }));
    expect(await screen.findByRole("button", { name: "Assign Ivy" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Assign Ian" })).not.toBeInTheDocument();
  });

  it("says so when no interviewer accounts exist yet", async () => {
    stubFetch(recruiterRoutes());
    renderApp(`/candidates/${CAND}`);

    await userEvent.click(await screen.findByRole("tab", { name: /^Interviewers/ }));
    expect(await screen.findByText("No interviewer accounts exist yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add interviewer" })).not.toBeInTheDocument();
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

const NAMES = ["Backend experience", "Incident response", "Mentoring"];

/** Scores 3 and writes a comment on the criterion shown, then moves on with the primary button. */
async function fillStep(name: string, primary: string) {
  const group = screen.getByRole("radiogroup", { name: `Score for ${name}` });
  await userEvent.click(within(group).getByRole("radio", { name: /^3/ }));
  await userEvent.type(screen.getByLabelText(`Comment on ${name}`), "solid");
  await userEvent.click(screen.getByRole("button", { name: primary }));
}

async function fillAll() {
  await fillStep(NAMES[0] ?? "", "Save and next");
  await fillStep(NAMES[1] ?? "", "Save and next");
  await fillStep(NAMES[2] ?? "", "Review and submit");
}

describe("candidate detail, interviewer", () => {
  const question = (id: string, criterion_id: string, position: number) => ({
    id,
    criterion_id,
    question_text: `Question ${id}`,
    strong_answer: `strong ${id}`,
    weak_answer: `weak ${id}`,
    position,
  });
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
    expect(await screen.findByText("Criterion 1 of 3")).toBeInTheDocument();
  });

  it("shows one criterion with its rubric text beside each score", async () => {
    stubFetch(interviewerRoutes());
    renderApp(`/candidates/${CAND}`);

    expect(await screen.findByRole("heading", { name: "Backend experience" })).toBeInTheDocument();
    const group = screen.getByRole("radiogroup", { name: "Score for Backend experience" });
    expect(
      within(group).getByRole("radio", { name: "3 Owns services in production" }),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Comment on Incident response")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to My candidates" })).toHaveAttribute(
      "href",
      "/me/candidates",
    );
    expect(screen.queryByText(/Anonymized resume text/)).not.toBeInTheDocument();
    expect(screen.queryByRole("radiogroup", { name: /change score/ })).not.toBeInTheDocument();
  });

  it("lists the questions once and opens the strong and weak answers on demand", async () => {
    stubFetch(
      interviewerRoutes({
        [`GET /v1/roles/${ROLE}/kit`]: () =>
          json(200, {
            stale: false,
            questions: [question("q1", CRIT_A, 1), question("q2", CRIT_A, 2)],
          }),
      }),
    );
    renderApp(`/candidates/${CAND}`);

    expect(await screen.findAllByText("Question q1")).toHaveLength(1);
    expect(screen.getByText("Question q1").closest("details")).not.toHaveAttribute("open");
    await userEvent.click(screen.getByText("Question q1"));

    expect(screen.getByText("Question q1").closest("details")).toHaveAttribute("open");
    expect(screen.getByText("strong q1")).toBeInTheDocument();
  });

  it("selects a score with the 0 to 4 keys", async () => {
    stubFetch(interviewerRoutes());
    renderApp(`/candidates/${CAND}`);
    const group = await screen.findByRole("radiogroup", { name: "Score for Backend experience" });

    within(group).getByRole("radio", { name: /^1/ }).focus();
    await userEvent.keyboard("4");

    expect(within(group).getByRole("radio", { name: /^4/ })).toBeChecked();
  });

  it("moves between criteria with Previous and Save and next and keeps the draft", async () => {
    stubFetch(interviewerRoutes());
    renderApp(`/candidates/${CAND}`);
    await screen.findByRole("heading", { name: "Backend experience" });

    await fillStep("Backend experience", "Save and next");

    expect(await screen.findByRole("heading", { name: "Incident response" })).toHaveFocus();
    expect(screen.getByRole("status")).toHaveTextContent("Criterion 2 of 3: Incident response");
    await userEvent.click(screen.getByRole("button", { name: "Previous" }));
    const group = await screen.findByRole("radiogroup", { name: "Score for Backend experience" });
    expect(within(group).getByRole("radio", { name: /^3/ })).toBeChecked();
    expect(screen.getByLabelText("Comment on Backend experience")).toHaveValue("solid");
  });

  it("jumps from the progress segments", async () => {
    stubFetch(interviewerRoutes());
    renderApp(`/candidates/${CAND}`);
    const nav = await screen.findByRole("navigation", { name: "Criteria" });

    await userEvent.click(within(nav).getByRole("button", { name: /Mentoring/ }));

    expect(await screen.findByRole("heading", { name: "Mentoring" })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /Mentoring/ })).toHaveAttribute(
      "aria-current",
      "step",
    );
  });

  it("flags missing criteria on the review step and keeps submit disabled", async () => {
    stubFetch(interviewerRoutes());
    renderApp(`/candidates/${CAND}`);
    await screen.findByRole("heading", { name: "Backend experience" });
    const nav = screen.getByRole("navigation", { name: "Criteria" });

    await userEvent.click(within(nav).getByRole("button", { name: "Review step" }));

    expect(
      await screen.findByText(/3 criteria still need a score and a comment/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Locked after submit; a recruiter can approve an edit/),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Needs a score and comment")).toHaveLength(3);
    expect(screen.getByRole("button", { name: "Submit feedback" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Edit Mentoring" }));
    expect(await screen.findByRole("heading", { name: "Mentoring" })).toBeInTheDocument();
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
    await screen.findByText("Criterion 1 of 3");
    expect(screen.queryByRole("link", { name: "Next candidate" })).not.toBeInTheDocument();

    await fillAll();
    await userEvent.click(await screen.findByRole("button", { name: "Submit feedback" }));

    expect(await screen.findByRole("link", { name: "Next candidate" })).toHaveAttribute(
      "href",
      "/candidates/c9",
    );
    expect(screen.getByText(/Feedback submitted/)).toBeInTheDocument();
  });

  it("submits every criterion once, and only when all are complete", async () => {
    const { calls } = stubFetch(
      interviewerRoutes({
        [`POST /v1/candidates/${CAND}/feedback`]: () => json(201, { data: [] }),
      }),
    );
    renderApp(`/candidates/${CAND}`);
    await screen.findByRole("heading", { name: "Backend experience" });

    await fillAll();
    expect(await screen.findByText("3 of 3 complete")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Submit feedback" }));

    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST")).toBe(true);
    });
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
    expect(screen.queryByRole("button", { name: /^Edit / })).not.toBeInTheDocument();
  });
});
