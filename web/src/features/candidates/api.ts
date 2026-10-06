import { request } from "../../lib/api";
import { bool, list, num, oneOf, optNum, optStr, rec, str } from "../../lib/guards";

// Hand-typed from backend/api/openapi.yaml: UploadResponse, QueueView, RankedList.
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

export const MAX_FILES = 100;

export interface UploadFileResult {
  file_name: string;
  status: "accepted" | "rejected" | "role_not_approved";
  candidate_no: number | null;
  duplicate_of_candidate_no: number | null;
  reason: string | null;
}

export interface QueueSummary {
  waiting: number;
  running: number;
}

export interface ScoreCell {
  criterion_id: string;
  criterion_name: string;
  kind: "must_have" | "nice_to_have";
  status: "scored" | "no_evidence" | "failed";
  model_score: number | null;
  override_score: number | null;
  stale: boolean;
  flag_reason: string | null;
}

export interface RankedCandidate {
  id: string;
  candidate_no: number;
  stage: Stage;
  processing_status: "queued" | "parsing" | "anonymizing" | "scoring" | "done" | "failed";
  failure_reason: string | null;
  total: number;
  must_have_covered: number;
  must_have_total: number;
  stale: boolean;
  duplicate_of_candidate_no: number | null;
  scores: ScoreCell[];
}

export interface RankedPage {
  data: RankedCandidate[];
  limit: number;
  offset: number;
  total: number;
}

function parseResult(body: unknown): UploadFileResult {
  const r = rec(body);
  return {
    file_name: str(r, "file_name"),
    status: oneOf(r, "status", ["accepted", "rejected", "role_not_approved"]),
    candidate_no: optNum(r, "candidate_no"),
    duplicate_of_candidate_no: optNum(r, "duplicate_of_candidate_no"),
    reason: optStr(r, "reason"),
  };
}

function parseScore(body: unknown): ScoreCell {
  const r = rec(body);
  return {
    criterion_id: str(r, "criterion_id"),
    criterion_name: str(r, "criterion_name"),
    kind: oneOf(r, "kind", ["must_have", "nice_to_have"]),
    status: oneOf(r, "status", ["scored", "no_evidence", "failed"]),
    model_score: optNum(r, "model_score"),
    override_score: optNum(r, "override_score"),
    stale: r.stale === true,
    flag_reason: optStr(r, "flag_reason"),
  };
}

function parseCandidate(body: unknown): RankedCandidate {
  const r = rec(body);
  return {
    id: str(r, "id"),
    candidate_no: num(r, "candidate_no"),
    stage: oneOf(r, "stage", STAGES),
    processing_status: oneOf(r, "processing_status", [
      "queued",
      "parsing",
      "anonymizing",
      "scoring",
      "done",
      "failed",
    ]),
    failure_reason: optStr(r, "failure_reason"),
    total: num(r, "total"),
    must_have_covered: num(r, "must_have_covered"),
    must_have_total: num(r, "must_have_total"),
    stale: bool(r, "stale"),
    duplicate_of_candidate_no: optNum(r, "duplicate_of_candidate_no"),
    scores: list(r, "scores").map(parseScore),
  };
}

/** POST /v1/roles/{id}/resumes (multipart, field "files"): 207 with one result per file. */
export async function uploadResumes(roleId: string, files: File[]): Promise<UploadFileResult[]> {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  const body = rec(await request("POST", `/v1/roles/${roleId}/resumes`, form));
  return list(body, "results").map(parseResult);
}

/** GET /v1/roles/{id}/queue: how many files are waiting or being processed. */
export async function getQueue(roleId: string): Promise<QueueSummary> {
  const body = rec(await request("GET", `/v1/roles/${roleId}/queue`));
  return { waiting: num(body, "waiting"), running: num(body, "running") };
}

export const PAGE_SIZE = 100;

/** GET /v1/roles/{id}/candidates: one page of the ranked list, optionally one stage. */
export async function listCandidates(
  roleId: string,
  options: { stage: Stage | null; offset: number },
): Promise<RankedPage> {
  const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(options.offset) });
  if (options.stage !== null) params.set("filter[stage]", options.stage);
  const body = rec(await request("GET", `/v1/roles/${roleId}/candidates?${params.toString()}`));
  const page = rec(body.page);
  return {
    data: list(body, "data").map(parseCandidate),
    limit: num(page, "limit"),
    offset: num(page, "offset"),
    total: num(page, "total"),
  };
}
