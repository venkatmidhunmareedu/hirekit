import { cn } from "@/lib/utils";

/** The highlighter yellow of the `--mark` token as sRGB; the SVG favicon repeats it (Design.md 2.2). */
const HIGHLIGHT = "#f6e46a";

/** The HireKit mark and wordmark (Design.md section 2): a check on a tile, underlined like a highlighted quote. */
export function Logo({
  wordmarkClassName,
  inverse = false,
}: {
  /** Extra classes for the wordmark; `hidden` leaves the mark alone (collapsed rail). */
  wordmarkClassName?: string;
  /** White tile on the deep brand ground. */
  inverse?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
        <rect
          width="32"
          height="32"
          rx="9"
          className={inverse ? "fill-brand-foreground" : "fill-primary"}
        />
        <path
          d="M8 16l4.5 4.5L21 10.5"
          fill="none"
          className={inverse ? "stroke-brand" : "stroke-primary-foreground"}
          strokeWidth="3.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <rect x="8" y="24" width="16" height="3" rx="1.5" fill={HIGHLIGHT} />
      </svg>
      <span
        className={cn(
          "font-sans text-xl leading-none font-semibold tracking-tight",
          inverse ? "text-brand-foreground" : "text-foreground",
          wordmarkClassName,
        )}
      >
        Hire<span className={inverse ? undefined : "text-primary"}>Kit</span>
      </span>
    </span>
  );
}
