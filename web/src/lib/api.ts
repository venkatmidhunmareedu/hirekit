/** A failed API call. status 0 means the request never got an answer. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

// The session's CSRF token (api-lld section 4.1). Client-only state, set when
// login or /v1/auth/me returns it, and sent on every non-GET call.
let csrfToken: string | null = null;

/** Remember (or forget, with null) the CSRF token the API issued. */
export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

function errorCode(body: unknown): string | null {
  if (typeof body !== "object" || body === null || !("error" in body)) return null;
  const { error } = body;
  if (typeof error !== "object" || error === null || !("code" in error)) return null;
  return typeof error.code === "string" ? error.code : null;
}

/**
 * The one path to the API. Same-origin (the Vite proxy forwards /v1), so the
 * cookie rides along. Resolves to the parsed JSON body, or undefined on 204;
 * throws ApiError for a non-2xx status or a network failure.
 */
export async function request(method: string, path: string, body?: unknown): Promise<unknown> {
  const headers = new Headers({ Accept: "application/json" });
  if (body !== undefined) headers.set("Content-Type", "application/json");
  if (method !== "GET" && csrfToken !== null) headers.set("X-CSRF-Token", csrfToken);

  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers,
      credentials: "same-origin",
      ...(body !== undefined && { body: JSON.stringify(body) }),
    });
  } catch {
    throw new ApiError(0, "network", "The request did not reach the server");
  }

  if (!response.ok) {
    const parsed: unknown = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      errorCode(parsed) ?? "http_error",
      `HTTP ${response.status}`,
    );
  }
  if (response.status === 204) return undefined;
  return response.json().catch(() => {
    throw new ApiError(response.status, "bad_response", "The response was not JSON");
  });
}
