import { motion, useReducedMotion } from "motion/react";

import { cn } from "@/lib/utils";

import type { Bin } from "./shape";

/** Grows from empty to its share once on mount; no motion for people who asked for none. */
function useGrow() {
  const reduce = useReducedMotion();
  return { duration: reduce ? 0 : 0.3, ease: "easeOut" } as const;
}

/** A horizontal bar for a share of a whole. The caller prints the number, so the bar is never the only signal; without a label it is decorative. */
export function GrowBar({
  percent,
  label,
  className,
}: {
  percent: number;
  label?: string;
  className?: string;
}) {
  const transition = useGrow();
  return (
    <div
      {...(label === undefined
        ? { "aria-hidden": true }
        : {
            role: "progressbar",
            "aria-label": label,
            "aria-valuemin": 0,
            "aria-valuemax": 100,
            "aria-valuenow": percent,
          })}
      className={cn("h-2.5 w-full overflow-hidden rounded-full bg-muted", className)}
    >
      <motion.div
        className="h-full w-full origin-left rounded-full bg-primary"
        initial={{ scaleX: 0 }}
        animate={{ scaleX: percent / 100 }}
        transition={transition}
      />
    </div>
  );
}

/** Counts per stage as labelled bars. Each row prints its count; there is no color scale. */
export function StageBars({ counts }: { counts: { label: string; count: number }[] }) {
  const max = Math.max(1, ...counts.map((c) => c.count));
  return (
    <ul className="flex flex-col gap-2.5">
      {counts.map((c) => (
        <li key={c.label} className="grid grid-cols-[5.5rem_1fr_2rem] items-center gap-3 text-sm">
          <span className="text-muted-foreground">{c.label}</span>
          <GrowBar percent={Math.round((c.count / max) * 100)} />
          <span className="text-right font-mono tabular-nums">{c.count}</span>
        </li>
      ))}
    </ul>
  );
}

function fmt(n: number): string {
  return n.toFixed(1);
}

/**
 * A histogram as CSS columns, with a table for assistive technology. Every column carries one
 * hue and its count: height is the only encoding, so no band is colored by how good it is.
 */
export function Histogram({ bins, caption }: { bins: Bin[]; caption: string }) {
  const transition = useGrow();
  const max = Math.max(1, ...bins.map((b) => b.count));
  return (
    <figure className="flex flex-col gap-2">
      <div aria-hidden="true" className="flex h-44 items-end gap-2 border-b">
        {bins.map((bin) => (
          <div key={bin.from} className="flex h-full min-w-0 flex-1 flex-col justify-end gap-1">
            <span className="text-center font-mono text-xs tabular-nums">{bin.count}</span>
            <motion.div
              className="min-h-px w-full rounded-t-sm bg-primary"
              initial={{ height: 0 }}
              animate={{ height: `${Math.round((bin.count / max) * 100)}%` }}
              transition={transition}
            />
          </div>
        ))}
      </div>
      <div aria-hidden="true" className="flex gap-2">
        {bins.map((bin) => (
          <span
            key={bin.from}
            className="min-w-0 flex-1 text-center font-mono text-xs leading-tight text-muted-foreground"
          >
            {fmt(bin.from)}
            {bin.to !== bin.from && (
              <>
                <br />
                to {fmt(bin.to)}
              </>
            )}
          </span>
        ))}
      </div>
      <div className="sr-only">
        <table>
          <caption>{caption}</caption>
          <thead>
            <tr>
              <th scope="col">Weighted total from</th>
              <th scope="col">to</th>
              <th scope="col">Candidates</th>
            </tr>
          </thead>
          <tbody>
            {bins.map((bin) => (
              <tr key={bin.from}>
                <td>{fmt(bin.from)}</td>
                <td>{fmt(bin.to)}</td>
                <td>{bin.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <figcaption className="text-xs text-muted-foreground">{caption}</figcaption>
    </figure>
  );
}
