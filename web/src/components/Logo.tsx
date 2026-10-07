import { cn } from "@/lib/utils";

/** The HireKit mark and wordmark (Design.md section 2): a case with a check, "Kit" in italic serif. */
export function Logo({
  wordmarkClassName,
  inverse = false,
}: {
  wordmarkClassName?: string;
  /** Light mark and wordmark for the deep brand ground. */
  inverse?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2",
        inverse ? "text-brand-foreground" : "text-primary",
      )}
    >
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
          className={inverse ? "stroke-brand" : "stroke-primary-foreground"}
          strokeWidth="8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span
        className={cn(
          "font-display text-2xl leading-none font-medium tracking-tight",
          inverse ? "text-brand-foreground" : "text-foreground",
          wordmarkClassName,
        )}
      >
        Hire<em className={inverse ? undefined : "text-primary"}>Kit</em>
      </span>
    </span>
  );
}
