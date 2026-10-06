import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryHistory } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { setCsrfToken } from "../lib/api";
import { json, networkDown, session, stubFetch, unauthenticated } from "../test/fetch";

import { createAppRouter } from "./router";

afterEach(() => {
  setCsrfToken(null);
});

function renderApp(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createAppRouter(queryClient, createMemoryHistory({ initialEntries: [path] }));
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

describe("budget pill", () => {
  const costLog =
    (spent: string, allowed = true) =>
    () =>
      json(200, {
        budget: {
          spent_usd: spent,
          limit_usd: "8.00",
          mode: "live",
          model_actions_allowed: allowed,
        },
        data: [],
        page: { next_cursor: null, has_more: false },
      });
  const routes = {
    "GET /v1/auth/me": () => json(200, session),
    "GET /v1/roles": () => json(200, { data: [] }),
  };

  it("shows spend against the limit", async () => {
    stubFetch({ ...routes, "GET /v1/cost-log?limit=1": costLog("2.00") });
    renderApp("/");
    expect(await screen.findByText("Budget USD 2.00 of 8.00")).toBeInTheDocument();
  });

  it("warns from 75 percent", async () => {
    stubFetch({ ...routes, "GET /v1/cost-log?limit=1": costLog("6.00") });
    renderApp("/");
    expect(await screen.findByText("Budget USD 6.00 of 8.00, nearly used")).toBeInTheDocument();
  });

  it("says when the budget is reached", async () => {
    stubFetch({ ...routes, "GET /v1/cost-log?limit=1": costLog("8.00", false) });
    renderApp("/");
    expect(await screen.findByText("Budget reached")).toBeInTheDocument();
  });

  it("is not shown to interviewers and makes no cost call", async () => {
    const { calls } = stubFetch({
      "GET /v1/auth/me": () =>
        json(200, { ...session, user: { ...session.user, role: "interviewer" } }),
      "GET /v1/me/candidates": () => json(200, { data: [] }),
    });
    renderApp("/me/candidates");
    await screen.findByText("interviewer");
    expect(screen.queryByText(/Budget/)).not.toBeInTheDocument();
    expect(calls.some((c) => c.path.includes("cost-log"))).toBe(false);
  });
});

describe("route guard", () => {
  it("redirects to sign-in when /v1/auth/me answers 401", async () => {
    stubFetch({ "GET /v1/auth/me": unauthenticated });

    const router = renderApp("/");

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/sign-in");
  });

  it("shows the shell with the user name when signed in", async () => {
    stubFetch({
      "GET /v1/auth/me": () => json(200, session),
      "GET /v1/roles": () => json(200, { data: [] }),
    });

    renderApp("/");

    expect(await screen.findByRole("heading", { name: "Roles" })).toBeInTheDocument();
    expect(screen.getByText("Riya")).toBeInTheDocument();
  });

  it("offers a retry when /me cannot be reached, instead of signing the user out", async () => {
    stubFetch({ "GET /v1/auth/me": networkDown });

    renderApp("/");

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach the server");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("signs out, sends the CSRF header and returns to sign-in", async () => {
    const { calls } = stubFetch({
      "GET /v1/auth/me": () => json(200, session),
      "GET /v1/roles": () => json(200, { data: [] }),
      "POST /v1/auth/logout": () => new Response(null, { status: 204 }),
    });
    const router = renderApp("/");

    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/sign-in");
    });
    expect(calls.find((c) => c.method === "POST")?.headers.get("X-CSRF-Token")).toBe("csrf-abc");
  });

  it("treats a 401 on logout as signed out", async () => {
    stubFetch({
      "GET /v1/auth/me": () => json(200, session),
      "GET /v1/roles": () => json(200, { data: [] }),
      "POST /v1/auth/logout": unauthenticated,
    });
    const router = renderApp("/");

    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/sign-in");
    });
  });

  it("stays signed in and says so when logout cannot reach the server", async () => {
    stubFetch({
      "GET /v1/auth/me": () => json(200, session),
      "GET /v1/roles": () => json(200, { data: [] }),
      "POST /v1/auth/logout": networkDown,
    });
    const router = renderApp("/");

    await userEvent.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not sign out");
    expect(router.state.location.pathname).toBe("/");
  });
});
