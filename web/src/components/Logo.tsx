import { cn } from "@/lib/utils";

/** The HireKit mark and wordmark (Design.md section 2): a case with a check, "Kit" in italic serif. */
export function Logo({ wordmarkClassName }: { wordmarkClassName?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-primary">
      <svg width="28" height="24" viewBox="88 58 96 80" aria-hidden="true" focusable="false">
        <path
          d="M116 76V70a6 6 0 0 1 6-6h26a6 6 0 0 1 6 6v6"
          fill="none"
          stroke="currentColor"
          strokeWidth="6"
          strokeLinecap="round"
        />
        <rect x="93" y="76" width="84" height="58" rx="10" fill="currentColor" />
        <polyline
          points="116,106 129,119 154,92"
          fill="none"
          className="stroke-primary-foreground"
          strokeWidth="8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span
        className={cn(
          "font-display text-2xl leading-none font-medium tracking-tight text-foreground",
          wordmarkClassName,
        )}
      >
        Hire<em className="text-primary">Kit</em>
      </span>
    </span>
  );
}
