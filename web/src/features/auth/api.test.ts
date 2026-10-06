import { afterEach, describe, expect, it } from "vitest";

import { ApiError, setCsrfToken } from "../../lib/api";
import { json, networkDown, session, stubFetch, unauthenticated } from "../../test/fetch";

import { getCurrentUser, login, logout } from "./api";

afterEach(() => {
  setCsrfToken(null);
});

describe("auth api", () => {
  it("login posts the credentials as JSON with the cookie and returns the session", async () => {
    const { calls } = stubFetch({ "POST /v1/auth/login": () => json(200, session) });

    const result = await login("riya@example.com", "pw");

    expect(result).toEqual(session);
    expect(calls[0]?.body).toBe(JSON.stringify({ email: "riya@example.com", password: "pw" }));
    expect(calls[0]?.headers.get("Content-Type")).toBe("application/json");
  });

  it("sends the cookie on every call", async () => {
    const { fetchMock } = stubFetch({ "GET /v1/auth/me": () => json(200, session) });

    await getCurrentUser();

    expect(fetchMock.mock.calls[0]?.[1]?.credentials).toBe("same-origin");
  });

  it("does not send a CSRF header on GET", async () => {
    const { calls } = stubFetch({ "GET /v1/auth/me": () => json(200, session) });

    await getCurrentUser();

    expect(calls[0]?.headers.has("X-CSRF-Token")).toBe(false);
  });

  it("sends the CSRF token from /me on logout", async () => {
    const { calls } = stubFetch({
      "GET /v1/auth/me": () => json(200, session),
      "POST /v1/auth/logout": () => new Response(null, { status: 204 }),
    });
    await getCurrentUser();

    await logout();

    expect(calls[1]?.headers.get("X-CSRF-Token")).toBe("csrf-abc");
  });

  it("sends the CSRF token from login on a later POST", async () => {
    const { calls } = stubFetch({
      "POST /v1/auth/login": () => json(200, session),
      "POST /v1/auth/logout": () => new Response(null, { status: 204 }),
    });
    await login("riya@example.com", "pw");

    await logout();

    expect(calls[1]?.headers.get("X-CSRF-Token")).toBe("csrf-abc");
  });

  it("forgets the CSRF token after logout", async () => {
    const { calls } = stubFetch({
      "GET /v1/auth/me": () => json(200, session),
      "POST /v1/auth/logout": () => new Response(null, { status: 204 }),
    });
    await getCurrentUser();
    await logout();

    await logout();

    expect(calls[2]?.headers.has("X-CSRF-Token")).toBe(false);
  });

  it("raises ApiError 401 with the server code on a wrong password", async () => {
    stubFetch({ "POST /v1/auth/login": unauthenticated });

    const failure = await login("riya@example.com", "bad").catch((e: unknown) => e);

    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({ status: 401, code: "unauthenticated" });
  });

  it("raises ApiError with status 0 and code network when fetch rejects", async () => {
    stubFetch({ "GET /v1/auth/me": networkDown });

    const failure = await getCurrentUser().catch((e: unknown) => e);

    expect(failure).toMatchObject({ status: 0, code: "network" });
  });

  it("raises ApiError when an error body is not the envelope", async () => {
    stubFetch({
      "GET /v1/auth/me": () => new Response("<html>bad gateway</html>", { status: 502 }),
    });

    const failure = await getCurrentUser().catch((e: unknown) => e);

    expect(failure).toMatchObject({ status: 502, code: "http_error" });
  });

  it("rejects a 200 whose body is not a session", async () => {
    stubFetch({ "GET /v1/auth/me": () => json(200, { user: null }) });

    const failure = await getCurrentUser().catch((e: unknown) => e);

    expect(failure).toMatchObject({ code: "bad_response" });
  });

  it("rejects a 200 whose body is not JSON", async () => {
    stubFetch({ "GET /v1/auth/me": () => new Response("ok", { status: 200 }) });

    const failure = await getCurrentUser().catch((e: unknown) => e);

    expect(failure).toMatchObject({ code: "bad_response" });
  });
});
