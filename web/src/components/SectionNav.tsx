import { motion } from "motion/react";
import { type ComponentType, useId } from "react";

import { cn } from "@/lib/utils";

export interface NavItem {
  id: string;
  label: string;
  /** Shown beside the label; also read out ("Must-have, 6"). */
  count?: number;
  icon?: ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
}

/**
 * A jump navigator for long grouped content. It marks the section in view with a moving bar,
 * bold text and aria-current, so the state is never colour alone. Each entry is a button; the
 * caller decides what a jump does (scroll the page or a region).
 */
export function SectionNav({
  label,
  items,
  active,
  onSelect,
  orientation = "row",
  className,
}: {
  label: string;
  items: NavItem[];
  active: string | null;
  onSelect: (id: string) => void;
  orientation?: "row" | "column";
  className?: string;
}) {
  const group = useId();
  const column = orientation === "column";
  return (
    <nav aria-label={label} className={className}>
      <ul className={cn("flex gap-1", column ? "flex-col" : "flex-row overflow-x-auto")}>
        {items.map((item) => {
          const current = item.id === active;
          const Icon = item.icon;
          return (
            <li key={item.id}>
              <button
                type="button"
                aria-current={current ? "true" : undefined}
                onClick={() => {
                  onSelect(item.id);
                }}
                className={cn(
                  "relative flex min-h-10 w-full items-center gap-2 rounded-md px-3 text-left text-sm whitespace-nowrap outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50",
                  current ? "font-semibold text-foreground" : "text-muted-foreground",
                )}
              >
                {current && (
                  <motion.span
                    layoutId={`nav-${group}`}
                    aria-hidden="true"
                    className={cn(
                      "absolute rounded-full bg-primary",
                      column ? "inset-y-2 left-0 w-1" : "inset-x-3 bottom-0 h-1",
                    )}
                    transition={{ type: "spring", stiffness: 500, damping: 40 }}
                  />
                )}
                {Icon && <Icon aria-hidden className="size-4 shrink-0" />}
                <span className="min-w-0 flex-1">{item.label}</span>
                {item.count !== undefined && (
                  <span className="rounded-full bg-muted px-2 font-mono text-xs text-foreground tabular-nums">
                    <span className="sr-only">, </span>
                    {item.count}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
