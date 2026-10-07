import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { setCsrfToken } from "../../lib/api";
import { json, networkDown, session, stubFetch } from "../../test/fetch";
import { renderApp } from "../../test/render";

afterEach(() => {
  setCsrfToken(null);
});

const ROLE_ID = "10000000-0000-4000-8000-000000000001";
const PATH = `/roles/${ROLE_ID}/candidates`;
const LIST = `GET /v1/roles/${ROLE_ID}/candidates?limit=100&offset=0`;
const QUEUE = `GET /v1/roles/${ROLE_ID}/queue`;

const role = (status: string) => ({
  id: ROLE_ID,
  title: "Backend engineer",
  job_description: "Build.",
  status,
  criteria_version: 1,
  created_at: "2026-09-30T09:00:00Z",
  updated_at: "2026-09-30T09:00:00Z",
  criteria: [],
});

const me = { "GET /v1/auth/me": () => json(200, session) };
const approved = { ...me, [`GET /v1/roles/${ROLE_ID}`]: () => json(200, role("approved")) };
const idle = { [QUEUE]: () => json(200, { data: [], waiting: 0, running: 0 }) };

function cell(id: string, name: string, over: Record<string, unknown>) {
  return {
    criterion_id: id,
    criterion_name: name,
    kind: "must_have",
    status: "scored",
    model_score: 3,
    override_score: null,
    source: "model_suggestion",
    stale: false,
    quote: "secret evidence quote",
    flag_reason: null,
    override_note: null,
    ...over,
  };
}

function candidate(no: number, over: Record<string, unknown> = {}) {
  return {
    id: `30000000-0000-4000-8000-00000000000${no}`,
    candidate_no: no,
    stage: "screened",
    processing_status: "done",
    failure_reason: null,
    total: 11.5,
    must_have_covered: 2,
    must_have_total: 3,
    stale: false,
    duplicate_of_candidate_no: null,
    scores: [
      cell("c1", "Python experience", {}),
      cell("c2", "Payments", { status: "no_evidence", model_score: null }),
    ],
    ...over,
  };
}

const page = (data: unknown[], total = data.length, offset = 0) => ({
  data,
  page: { limit: 100, offset, total },
});

