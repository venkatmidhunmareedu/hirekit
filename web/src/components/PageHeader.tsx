import type { ReactNode } from "react";

/** Page title, one line on what the page is for, an optional breadcrumb and a primary-action slot. */
export function PageHeader({
  title,
  purpose,
  breadcrumb,
  action,
}: {
  title: ReactNode;
  purpose?: ReactNode;
  breadcrumb?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-2">
      {breadcrumb && <div className="text-sm text-muted-foreground">{breadcrumb}</div>}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-display text-3xl font-medium">{title}</h1>
        {action && <div className="flex gap-2 print:hidden">{action}</div>}
      </div>
      {purpose && <p className="max-w-prose text-muted-foreground">{purpose}</p>}
    </header>
  );
}
