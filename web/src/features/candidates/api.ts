import { request } from "../../lib/api";
import { Reader } from "../../lib/parse";

// Hand-typed from backend/api/openapi.yaml: Stage, ScoreCell, AuditEvent, CandidateDetail,
// CandidateText, Identity, StageChanged, Assignment, MyCandidates.
export const STAGES = [
  "new",
  "screened",
  "interview",
  "offer",
  "hired",
  "rejected",
  "withdrawn",
] as const;
export type Stage = (typeof STAGES)[number];

export type Kind = "must_have" | "nice_to_have";
const KINDS: readonly Kind[] = ["must_have", "nice_to_have"];

export interface ScoreCell {
  criterion_id: string;
  criterion_name: string;
  kind: Kind;
  status: "scored" | "no_evidence" | "failed";
  model_score: number | null;
  override_score: number | null;
  source: "model_suggestion" | "no_evidence_found" | "recruiter_override" | "failed";
  stale: boolean;
  quote: string | null;
  flag_reason: string | null;
  override_note: string | null;
}

export interface AuditEvent {
  id: number;
  kind: string;
  criterion_name: string | null;
  old_score: number | null;
  new_score: number | null;
  from_stage: Stage | null;
  to_stage: Stage | null;
  note: string | null;
  created_at: string;
}

export interface CandidateDetail {
  id: string;
  candidate_no: number;
  role_id: string;
  stage: Stage | null;
  processing_status: string | null;
  scores: ScoreCell[];
  audit: AuditEvent[];
  has_submitted: boolean;
}

export interface MyCandidate {
  candidate_id: string;
  candidate_no: number;
  role_id: string;
  role_title: string;
  has_submitted: boolean;
}

/** The anonymized label shown in place of a name (Design.md section 9). */
export function candidateLabel(no: number): string {
  return `C-${String(no).padStart(3, "0")}`;
}

export function readScoreCell(r: Reader): ScoreCell {
  return {
    criterion_id: r.str("criterion_id"),
    criterion_name: r.str("criterion_name"),
    kind: r.oneOf("kind", KINDS),
    status: r.oneOf("status", ["scored", "no_evidence", "failed"]),
    model_score: r.optNum("model_score"),
    override_score: r.optNum("override_score"),
    source: r.oneOf("source", [
      "model_suggestion",
      "no_evidence_found",
      "recruiter_override",
      "failed",
    ]),
    stale: r.optBool("stale"),
    quote: r.optStr("quote"),
    flag_reason: r.optStr("flag_reason"),
    override_note: r.optStr("override_note"),
  };
}

function readAudit(r: Reader): AuditEvent {
  return {
    id: r.num("id"),
    kind: r.str("kind"),
    criterion_name: r.optStr("criterion_name"),
    old_score: r.optNum("old_score"),
    new_score: r.optNum("new_score"),
    from_stage: r.optOneOf("from_stage", STAGES),
    to_stage: r.optOneOf("to_stage", STAGES),
    note: r.optStr("note"),
    created_at: r.str("created_at"),
  };
}

/** GET /v1/candidates/{id}. Interviewers get no scores until they submit feedback. */
export async function getCandidate(id: string): Promise<CandidateDetail> {
  const r = new Reader(await request("GET", `/v1/candidates/${id}`), "candidate");
  return {
    id: r.str("id"),
    candidate_no: r.num("candidate_no"),
    role_id: r.str("role_id"),
    stage: r.optOneOf("stage", STAGES),
    processing_status: r.optStr("processing_status"),
    scores: r.list("scores", readScoreCell),
    audit: r.list("audit", readAudit),
    has_submitted: r.optBool("has_submitted"),
  };
}

/** GET /v1/candidates/{id}/text. Recruiters only; only the anonymized text is kept. */
export async function getAnonymizedText(id: string): Promise<string> {
  const r = new Reader(await request("GET", `/v1/candidates/${id}/text`), "candidate text");
  return r.str("anonymized_text");
}

/** PUT .../scores/{criterion_id}/override. The note needs at least 10 characters. */
export async function overrideScore(
  candidateId: string,
  criterionId: string,
  overrideScoreValue: number,
  note: string,
): Promise<ScoreCell> {
  const body = { override_score: overrideScoreValue, note };
  const path = `/v1/candidates/${candidateId}/scores/${criterionId}/override`;
  return readScoreCell(new Reader(await request("PUT", path, body), "score"));
}

/** POST /v1/candidates/{id}/stage. The only call that changes a stage. */
export async function changeStage(id: string, stage: Stage, reason: string | null): Promise<Stage> {
  const body = reason ? { stage, reason } : { stage };
  const r = new Reader(await request("POST", `/v1/candidates/${id}/stage`, body), "stage");
  return r.oneOf("to_stage", STAGES);
}

export interface Identity {
  identity_name: string | null;
  file_name: string;
}

/** POST /v1/candidates/{id}:reveal-identity. The server audits it before it answers. */
export async function revealIdentity(id: string): Promise<Identity> {
  const r = new Reader(await request("POST", `/v1/candidates/${id}:reveal-identity`), "identity");
  return { identity_name: r.optStr("identity_name"), file_name: r.str("file_name") };
}

/** POST /v1/candidates/{id}/assignments. Idempotent. */
export async function assignInterviewer(id: string, userId: string): Promise<string> {
  const body = { user_id: userId };
  const r = new Reader(
    await request("POST", `/v1/candidates/${id}/assignments`, body),
    "assignment",
  );
  return r.str("user_id");
}

/** DELETE /v1/candidates/{id}/assignments/{user_id}. */
export async function unassignInterviewer(id: string, userId: string): Promise<void> {
  await request("DELETE", `/v1/candidates/${id}/assignments/${userId}`);
}

/** GET /v1/me/candidates: the interviewer's assigned candidates. */
export async function getMyCandidates(): Promise<MyCandidate[]> {
  const r = new Reader(await request("GET", "/v1/me/candidates"), "my candidates");
  return r.list("data", (c) => ({
    candidate_id: c.str("candidate_id"),
    candidate_no: c.num("candidate_no"),
    role_id: c.str("role_id"),
    role_title: c.str("role_title"),
    has_submitted: c.bool("has_submitted"),
  }));
}