describe("candidates page", () => {
  it("locks upload and the list while the role is a draft", async () => {
    stubFetch({ ...me, [`GET /v1/roles/${ROLE_ID}`]: () => json(200, role("draft")) });

    renderApp(PATH);

    expect(await screen.findByText(/Approve the criteria to start uploading/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Choose files/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Propose criteria" })).toHaveAttribute(
      "href",
      `/roles/${ROLE_ID}`,
    );
  });

  it("shows the empty state with one next action", async () => {
    stubFetch({ ...approved, ...idle, [LIST]: () => json(200, page([])) });

    renderApp(PATH);

    expect(await screen.findByText(/No resumes yet/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Choose files/)).toBeInTheDocument();
  });

  it("ranks candidates by anonymous id with chips, coverage, flags and stage", async () => {
    stubFetch({
      ...approved,
      ...idle,
      [LIST]: () =>
        json(
          200,
          page([
            candidate(14, {
              scores: [
                cell("c1", "Python experience", { override_score: 4, model_score: 2 }),
                cell("c2", "Payments", { status: "no_evidence", model_score: null }),
                cell("c3", "Go", { flag_reason: "Quote not found" }),
              ],
            }),
            candidate(3, { total: 4, stage: "new", duplicate_of_candidate_no: 14, stale: true }),
          ]),
        ),
    });

    renderApp(PATH);

    const table = await screen.findByRole("table", { name: /ranked by weighted total/ });
    const first = within(table).getByRole("row", { name: /^1 C-014/ });
    const second = within(table).getByRole("row", { name: /^2 C-003/ });
    expect(within(first).getByText("C-014")).toBeInTheDocument();
    expect(within(first).getByText("4 / 4")).toBeInTheDocument();
    expect(within(first).getByText("Changed by recruiter")).toBeInTheDocument();
    expect(within(first).getByText("No evidence found")).toBeInTheDocument();
    expect(within(first).getByText("11.5")).toBeInTheDocument();
    expect(within(first).getByText("2 of 3")).toBeInTheDocument();
    expect(within(first).getByText("Screened")).toBeInTheDocument();
    expect(within(second).getByText("C-003")).toBeInTheDocument();
    expect(within(second).getByText(/Possible duplicate of C-014/)).toBeInTheDocument();
    expect(within(second).getByText("AI suggestion")).toBeInTheDocument();
    expect(screen.getByText(/The criteria changed after some resumes/)).toBeInTheDocument();
    expect(screen.queryByText("secret evidence quote")).not.toBeInTheDocument();
  });

  it("states that anonymization does not remove bias", async () => {
    stubFetch({ ...approved, ...idle, [LIST]: () => json(200, page([candidate(1)])) });

    renderApp(PATH);

    expect(await screen.findByText(/does not remove it/)).toBeInTheDocument();
    expect(screen.queryByText(/fair/i)).not.toBeInTheDocument();
  });

  it("keeps a candidate that is still processing or failed in the list", async () => {
    stubFetch({
      ...approved,
      ...idle,
      [LIST]: () =>
        json(
          200,
          page([
            candidate(5, { processing_status: "scoring", total: 0, scores: [] }),
            candidate(6, { processing_status: "failed", total: 0, scores: [] }),
          ]),
        ),
    });

    renderApp(PATH);

    expect(await screen.findByText("Scoring")).toBeInTheDocument();
    expect(screen.getByText("Could not process")).toBeInTheDocument();
    expect(screen.getAllByText("Not scored yet")).toHaveLength(2);
  });

  it("filters by stage with the API parameter and resets to the first page", async () => {
    const { calls } = stubFetch({
      ...approved,
      ...idle,
      [LIST]: () => json(200, page([candidate(1)])),
      [`GET /v1/roles/${ROLE_ID}/candidates?limit=100&offset=0&filter%5Bstage%5D=interview`]: () =>
        json(200, page([])),
    });
    renderApp(PATH);

    await userEvent.click(await screen.findByLabelText("Hiring stage"));
    await userEvent.click(await screen.findByRole("option", { name: "Interview" }));

    expect(await screen.findByText("No candidates are in this hiring stage.")).toBeInTheDocument();
    expect(calls.at(-1)?.path).toContain("filter%5Bstage%5D=interview");
  });

  it("pages with limit and offset", async () => {
    const next = `GET /v1/roles/${ROLE_ID}/candidates?limit=100&offset=100`;
    stubFetch({
      ...approved,
      ...idle,
      [LIST]: () => json(200, page([candidate(1)], 150)),
      [next]: () => json(200, page([candidate(2)], 150, 100)),
    });
    renderApp(PATH);

    expect(await screen.findByText("1 to 1 of 150")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Next page" }));

    expect(await screen.findByText("C-002")).toBeInTheDocument();
    expect(screen.getByText("101 to 101 of 150")).toBeInTheDocument();
  });

  it("explains a list that cannot load and offers a retry", async () => {
    stubFetch({ ...approved, ...idle, [LIST]: networkDown });

    renderApp(PATH);

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach the server");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("reports queue progress", async () => {
    stubFetch({
      ...approved,
      [QUEUE]: () => json(200, { data: [], waiting: 12, running: 4 }),
      [LIST]: () => json(200, page([])),
    });

    renderApp(PATH);

    expect(await screen.findByText(/12 waiting, 4 running/)).toBeInTheDocument();
  });
});

const COST = "GET /v1/cost-log?limit=1";
const budget = (allowed: boolean) => () =>
  json(200, {
    budget: { spent_usd: "1.00", limit_usd: "8.00", mode: "live", model_actions_allowed: allowed },
    data: [],
    page: { next_cursor: null, has_more: false },
  });
const RESCORE = `POST /v1/roles/${ROLE_ID}:rescore`;

describe("re-score", () => {
  const stale = () => json(200, page([candidate(1, { stale: true })]));

  it("posts the rescore and reports queued and skipped", async () => {
    const { calls } = stubFetch({
      ...approved,
      ...idle,
      [LIST]: stale,
      [COST]: budget(true),
      [RESCORE]: () => json(202, { job_ids: [41, 42], skipped_candidate_nos: [7] }),
    });
    renderApp(PATH);

    await userEvent.click(await screen.findByRole("button", { name: "Re-score" }));

    expect(await screen.findByText("Re-scoring 2 candidates; 1 skipped")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST" && c.path.endsWith(":rescore"))).toBe(true);
  });

  it("explains a refusal", async () => {
    stubFetch({
      ...approved,
      ...idle,
      [LIST]: stale,
      [COST]: budget(true),
      [RESCORE]: () =>
        json(409, {
          error: { code: "budget_reached", message: "x", details: {}, request_id: null },
        }),
    });
    renderApp(PATH);

    await userEvent.click(await screen.findByRole("button", { name: "Re-score" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("AI budget has been reached");
  });

  it("is disabled when the budget blocks model actions", async () => {
    stubFetch({ ...approved, ...idle, [LIST]: stale, [COST]: budget(false) });
    renderApp(PATH);

    const button = await screen.findByRole("button", { name: "Re-score" });
    await vi.waitFor(() => {
      expect(button).toBeDisabled();
    });
  });
});

describe("ranked list filters and navigation", () => {
  const rows = () =>
    json(
      200,
      page([
        candidate(1, { scores: [cell("c1", "Python experience", { flag_reason: "vague" })] }),
        candidate(2, { scores: [cell("c1", "Python experience", { override_score: 4 })] }),
        candidate(3),
      ]),
    );

  it("shows flagged candidates only", async () => {
    stubFetch({ ...approved, ...idle, [LIST]: rows });
    renderApp(PATH);

    await userEvent.click(await screen.findByLabelText("Needs a look only"));

    expect(screen.getByText("C-001")).toBeInTheDocument();
    expect(screen.queryByText("C-002")).not.toBeInTheDocument();
    expect(screen.queryByText("C-003")).not.toBeInTheDocument();
  });

  it("shows candidates with overrides only, and says when none match", async () => {
    stubFetch({ ...approved, ...idle, [LIST]: rows });
    renderApp(PATH);

    await userEvent.click(await screen.findByLabelText("Changed by recruiter"));
    expect(screen.getByText("C-002")).toBeInTheDocument();
    expect(screen.queryByText("C-001")).not.toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Needs a look only"));
    expect(screen.getByText("No candidates on this page match the filters.")).toBeInTheDocument();
  });

  it("links each label to the candidate detail", async () => {
    stubFetch({ ...approved, ...idle, [LIST]: rows });
    renderApp(PATH);

    const link = await screen.findByRole("link", { name: "C-001" });

    expect(link).toHaveAttribute("href", "/candidates/30000000-0000-4000-8000-000000000001");
  });

  it("enables Compare only for two to four selected candidates", async () => {
    const five = () => json(200, page([1, 2, 3, 4, 5].map((n) => candidate(n))));
    stubFetch({ ...approved, ...idle, [LIST]: five });
    renderApp(PATH);

    const box = async (no: number) =>
      screen.findByRole("checkbox", { name: `Select C-00${no} to compare` });
    const compare = () => screen.getByRole("button", { name: "Compare" });

    await userEvent.click(await box(1));
    expect(compare()).toBeDisabled();
    expect(screen.getByText(/1 selected/)).toBeInTheDocument();

    await userEvent.click(await box(2));
    expect(compare()).toBeEnabled();
    expect(screen.getByText(/2 selected/)).toBeInTheDocument();

    for (const n of [3, 4, 5]) await userEvent.click(await box(n));
    expect(compare()).toBeDisabled();
  });
});

describe("resume upload", () => {
  const pdf = new File(["a"], "resume-1.pdf", { type: "application/pdf" });
  const txt = new File(["b"], "notes.txt", { type: "text/plain" });

  it("sends the files as multipart and lists one result per file", async () => {
    const { calls } = stubFetch({
      ...approved,
      ...idle,
      [LIST]: () => json(200, page([])),
      [`POST /v1/roles/${ROLE_ID}/resumes`]: () =>
        json(207, {
          results: [
            {
              file_name: "resume-1.pdf",
              status: "accepted",
              candidate_id: "x",
              candidate_no: 14,
              duplicate_of_candidate_no: 9,
              reason: null,
            },
            {
              file_name: "notes.txt",
              status: "rejected",
              candidate_id: null,
              candidate_no: null,
              duplicate_of_candidate_no: null,
              reason: "Only PDF and DOCX files are accepted",
            },
          ],
        }),
    });
    renderApp(PATH);

    await userEvent.upload(await screen.findByLabelText(/Choose files/), [pdf, txt], {
      applyAccept: false,
    });

    expect(await screen.findByText("1 of 2 files uploaded, 1 not uploaded.")).toBeInTheDocument();
    expect(screen.getByText(/Accepted, possible duplicate of C-009/)).toBeInTheDocument();
    expect(
      screen.getByText("Not uploaded: Only PDF and DOCX files are accepted"),
    ).toBeInTheDocument();
    const post = calls.find((c) => c.method === "POST");
    expect(post?.headers.get("Content-Type")).toBeNull();
    expect(post?.headers.get("X-CSRF-Token")).toBe("csrf-abc");
  });

  it("explains a refused upload", async () => {
    stubFetch({
      ...approved,
      ...idle,
      [LIST]: () => json(200, page([])),
      [`POST /v1/roles/${ROLE_ID}/resumes`]: () =>
        json(413, {
          error: { code: "payload_too_large", message: "x", details: {}, request_id: null },
        }),
    });
    renderApp(PATH);

    await userEvent.upload(await screen.findByLabelText(/Choose files/), pdf);

    expect(await screen.findByRole("alert")).toHaveTextContent("too large");
  });

  it("refuses more than 100 files before sending", async () => {
    const { calls } = stubFetch({ ...approved, ...idle, [LIST]: () => json(200, page([])) });
    renderApp(PATH);
    const many = Array.from({ length: 101 }, (_, i) => new File(["x"], `r${i}.pdf`));

    await userEvent.upload(await screen.findByLabelText(/Choose files/), many);

    expect(await screen.findByRole("alert")).toHaveTextContent("at most 100 files");
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });
});
