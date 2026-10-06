import type { ReactNode } from "react";

/** An empty list: what is missing and, when there is one, the next action. */
export function EmptyState({ message, action }: { message: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-lg border border-dashed border-input bg-card px-5 py-6 text-sm text-muted-foreground">
      <p className="max-w-prose text-foreground">{message}</p>
      {action}
    </div>
  );
}
