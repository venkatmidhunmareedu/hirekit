import { ApiError, request, setCsrfToken } from "../../lib/api";

// Hand-typed from backend/api/openapi.yaml: User, Session, Role_kind.
export type UserRole = "recruiter" | "interviewer";
export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
}
export interface Session {
  user: User;
  csrf_token: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Validate a response body where it enters the app; the contract says Session. */
function parseSession(body: unknown): Session {
  if (isRecord(body) && isRecord(body.user) && typeof body.csrf_token === "string") {
    const { id, name, email, role } = body.user;
    if (
      typeof id === "string" &&
      typeof name === "string" &&
      typeof email === "string" &&
      (role === "recruiter" || role === "interviewer")
    ) {
      return { user: { id, name, email, role }, csrf_token: body.csrf_token };
    }
  }
  throw new ApiError(200, "bad_response", "The session response did not match the contract");
}

async function sessionFrom(call: Promise<unknown>): Promise<Session> {
  const session = parseSession(await call);
  setCsrfToken(session.csrf_token);
  return session;
}

/** POST /v1/auth/login. 401 means a wrong email or password. */
export function login(email: string, password: string): Promise<Session> {
  return sessionFrom(request("POST", "/v1/auth/login", { email, password }));
}

/** GET /v1/auth/me. 401 means nobody is signed in. */
export function getCurrentUser(): Promise<Session> {
  return sessionFrom(request("GET", "/v1/auth/me"));
}

/** POST /v1/auth/logout. A 401 means the session is already gone, which is the goal. */
export async function logout(): Promise<void> {
  try {
    await request("POST", "/v1/auth/logout");
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 401)) throw error;
  }
  setCsrfToken(null);
}
