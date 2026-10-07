import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { setCsrfToken } from "../../lib/api";
import { json, networkDown, session, stubFetch } from "../../test/fetch";
import { renderApp } from "../../test/render";

afterEach(() => {
  setCsrfToken(null);
});

const ROLE_ID = "10000000-0000-4000-8000-000000000001";
const CRITERION_ID = "20000000-0000-4000-8000-000000000001";

const role = {
  id: ROLE_ID,
  title: "Backend engineer",
  job_description: "Build and run our payments API.\nOn call weekly.",
  status: "draft",
  criteria_version: 1,
  created_at: "2026-09-30T09:00:00Z",
  updated_at: "2026-09-30T09:00:00Z",
};

const rubric = [0, 1, 2, 3, 4].map((level) => ({ level, descriptor: `Level ${level} text` }));
const criterion = {
  id: CRITERION_ID,
  name: "Python experience",
  kind: "must_have",
  weight: 3,
  position: 1,
  rubric,
};
const detail = { ...role, criteria: [criterion] };

const me = { "GET /v1/auth/me": () => json(200, session) };

describe("role list", () => {
  it("lists roles with their status", async () => {
    stubFetch({
      ...me,
      "GET /v1/roles": () =>
        json(200, { data: [role, { ...role, id: "x", title: "Designer", status: "approved" }] }),
    });

    renderApp("/");

    const link = await screen.findByRole("link", { name: "Backend engineer" });
    expect(link).toHaveAttribute("href", `/roles/${ROLE_ID}`);
    expect(screen.getByText("Approved")).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Approve criteria" })).toHaveAttribute(
      "href",
      `/roles/${ROLE_ID}`,
    );
    expect(screen.getByRole("link", { name: "Open candidates" })).toHaveAttribute(
      "href",
      "/roles/x/candidates",
    );
  });

  it("shows an empty state and an error with a retry", async () => {
    stubFetch({ ...me, "GET /v1/roles": () => json(200, { data: [] }) });
    renderApp("/");
    expect(await screen.findByText(/No roles yet/)).toBeInTheDocument();
  });

  it("explains a network failure", async () => {
    stubFetch({ ...me, "GET /v1/roles": networkDown });
    renderApp("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach the server");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("rejects a body that breaks the contract", async () => {
    stubFetch({ ...me, "GET /v1/roles": () => json(200, { data: [{ id: 1 }] }) });
    renderApp("/");
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
  });

  it("creates a role from a title and job description, then opens its setup", async () => {
    const { calls } = stubFetch({
      ...me,
      "GET /v1/roles": () => json(200, { data: [] }),
      "POST /v1/roles": () => json(201, role),
      [`GET /v1/roles/${ROLE_ID}`]: () => json(200, { ...role, criteria: [] }),
    });
    const router = renderApp("/");

    await userEvent.click(await screen.findByRole("button", { name: "New role" }));
    const create = await screen.findByRole("button", { name: "Create role" });
    expect(create).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Role title"), "  Backend engineer ");
    await userEvent.type(screen.getByLabelText("Job description"), "Build things");
    await userEvent.click(create);

    expect(await screen.findByRole("heading", { name: "Backend engineer" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(`/roles/${ROLE_ID}`);
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toBe(
      JSON.stringify({ title: "Backend engineer", job_description: "Build things" }),
    );
    expect(post?.headers.get("X-CSRF-Token")).toBe("csrf-abc");
  });

  it("says why a role could not be created", async () => {
    stubFetch({
      ...me,
      "GET /v1/roles": () => json(200, { data: [] }),
      "POST /v1/roles": () =>
        json(403, { error: { code: "forbidden", message: "x", details: {}, request_id: null } }),
    });
    renderApp("/");

    await userEvent.click(await screen.findByRole("button", { name: "New role" }));
    await userEvent.type(await screen.findByLabelText("Role title"), "T");
    await userEvent.type(screen.getByLabelText("Job description"), "D");
    await userEvent.click(screen.getByRole("button", { name: "Create role" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Your role cannot do this.");
  });
});

describe("role setup", () => {
  it("shows the job description as text and the draft banner", async () => {
    stubFetch({ ...me, [`GET /v1/roles/${ROLE_ID}`]: () => json(200, detail) });
    renderApp(`/roles/${ROLE_ID}`);

    expect(await screen.findByText(/Build and run our payments API/)).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText(/Next up:/)).toHaveTextContent("Approve criteria");
    expect(screen.getByLabelText("Name")).toHaveValue("Python experience");
    expect(screen.getByLabelText("Score 4 looks like")).toHaveValue("Level 4 text");
    expect(screen.getAllByText("Approve criteria first")).toHaveLength(2);
    expect(screen.getByText("Needs approval").closest("[aria-current]")).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(screen.queryByRole("link", { name: /Candidates/ })).not.toBeInTheDocument();
  });

  it("reports a missing role", async () => {
    stubFetch({
      ...me,
      [`GET /v1/roles/${ROLE_ID}`]: () =>
        json(404, { error: { code: "not_found", message: "x", details: {}, request_id: null } }),
    });
    renderApp(`/roles/${ROLE_ID}`);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This record is missing or you cannot see it.",
    );
  });

  it("saves edited criteria by id, then approves with the version it saw after a confirmation", async () => {
    let current = detail;
    const { calls } = stubFetch({
      ...me,
      [`GET /v1/roles/${ROLE_ID}`]: () => json(200, current),
      [`PUT /v1/roles/${ROLE_ID}/criteria`]: () => {
        current = {
          ...detail,
          criteria_version: 2,
          updated_at: "2026-09-30T10:00:00Z",
          criteria: [{ ...criterion, name: "Python and Go" }],
        };
        return json(200, current);
      },
      [`POST /v1/roles/${ROLE_ID}/approve`]: () => {
        current = { ...current, status: "approved" };
        return json(200, current);
      },
    });
    renderApp(`/roles/${ROLE_ID}`);

    const name = await screen.findByLabelText("Name");
    const saveButton = screen.getByRole("button", { name: "Save draft" });
    const approveButton = screen.getByRole("button", { name: "Approve criteria" });
    expect(saveButton).toBeDisabled();
    expect(approveButton).toBeEnabled();

    await userEvent.clear(name);
    await userEvent.type(name, "Python and Go");
    expect(approveButton).toBeDisabled();
    await userEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByLabelText("Name")).toHaveValue("Python and Go");
    });
    const put = calls.find((c) => c.method === "PUT");
    expect(JSON.parse(put?.body ?? "{}")).toEqual({
      criteria: [{ id: CRITERION_ID, name: "Python and Go", kind: "must_have", weight: 3, rubric }],
    });

    await userEvent.click(screen.getByRole("button", { name: "Approve criteria" }));
    const confirm = screen.getByRole("group", { name: "Confirm approval" });
    expect(confirm).toHaveTextContent("unlocks resume upload");
    await userEvent.click(within(confirm).getByRole("button", { name: "Confirm approval" }));

    expect(await screen.findByText("Approved")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Open candidates" })).toHaveAttribute(
      "href",
      `/roles/${ROLE_ID}/candidates`,
    );
    expect(calls.find((c) => c.path.endsWith("/approve"))?.body).toBe(
      JSON.stringify({ criteria_version: 2 }),
    );
  });

  it("explains a criteria_changed conflict on approve", async () => {
    stubFetch({
      ...me,
      [`GET /v1/roles/${ROLE_ID}`]: () => json(200, detail),
      [`POST /v1/roles/${ROLE_ID}/approve`]: () =>
        json(409, {
          error: { code: "criteria_changed", message: "x", details: {}, request_id: null },
        }),
    });
    renderApp(`/roles/${ROLE_ID}`);

    await userEvent.click(await screen.findByRole("button", { name: "Approve criteria" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm approval" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The criteria changed");
  });

  it("adds a criterion with five empty levels and blocks saving until it is complete", async () => {
    stubFetch({ ...me, [`GET /v1/roles/${ROLE_ID}`]: () => json(200, detail) });
    renderApp(`/roles/${ROLE_ID}`);

    await userEvent.click(await screen.findByRole("button", { name: "Add criterion" }));

    expect(screen.getAllByLabelText(/Score \d looks like/)).toHaveLength(10);
    expect(screen.getByText("Give every criterion a name.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();
    expect(screen.getByText("Save your edits first.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve criteria" })).toHaveAccessibleDescription(
      "Save your edits first.",
    );
  });

  it("removes a criterion", async () => {
    stubFetch({ ...me, [`GET /v1/roles/${ROLE_ID}`]: () => json(200, detail) });
    renderApp(`/roles/${ROLE_ID}`);

    await userEvent.click(await screen.findByRole("button", { name: "Remove criterion" }));

    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve criteria" })).toBeDisabled();
  });

  it("loads the proposed criteria when the job has succeeded", async () => {
    let current = { ...detail, criteria: [] as unknown[] };
    stubFetch({
      ...me,
      [`GET /v1/roles/${ROLE_ID}`]: () => json(200, current),
      [`POST /v1/roles/${ROLE_ID}/criteria:propose`]: () => json(202, { job_id: 41 }),
      "GET /v1/jobs/41": () => {
        current = detail;
        return json(200, { id: 41, status: "succeeded" });
      },
    });
    renderApp(`/roles/${ROLE_ID}`);

    await userEvent.click(await screen.findByRole("button", { name: "Propose criteria" }));

    expect(await screen.findByLabelText("Name")).toHaveValue("Python experience");
    expect(screen.queryByLabelText("Proposing criteria")).not.toBeInTheDocument();
  });

  it("shows progress while the proposal runs and cancels it", async () => {
    const { calls } = stubFetch({
      ...me,
      [`GET /v1/roles/${ROLE_ID}`]: () => json(200, { ...detail, criteria: [] }),
      [`POST /v1/roles/${ROLE_ID}/criteria:propose`]: () => json(202, { job_id: 41 }),
      "GET /v1/jobs/41": () => json(200, { id: 41, status: "running" }),
      "POST /v1/jobs/41:cancel": () => json(200, { id: 41, status: "cancelled" }),
    });
    renderApp(`/roles/${ROLE_ID}`);

    await userEvent.click(await screen.findByRole("button", { name: "Propose criteria" }));
    expect(await screen.findByLabelText("Proposing criteria")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() => {
      expect(calls.some((c) => c.path === "/v1/jobs/41:cancel")).toBe(true);
    });
  });

  it("says when the proposal failed", async () => {
    stubFetch({
      ...me,
      [`GET /v1/roles/${ROLE_ID}`]: () => json(200, { ...detail, criteria: [] }),
      [`POST /v1/roles/${ROLE_ID}/criteria:propose`]: () => json(202, { job_id: 41 }),
      "GET /v1/jobs/41": () => json(200, { id: 41, status: "failed" }),
    });
    renderApp(`/roles/${ROLE_ID}`);

    await userEvent.click(await screen.findByRole("button", { name: "Propose criteria" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The proposal did not finish");
  });

  it("explains a refused proposal (budget reached)", async () => {
    stubFetch({
      ...me,
      [`GET /v1/roles/${ROLE_ID}`]: () => json(200, detail),
      [`POST /v1/roles/${ROLE_ID}/criteria:propose`]: () =>
        json(409, {
          error: { code: "budget_reached", message: "x", details: {}, request_id: null },
        }),
    });
    renderApp(`/roles/${ROLE_ID}`);

    await userEvent.click(await screen.findByRole("button", { name: "Propose criteria" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("budget has been reached");
  });
});
