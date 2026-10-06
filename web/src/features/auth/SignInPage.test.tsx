import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryHistory } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { createAppRouter } from "../../app/router";
import { setCsrfToken } from "../../lib/api";
import { json, networkDown, session, stubFetch, unauthenticated } from "../../test/fetch";

afterEach(() => {
  setCsrfToken(null);
});

function renderSignIn() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createAppRouter(
    queryClient,
    createMemoryHistory({ initialEntries: ["/sign-in"] }),
  );
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

async function submit(email: string, password: string) {
  await userEvent.type(await screen.findByLabelText("Email"), email);
  await userEvent.type(screen.getByLabelText("Password"), password);
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("sign-in screen", () => {
  it("labels both fields and has one primary action", async () => {
    stubFetch({});

    renderSignIn();

    expect(await screen.findByLabelText("Email")).toHaveAttribute("type", "email");
    expect(screen.getByLabelText("Password")).toHaveAttribute("type", "password");
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("signs in and opens the app shell", async () => {
    const { calls } = stubFetch({
      "POST /v1/auth/login": () => json(200, session),
      "GET /v1/auth/me": () => json(200, session),
      "GET /v1/roles": () => json(200, { data: [] }),
    });
    const router = renderSignIn();

    await submit("riya@example.com", "pw");

    expect(await screen.findByRole("heading", { name: "Roles" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/");
    expect(calls[0]?.body).toBe(JSON.stringify({ email: "riya@example.com", password: "pw" }));
  });

  it("explains a wrong email or password and keeps the form", async () => {
    stubFetch({ "POST /v1/auth/login": unauthenticated });
    const router = renderSignIn();

    await submit("riya@example.com", "bad");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The email or password is not right. Check both and try again.",
    );
    expect(router.state.location.pathname).toBe("/sign-in");
    expect(screen.getByLabelText("Email")).toHaveValue("riya@example.com");
  });

  it("explains a network failure and offers another try", async () => {
    stubFetch({ "POST /v1/auth/login": networkDown });
    renderSignIn();

    await submit("riya@example.com", "pw");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Could not reach the server. Check your connection and try again.",
    );
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
    });
  });

  it("explains an unexpected server error", async () => {
    stubFetch({
      "POST /v1/auth/login": () =>
        json(500, { error: { code: "internal", message: "x", details: {} } }),
    });
    renderSignIn();

    await submit("riya@example.com", "pw");

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
  });
});
