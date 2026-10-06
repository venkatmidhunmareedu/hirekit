import type { ReactNode } from "react";

/** An empty list: what is missing and, when there is one, the next action. */
export function EmptyState({ message, action }: { message: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <p>{message}</p>
      {action}
    </div>
  );
}
