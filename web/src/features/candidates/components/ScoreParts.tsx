import { useState } from "react";

import { Icon } from "../../../components/Icon";
import { type ScoreCell } from "../api";

/** Score chip (Design.md 7.2): neutral, mono; an override shows the model value struck through. */
export function ScoreChip({ model, override }: { model: number | null; override: number | null }) {
  if (override !== null) {
    return (
      <span className="chip">
        <Icon name="pencil" />
        <span className="mono">{override} / 4</span>
        {model !== null && (
          <s className="mono muted">
            <span className="sr-only">model value </span>
            {model}
          </s>
        )}
      </span>
    );
  }
  if (model === null) return <span className="chip muted">Not scored</span>;
  return <span className="chip mono">{model} / 4</span>;
}

const SOURCE_LABEL: Record<ScoreCell["source"], string> = {
  model_suggestion: "Model suggestion",
  no_evidence_found: "Model suggestion",
  recruiter_override: "Recruiter override",
  failed: "Scoring failed",
};

export function sourceLabel(cell: ScoreCell): string {
  return SOURCE_LABEL[cell.source];
}

/** Evidence block (Design.md 7.3): verified quote, no evidence found, or flagged. */
export function EvidenceBlock({ cell }: { cell: ScoreCell }) {
  const [expanded, setExpanded] = useState(false);

  if (cell.flag_reason) {
    return (
      <div className="evidence">
        <span className="tag tag-warning">
          <Icon name="triangle" color="var(--warning)" />
          Flagged
        </span>
        <p>
          The model&apos;s quote was not found in the resume. It was replaced with no evidence
          found.
        </p>
        <p className="muted">{cell.flag_reason}</p>
      </div>
    );
  }
  if (cell.status === "failed") {
    return (
      <p className="tag muted">
        <Icon name="triangle" color="var(--warning)" />
        Scoring failed for this criterion. Retry scoring from the ranked list.
      </p>
    );
  }
  if (cell.status === "no_evidence" || !cell.quote) {
    return (
      <p className="tag muted">
        <Icon name="dash" color="var(--gray-500)" />
        No evidence found
      </p>
    );
  }
  return (
    <div className="evidence">
      <span className="tag tag-success">
        <Icon name="check" color="var(--success)" />
        Verified
      </span>
      <blockquote className={expanded ? "quote" : "quote quote-clamped"}>
        &ldquo;{cell.quote}&rdquo;
      </blockquote>
      {cell.quote.length > 160 && (
        <button
          type="button"
          className="btn btn-ghost"
          aria-expanded={expanded}
          onClick={() => {
            setExpanded(!expanded);
          }}
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}
