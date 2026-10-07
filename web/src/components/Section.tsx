import type { ReactNode } from "react";

/** A page section: a heading and the content. No box and no rule; cards are for independent objects. */
export function Section({
  id,
  title,
  description,
  action,
  children,
}: {
  id: string;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={id}>{title}</h2>
        {action}
      </div>
      {description && (
        <p className="-mt-1 max-w-prose text-sm text-muted-foreground">{description}</p>
      )}
      {children}
    </section>
  );
}
