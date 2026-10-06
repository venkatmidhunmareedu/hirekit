import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { setCsrfToken } from "../../lib/api";
import { CRIT_A, CRIT_B, INTERVIEWER, ROLE, role } from "../../test/fixtures";
import { json, session, stubFetch } from "../../test/fetch";
import { renderApp } from "../../test/renderApp";

afterEach(() => {
  setCsrfToken(null);
});

async function first(name: string, index = 0): Promise<HTMLElement> {
  const found = (await screen.findAllByRole("button", { name })).at(index);
  if (!found) throw new Error(`no button ${name} at ${index}`);
  return found;
}

const q = (id: string, crit: string, position: number, text: string) => ({
  id,
  criterion_id: crit,
  question_text: text,
  strong_answer: `strong ${text}`,
  weak_answer: `weak ${text}`,
  position,
});
const kit = {
  role_id: ROLE,
  stale: false,
  criteria_version: 1,
  questions: [
    q("q1", CRIT_A, 1, "Tell me about APIs"),
    q("q2", CRIT_A, 2, "Scaling?"),
    q("q3", CRIT_B, 1, "Outages?"),
  ],
};

function routes(extra: Record<string, () => Response> = {}, who = session) {
  return {
    "GET /v1/auth/me": () => json(200, who),
    [`GET /v1/roles/${ROLE}`]: () => json(200, role),
    [`GET /v1/roles/${ROLE}/kit`]: () => json(200, kit),
    ...extra,
  };
}

