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
    <header className="page-header">
      {breadcrumb && <div className="breadcrumb">{breadcrumb}</div>}
      <div className="row-between">
        <h1>{title}</h1>
        {action && <div className="actions no-print">{action}</div>}
      </div>
      {purpose && <p className="page-header-purpose">{purpose}</p>}
    </header>
  );
}
