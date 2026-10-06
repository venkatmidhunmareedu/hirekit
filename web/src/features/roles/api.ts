import { request } from "../../lib/api";
import { list, num, oneOf, rec, str } from "../../lib/guards";

// Hand-typed from backend/api/openapi.yaml: Role, RoleDetail, Criterion, RubricLevel, Job.
export interface Role {
  id: string;
  title: string;
  job_description: string;
  status: "draft" | "approved";
  criteria_version: number;
  created_at: string;
  updated_at: string;
}
export interface RubricLevel {
  level: number;
  descriptor: string;
}
export type CriterionKind = "must_have" | "nice_to_have";
export interface Criterion {
  id: string;
  name: string;
  kind: CriterionKind;
  weight: number;
  position: number;
  rubric: RubricLevel[];
}
export interface RoleDetail extends Role {
  criteria: Criterion[];
}
/** CriterionInput: id is set when editing an existing criterion in place. */
export interface CriterionInput {
  id: string | null;
  name: string;
  kind: CriterionKind;
  weight: number;
  rubric: RubricLevel[];
}
export const JOB_DONE = ["succeeded", "failed", "stale", "cancelled"] as const;
export interface Job {
  id: number;
  status: "queued" | "running" | (typeof JOB_DONE)[number];
}

function parseRole(body: unknown): Role {
  const r = rec(body);
  return {
    id: str(r, "id"),
    title: str(r, "title"),
    job_description: str(r, "job_description"),
    status: oneOf(r, "status", ["draft", "approved"]),
    criteria_version: num(r, "criteria_version"),
    created_at: str(r, "created_at"),
    updated_at: str(r, "updated_at"),
  };
}

function parseCriterion(body: unknown): Criterion {
  const r = rec(body);
  return {
    id: str(r, "id"),
    name: str(r, "name"),
    kind: oneOf(r, "kind", ["must_have", "nice_to_have"]),
    weight: num(r, "weight"),
    position: num(r, "position"),
    rubric: list(r, "rubric").map((item) => {
      const level = rec(item);
      return { level: num(level, "level"), descriptor: str(level, "descriptor") };
    }),
  };
}

function parseRoleDetail(body: unknown): RoleDetail {
  return {
    ...parseRole(body),
    criteria: list(rec(body), "criteria")
      .map(parseCriterion)
      .sort((a, b) => a.position - b.position),
  };
}

/** GET /v1/roles: at most 50, newest first. */
export async function listRoles(): Promise<Role[]> {
  return list(rec(await request("GET", "/v1/roles")), "data").map(parseRole);
}

/** POST /v1/roles: creates a Draft role. */
export async function createRole(input: { title: string; job_description: string }): Promise<Role> {
  return parseRole(await request("POST", "/v1/roles", input));
}

/** GET /v1/roles/{id}. */
export async function getRole(roleId: string): Promise<RoleDetail> {
  return parseRoleDetail(await request("GET", `/v1/roles/${roleId}`));
}

/** POST /v1/roles/{id}/criteria:propose: enqueues a job and returns its id. */
export async function proposeCriteria(roleId: string): Promise<number> {
  return num(rec(await request("POST", `/v1/roles/${roleId}/criteria:propose`)), "job_id");
}

/** PUT /v1/roles/{id}/criteria: replaces the set; an approved role returns to Draft. */
export async function replaceCriteria(
  roleId: string,
  criteria: CriterionInput[],
): Promise<RoleDetail> {
  return parseRoleDetail(await request("PUT", `/v1/roles/${roleId}/criteria`, { criteria }));
}

/** POST /v1/roles/{id}/approve with the criteria version the recruiter saw. */
export async function approveRole(roleId: string, criteriaVersion: number): Promise<Role> {
  return parseRole(
    await request("POST", `/v1/roles/${roleId}/approve`, { criteria_version: criteriaVersion }),
  );
}

/** GET /v1/jobs/{id}. */
export async function getJob(jobId: number): Promise<Job> {
  const r = rec(await request("GET", `/v1/jobs/${jobId}`));
  return { id: num(r, "id"), status: oneOf(r, "status", ["queued", "running", ...JOB_DONE]) };
}

/** POST /v1/jobs/{id}:cancel. */
export async function cancelJob(jobId: number): Promise<void> {
  await request("POST", `/v1/jobs/${jobId}:cancel`);
}
