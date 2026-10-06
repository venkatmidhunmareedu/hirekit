import { type ErrorComponentProps, useRouter } from "@tanstack/react-router";

import { AlertIcon } from "../components/AlertIcon";
import { ApiError } from "../lib/api";

/** Error state with a retry (Design.md section 11). Never signs the user out. */
export function RouteError({ error, reset }: ErrorComponentProps) {
  const router = useRouter();
  const unreachable = error instanceof ApiError && error.status === 0;

  return (
    <main className="auth-page">
      <div className="card auth-card stack">
        <p role="alert" className="notice notice-danger">
          <AlertIcon />
          <span>
            {unreachable
              ? "Could not reach the server. Check your connection and try again."
              : "Something went wrong. Try again in a moment."}
          </span>
        </p>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => {
            reset();
            void router.invalidate();
          }}
        >
          Try again
        </button>
      </div>
    </main>
  );
}
