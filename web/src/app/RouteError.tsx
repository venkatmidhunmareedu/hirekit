import { type ErrorComponentProps, useRouter } from "@tanstack/react-router";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

import { Notice } from "../components/Notice";
import { ApiError } from "../lib/api";

/** Error state with a retry (Design.md section 11). Never signs the user out. */
export function RouteError({ error, reset }: ErrorComponentProps) {
  const router = useRouter();
  const unreachable = error instanceof ApiError && error.status === 0;

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <Card className="w-full max-w-sm gap-4 px-5">
        <Notice tone="danger">
          {unreachable
            ? "Could not reach the server. Check your connection and try again."
            : "Something went wrong. Try again in a moment."}
        </Notice>
        <Button
          type="button"
          className="h-10 px-4"
          onClick={() => {
            reset();
            void router.invalidate();
          }}
        >
          Try again
        </Button>
      </Card>
    </main>
  );
}
