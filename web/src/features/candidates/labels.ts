import { type RankedCandidate, type Stage } from "./api";

/** One list of hiring stage names, used by the filter, the table, the control and the history. */
export const STAGE_LABEL: Record<Stage, string> = {
  new: "New",
  screened: "Screened",
  interview: "Interview",
  offer: "Offer",
  hired: "Hired",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export const PROCESSING_LABEL: Record<RankedCandidate["processing_status"], string> = {
  queued: "Waiting to start",
  parsing: "Reading the resume",
  anonymizing: "Removing identity details",
  scoring: "Scoring",
  done: "Ready",
  failed: "Could not process",
};

/** Readable label for a processing status the detail API sends as a plain string. */
export function processingLabel(status: string): string {
  return status in PROCESSING_LABEL
    ? PROCESSING_LABEL[status as RankedCandidate["processing_status"]]
    : status.replaceAll("_", " ");
}
