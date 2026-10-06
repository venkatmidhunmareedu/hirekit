import { vi } from "vitest";

export const session = {
  user: {
    id: "00000000-0000-4000-8000-000000000001",
    name: "Riya",
    email: "riya@example.com",
    role: "recruiter",
  },
  csrf_token: "csrf-abc",
};

export function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function unauthenticated(): Response {
  return json(401, {
    error: { code: "unauthenticated", message: "sign in required", details: {}, request_id: null },
  });
}

export interface Call {
  method: string;
  path: string;
  headers: Headers;
  body: string | null;
}

/**
 * Replaces global fetch. `routes` is keyed "METHOD /path"; a handler returns a
 * Response, or throws to simulate a network failure. An unlisted request fails
 * the test, so no test can reach a real server.
 */
export function stubFetch(routes: Record<string, () => Response>) {
  const calls: Call[] = [];
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const method = init?.method ?? "GET";
    const path = input instanceof Request ? input.url : String(input);
    calls.push({
      method,
      path,
      headers: new Headers(init?.headers),
      body: typeof init?.body === "string" ? init.body : null,
    });
    const handler = routes[`${method} ${path}`];
    if (!handler) return Promise.reject(new Error(`unstubbed request: ${method} ${path}`));
    try {
      return Promise.resolve(handler());
    } catch (error) {
      return Promise.reject(error instanceof Error ? error : new Error("stub failure"));
    }
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

export function networkDown(): never {
  throw new TypeError("Failed to fetch");
}
