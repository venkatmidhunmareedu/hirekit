import { Pencil, TriangleAlert } from "lucide-react";
import { useState } from "react";

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
 * Evidence block (Design.md 7.3): verified quote, no evidence found, or needs a look. The
 * quote carries the reserved highlighter; every state has an icon and words.
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
  if (cell.status === "no_evidence" || !cell.quote) {
    return <StatusTag tone="neutral">No evidence found</StatusTag>;
  }
  return (
    <div className="flex flex-col items-start gap-2">
      <StatusTag tone="success">Verified</StatusTag>
      <QuoteBox quote={cell.quote} clamp={!expanded} onLocate={onLocate} />
      {cell.quote.length > 160 && (
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

/** The verified quote in the highlighter. With `onLocate` the whole box finds the quote in the resume. */
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
    "w-full rounded-md bg-mark px-3 py-2 text-left font-display text-base text-mark-foreground italic",
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
