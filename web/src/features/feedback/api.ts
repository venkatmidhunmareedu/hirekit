import { request } from "../../lib/api";
import { Reader } from "../../lib/parse";

// Hand-typed from backend/api/openapi.yaml: FeedbackRow, FeedbackList, FeedbackSubmit.
export interface FeedbackRow {
  interviewer_id: string;
  criterion_id: string;
  score: number;
  comment: string;
  locked: boolean;
}

export interface FeedbackItem {
  criterion_id: string;
  score: number;
  comment: string;
}

export function readFeedbackRow(r: Reader): FeedbackRow {
  return {
    interviewer_id: r.str("interviewer_id"),
    criterion_id: r.str("criterion_id"),
    score: r.num("score"),
    comment: r.str("comment"),
    locked: r.bool("locked"),
  };
}

async function readList(call: Promise<unknown>): Promise<FeedbackRow[]> {
  return new Reader(await call, "feedback").list("data", readFeedbackRow);
}

/** GET .../feedback: a recruiter gets every interviewer's, an interviewer their own. */
export function getFeedback(candidateId: string): Promise<FeedbackRow[]> {
  return readList(request("GET", `/v1/candidates/${candidateId}/feedback`));
}

/** POST for the first submit (locks it), PUT for an approved edit (locks it again). */
export function submitFeedback(
  candidateId: string,
  items: FeedbackItem[],
  isEdit: boolean,
): Promise<FeedbackRow[]> {
  return readList(
    request(isEdit ? "PUT" : "POST", `/v1/candidates/${candidateId}/feedback`, { items }),
  );
}

/** POST .../feedback/{interviewer_id}:approve-edit. Recruiters only. */
export function approveEdit(candidateId: string, interviewerId: string): Promise<FeedbackRow[]> {
  return readList(
    request("POST", `/v1/candidates/${candidateId}/feedback/${interviewerId}:approve-edit`),
  );
}
