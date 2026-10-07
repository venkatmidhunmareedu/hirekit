import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { setCsrfToken } from "../../lib/api";
import { json, session, stubFetch } from "../../test/fetch";
import { renderApp } from "../../test/render";

afterEach(() => {
  setCsrfToken(null);
});

const ID = "10000000-0000-4000-8000-000000000001";
const role = (status: string, criteria: unknown[] = []) => ({
  id: ID,
  title: "Backend engineer",
  job_description: "Build.",
  status,
  criteria_version: 1,
  created_at: "2026-09-30T09:00:00Z",
  updated_at: "2026-09-30T09:00:00Z",
  criteria,
});
const cell = (flag: string | null) => ({
  criterion_id: "c1",
  criterion_name: "Python",
  kind: "must_have",
  status: "scored",
  model_score: 3,
  override_score: null,
  source: "model_suggestion",
  stale: false,
  quote: "q",
  flag_reason: flag,
  override_note: null,
});
const cand = (no: number, flag: string | null = null, status = "done") => ({
  id: `30000000-0000-4000-8000-00000000000${no}`,
  candidate_no: no,
  stage: "screened",
  processing_status: status,
  failure_reason: null,
  total: 5,
  must_have_covered: 1,
  must_have_total: 1,
  stale: false,
  duplicate_of_candidate_no: null,
  scores: [cell(flag)],
});
const ranked = (data: unknown[]) => ({
  data,
  page: { limit: 100, offset: 0, total: data.length },
});
const base = (detail: unknown) => ({
  "GET /v1/auth/me": () => json(200, session),
  [`GET /v1/roles/${ID}`]: () => json(200, detail),
});
const LIST = `GET /v1/roles/${ID}/candidates?limit=100&offset=0`;
const QUEUE = `GET /v1/roles/${ID}/queue`;

function progress() {
  return within(screen.getByRole("navigation", { name: "Role progress" }));
}

describe("role header", () => {
  it("draft with no criteria: propose is next, later steps say why they are locked", async () => {
    stubFetch(base(role("draft")));
    renderApp(`/roles/${ID}`);
    expect(await screen.findByText(/Next up:/)).toHaveTextContent("Propose criteria");
    expect(progress().getByText("None yet")).toBeInTheDocument();
    expect(progress().getAllByText("Approve criteria first")).toHaveLength(2);
  });

  it("approved with no candidates: upload is next", async () => {
    stubFetch({
      ...base(role("approved", [])),
      [QUEUE]: () => json(200, { data: [], waiting: 0, running: 0 }),
      [LIST]: () => json(200, ranked([])),
      [`GET /v1/roles/${ID}/kit`]: () => json(404, { error: { code: "not_found" } }),
    });
    renderApp(`/roles/${ID}/kit`);
    expect(await screen.findByRole("link", { name: "Upload resumes" })).toBeInTheDocument();
    expect(await progress().findByText("None uploaded")).toBeInTheDocument();
    expect(await progress().findByText("Not generated")).toBeInTheDocument();
  });

  it("counts scored, needs-a-look and processing candidates", async () => {
    stubFetch({
      ...base(role("approved", [])),
      [QUEUE]: () => json(200, { data: [], waiting: 1, running: 1 }),
      [LIST]: () =>
        json(200, ranked([cand(1), cand(2, "Quote not found"), cand(3, null, "scoring")])),
      [`GET /v1/roles/${ID}/kit`]: () => json(404, { error: { code: "not_found" } }),
    });
    renderApp(`/roles/${ID}`);
    await screen.findByRole("navigation", { name: "Role progress" });
    expect(await progress().findByText("2 scored, 1 need a look, 2 processing")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Processing 2 resumes");
  });
});
