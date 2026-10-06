import type { ReactNode } from "react";

import { Separator } from "@/components/ui/separator";

/** A page section: a rule, a heading and the content. No box; cards are for independent objects. */
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
    <section aria-labelledby={id} className="flex flex-col gap-4">
      <Separator />
      <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
        <h2 id={id} className="text-xl font-medium">
          {title}
        </h2>
        {action}
      </div>
      {description && <p className="max-w-prose text-muted-foreground">{description}</p>}
      {children}
    </section>
  );
}
