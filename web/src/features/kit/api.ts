import { ApiError, request } from "../../lib/api";
import { Reader } from "../../lib/parse";
import { type Kind } from "../candidates/api";

// Hand-typed from backend/api/openapi.yaml: RoleDetail, Criterion, Kit, Question, Job.
export interface RoleCriterion {
  id: string;
  name: string;
  kind: Kind;
  position: number;
  rubric: { level: number; descriptor: string }[];
}

export interface RoleCriteria {
  id: string;
  title: string;
  status: "draft" | "approved";
  criteria: RoleCriterion[];
}

export interface Question {
  id: string;
  criterion_id: string;
  question_text: string;
  strong_answer: string;
  weak_answer: string;
  position: number;
}

export interface Kit {
  stale: boolean;
  questions: Question[];
}

export interface Job {
  id: number;
  status: "queued" | "running" | "succeeded" | "failed" | "stale" | "cancelled";
}

/** GET /v1/roles/{id}: the title and criteria. Interviewers may read it too. */
export async function getRoleCriteria(roleId: string): Promise<RoleCriteria> {
  const r = new Reader(await request("GET", `/v1/roles/${roleId}`), "role");
  return {
    id: r.str("id"),
    title: r.str("title"),
    status: r.oneOf("status", ["draft", "approved"]),
    criteria: r.list("criteria", (c) => ({
      id: c.str("id"),
      name: c.str("name"),
      kind: c.oneOf("kind", ["must_have", "nice_to_have"]),
      position: c.num("position"),
      rubric: c.list("rubric", (l) => ({ level: l.num("level"), descriptor: l.str("descriptor") })),
    })),
  };
}

function readQuestion(r: Reader): Question {
  return {
    id: r.str("id"),
    criterion_id: r.str("criterion_id"),
    question_text: r.str("question_text"),
    strong_answer: r.str("strong_answer"),
    weak_answer: r.str("weak_answer"),
    position: r.num("position"),
  };
}

/** GET /v1/roles/{id}/kit. A role with no kit yet answers 404 not_found: that is an empty kit. */
export async function getKit(roleId: string): Promise<Kit> {
  let body: unknown;
  try {
    body = await request("GET", `/v1/roles/${roleId}/kit`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return { stale: false, questions: [] };
    throw error;
  }
  const r = new Reader(body, "kit");
  return { stale: r.bool("stale"), questions: r.list("questions", readQuestion) };
}

async function jobId(call: Promise<unknown>): Promise<number> {
  return new Reader(await call, "job").num("job_id");
}

/** POST /v1/roles/{id}/kit:generate (202, a job). */
export function generateKit(roleId: string): Promise<number> {
  return jobId(request("POST", `/v1/roles/${roleId}/kit:generate`));
}

/** POST /v1/kit/questions/{id}:regenerate (202, a job). */
export function regenerateQuestion(questionId: string): Promise<number> {
  return jobId(request("POST", `/v1/kit/questions/${questionId}:regenerate`));
}

/** GET /v1/jobs/{id}. */
export async function getJob(id: number): Promise<Job> {
  const r = new Reader(await request("GET", `/v1/jobs/${id}`), "job");
  return {
    id: r.num("id"),
    status: r.oneOf("status", ["queued", "running", "succeeded", "failed", "stale", "cancelled"]),
  };
}

/** PUT /v1/kit/questions/{id}: edit text or move to a position. */
export async function updateQuestion(
  questionId: string,
  patch: Partial<Pick<Question, "question_text" | "strong_answer" | "weak_answer" | "position">>,
): Promise<Question> {
  return readQuestion(
    new Reader(await request("PUT", `/v1/kit/questions/${questionId}`, patch), "question"),
  );
}

/** DELETE /v1/kit/questions/{id}. */
export async function deleteQuestion(questionId: string): Promise<void> {
  await request("DELETE", `/v1/kit/questions/${questionId}`);
}