describe("interview kit, recruiter", () => {
  it("groups questions by criterion with strong and weak answers", async () => {
    stubFetch(routes());
    renderApp(`/roles/${ROLE}/kit`);

    expect(await screen.findByRole("heading", { name: "Backend experience" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Tell me about APIs" })).toBeInTheDocument();
    expect(screen.getByText("strong Tell me about APIs")).toBeInTheDocument();
    expect(screen.getByText("weak Tell me about APIs")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Print interview kit" })).not.toBeInTheDocument();
  });

  it("warns that a stale kit belongs to older criteria", async () => {
    stubFetch(routes({ [`GET /v1/roles/${ROLE}/kit`]: () => json(200, { ...kit, stale: true }) }));
    renderApp(`/roles/${ROLE}/kit`);

    expect(await screen.findByText(/generated for older criteria/)).toBeInTheDocument();
  });

  it("blocks generation while the role is a draft", async () => {
    stubFetch(
      routes({
        [`GET /v1/roles/${ROLE}`]: () => json(200, { ...role, status: "draft" }),
        [`GET /v1/roles/${ROLE}/kit`]: () => json(200, { ...kit, questions: [] }),
      }),
    );
    renderApp(`/roles/${ROLE}/kit`);

    expect(await screen.findByText(/Approve the criteria/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate interview kit" })).toBeDisabled();
  });

  it("generates, polls the job and shows the new kit", async () => {
    let done = false;
    stubFetch(
      routes({
        [`GET /v1/roles/${ROLE}/kit`]: () => json(200, done ? kit : { ...kit, questions: [] }),
        [`POST /v1/roles/${ROLE}/kit:generate`]: () => json(202, { job_id: 7 }),
        "GET /v1/jobs/7": () => {
          done = true;
          return json(200, { id: 7, status: "succeeded" });
        },
      }),
    );
    renderApp(`/roles/${ROLE}/kit`);

    await userEvent.click(await screen.findByRole("button", { name: "Generate interview kit" }));

    expect(await screen.findByRole("heading", { name: "Scaling?" })).toBeInTheDocument();
  });

  it("explains a budget block on generate", async () => {
    stubFetch(
      routes({
        [`POST /v1/roles/${ROLE}/kit:generate`]: () =>
          json(409, { error: { code: "budget_reached", message: "x", details: {} } }),
      }),
    );
    renderApp(`/roles/${ROLE}/kit`);

    await userEvent.click(await screen.findByRole("button", { name: "Regenerate interview kit" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("AI budget has been reached");
  });

  it("edits a question in place", async () => {
    const { calls } = stubFetch(
      routes({
        "PUT /v1/kit/questions/q1": () => json(200, q("q1", CRIT_A, 1, "Tell me about APIs")),
      }),
    );
    renderApp(`/roles/${ROLE}/kit`);

    await userEvent.click(await first("Edit"));
    const field = screen.getByLabelText("Question");
    await userEvent.clear(field);
    await userEvent.type(field, "New wording");
    await userEvent.click(screen.getByRole("button", { name: "Save question" }));

    await screen.findByRole("heading", { name: "Backend experience" });
    expect(calls.find((c) => c.method === "PUT")?.body).toContain("New wording");
  });

  it("moves a question down by swapping positions", async () => {
    const { calls } = stubFetch(
      routes({
        "PUT /v1/kit/questions/q1": () => json(200, q("q1", CRIT_A, 2, "Tell me about APIs")),
        "PUT /v1/kit/questions/q2": () => json(200, q("q2", CRIT_A, 1, "Scaling?")),
      }),
    );
    renderApp(`/roles/${ROLE}/kit`);

    await userEvent.click(await first("Move down"));

    await screen.findByRole("heading", { name: "Backend experience" });
    const puts = calls.filter((c) => c.method === "PUT");
    expect(puts.map((c) => c.body)).toEqual(['{"position":2}', '{"position":1}']);
  });

  it("deletes and regenerates a question", async () => {
    const { calls } = stubFetch(
      routes({
        "DELETE /v1/kit/questions/q3": () => new Response(null, { status: 204 }),
        "POST /v1/kit/questions/q1:regenerate": () => json(202, { job_id: 9 }),
        "GET /v1/jobs/9": () => json(200, { id: 9, status: "failed" }),
      }),
    );
    renderApp(`/roles/${ROLE}/kit`);

    await userEvent.click(await first("Regenerate"));
    expect(await screen.findByText(/did not finish/)).toBeInTheDocument();
    await userEvent.click(await first("Delete", 2));

    await screen.findByRole("heading", { name: "Backend experience" });
    expect(calls.some((c) => c.method === "DELETE")).toBe(true);
  });
});

describe("interview kit, no kit yet", () => {
  it("offers Generate kit to a recruiter instead of an error", async () => {
    stubFetch(
      routes({
        [`GET /v1/roles/${ROLE}/kit`]: () =>
          json(404, { error: { code: "not_found", message: "kit not found", details: {} } }),
      }),
    );
    renderApp(`/roles/${ROLE}/kit`);

    expect(await screen.findByText(/No interview kit yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate interview kit" })).toBeEnabled();
  });

  it("tells an interviewer the kit is not ready", async () => {
    stubFetch(
      routes(
        {
          [`GET /v1/roles/${ROLE}/kit`]: () =>
            json(404, { error: { code: "not_found", message: "kit not found", details: {} } }),
        },
        INTERVIEWER,
      ),
    );
    renderApp(`/roles/${ROLE}/kit`);

    expect(await screen.findByText("The interview kit is not ready yet.")).toBeInTheDocument();
  });

  it("keeps a server error as an error", async () => {
    stubFetch(
      routes({
        [`GET /v1/roles/${ROLE}/kit`]: () =>
          json(500, { error: { code: "internal", message: "boom", details: {} } }),
      }),
    );
    renderApp(`/roles/${ROLE}/kit`);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

describe("interview kit, interviewer", () => {
  it("is read-only and printable", async () => {
    stubFetch(routes({}, INTERVIEWER));
    renderApp(`/roles/${ROLE}/kit`);

    expect(await screen.findByRole("button", { name: "Print interview kit" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Generate interview kit|Regenerate interview kit/ }),
    ).not.toBeInTheDocument();
  });
});
