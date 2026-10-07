import { Pencil, TriangleAlert } from "lucide-react";
import { type KeyboardEvent, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { StatusTag } from "../../../components/StatusTag";
import { type ScoreCell } from "../api";

/** Score chip (Design.md 7.2): neutral, mono; a changed score shows the AI value struck through. */
export function ScoreChip({ model, override }: { model: number | null; override: number | null }) {
  if (override !== null) {
    return (
      <Badge variant="outline" className="h-6 gap-1.5 px-2 font-mono text-xs">
        <Pencil aria-hidden="true" />
        <span className="mono">{override} / 4</span>
        {model !== null && (
          <s className="mono text-muted-foreground">
            <span className="sr-only">AI value </span>
            {model}
          </s>
        )}
      </Badge>
    );
  }
  if (model === null) {
    return (
      <Badge variant="outline" className="h-6 px-2 text-xs text-muted-foreground">
        Not scored
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="mono h-6 px-2 font-mono text-xs">
      {model} / 4
    </Badge>
  );
}

const SEGMENTS = [1, 2, 3, 4];

/**
 * Four-segment score meter: filled segments are the score. With `onPick` the segments are a radio
 * group (arrow keys move focus, Enter, Space or a click picks, which opens the change-score flow);
 * without it the meter is a read-only image. A changed score shows the AI value beside it.
 */
export function ScoreMeter({
  model,
  override,
  name,
  onPick,
}: {
  model: number | null;
  override: number | null;
  name: string;
  onPick?: ((score: number) => void) | undefined;
}) {
  const score = override ?? model;
  const label = score === null ? "Not scored" : `Score ${score} of 4`;
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const segments = SEGMENTS.map((n) => (
    <span
      key={n}
      className={cn(
        "h-3 w-9 rounded-sm",
        score !== null && n <= score ? "bg-primary" : "bg-border",
      )}
    />
  ));
  const readout = (
    <>
      <span className="font-mono text-xl font-semibold tabular-nums">
        {score ?? "-"}
        <span className="text-sm font-normal text-muted-foreground"> / 4</span>
      </span>
      {override !== null && model !== null && (
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <Pencil aria-hidden="true" className="size-3" />
          <s className="font-mono">
            <span className="sr-only">AI value </span>
            {model}
          </s>
        </span>
      )}
    </>
  );
  if (!onPick) {
    return (
      <div className="flex items-center gap-3">
        <div role="img" aria-label={label} className="flex gap-1">
          {segments}
        </div>
        {readout}
      </div>
    );
  }
  const tabbable = score !== null && score >= 1 ? score : 1;
  const move = (event: KeyboardEvent, from: number) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    if (step === undefined) return;
    event.preventDefault();
    refs.current[(from - 1 + step + 4) % 4]?.focus();
  };
  return (
    <div className="flex items-center gap-3">
      <div
        role="radiogroup"
        aria-label={`${label}, change score for ${name}`}
        className="flex gap-1"
      >
        {SEGMENTS.map((n) => (
          <button
            key={n}
            ref={(el) => {
              refs.current[n - 1] = el;
            }}
            type="button"
            role="radio"
            aria-checked={score === n}
            aria-label={`Set score to ${n}`}
            tabIndex={n === tabbable ? 0 : -1}
            title={`Change score to ${n}`}
            onClick={() => {
              onPick(n);
            }}
            onKeyDown={(event) => {
              move(event, n);
            }}
            className="group flex h-8 cursor-pointer items-center rounded-sm focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            <span
              className={cn(
                "h-3 w-9 rounded-sm group-hover:ring-2 group-hover:ring-primary/40",
                score !== null && n <= score ? "bg-primary" : "bg-border",
              )}
            />
          </button>
        ))}
      </div>
      {readout}
    </div>
  );
}

/** The quote the code verified in the anonymized text, or null for no evidence, failed or flagged. */
export function verifiedQuote(cell: ScoreCell): string | null {
  if (cell.flag_reason || cell.status !== "scored") return null;
  return cell.quote?.trim() ? cell.quote : null;
}

const SOURCE_LABEL: Record<ScoreCell["source"], string> = {
  model_suggestion: "AI suggestion",
  no_evidence_found: "AI suggestion",
  recruiter_override: "Changed by recruiter",
  failed: "Scoring failed",
};

export function sourceLabel(cell: ScoreCell): string {
  return SOURCE_LABEL[cell.source];
}

/**
 * Evidence block (Design.md 7.3): verified quote, no evidence found, or needs a look. Yellow is reserved
 * for the highlight in the resume, so the quote is a rule and italics; every state has an icon and words.
 */
export function EvidenceBlock({
  cell,
  onLocate,
}: {
  cell: ScoreCell;
  /** Clicking the quote finds it in the resume; the Show in resume button is the keyboard route. */
  onLocate?: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  if (cell.flag_reason) {
    return (
      <div className="flex flex-col items-start gap-2">
        <StatusTag tone="warning">Needs a look</StatusTag>
        <p>
          The AI&apos;s quote was not found in the resume. It was replaced with no evidence found.
        </p>
        <p className="text-muted-foreground">{cell.flag_reason}</p>
      </div>
    );
  }
  if (cell.status === "failed") {
    return (
      <p className="flex items-center gap-2">
        <TriangleAlert aria-hidden="true" className="size-4 shrink-0 text-warn" />
        Scoring failed for this criterion. Re-score from the ranked list.
      </p>
    );
  }
  const quote = verifiedQuote(cell);
  if (!quote) {
    return <StatusTag tone="neutral">No evidence found</StatusTag>;
  }
  return (
    <div className="flex flex-col items-start gap-2">
      <StatusTag tone="success">Verified</StatusTag>
      <QuoteBox quote={quote} clamp={!expanded} onLocate={onLocate} />
      {quote.length > 160 && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 px-2"
          aria-expanded={expanded}
          onClick={() => {
            setExpanded(!expanded);
          }}
        >
          {expanded ? "Show less" : "Show more"}
        </Button>
      )}
    </div>
  );
}

/** The verified quote. With `onLocate` the whole box finds the quote in the resume. */
function QuoteBox({
  quote,
  clamp,
  onLocate,
}: {
  quote: string;
  clamp: boolean;
  onLocate: (() => void) | undefined;
}) {
  const classes = cn(
    "w-full border-l-2 border-primary/40 py-1 pl-3 text-left font-display text-base text-foreground/80 italic",
    clamp && "line-clamp-3",
  );
  if (!onLocate) return <blockquote className={classes}>&ldquo;{quote}&rdquo;</blockquote>;
  return (
    <button
      type="button"
      title="Find this quote in the resume"
      onClick={onLocate}
      className={cn(
        classes,
        "cursor-pointer focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
      )}
    >
      &ldquo;{quote}&rdquo;
    </button>
  );
}
