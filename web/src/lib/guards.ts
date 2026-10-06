import { ApiError } from "./api";

// Response guards: a body is checked where it enters the app (no schema library yet, see HK-52).
export type Rec = Record<string, unknown>;

function bad(): ApiError {
  return new ApiError(200, "bad_response", "The response did not match the contract");
}

export function rec(value: unknown): Rec {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw bad();
  return Object.fromEntries(Object.entries(value));
}

export function str(r: Rec, key: string): string {
  const v = r[key];
  if (typeof v !== "string") throw bad();
  return v;
}

export function num(r: Rec, key: string): number {
  const v = r[key];
  if (typeof v !== "number") throw bad();
  return v;
}

export function bool(r: Rec, key: string): boolean {
  const v = r[key];
  if (typeof v !== "boolean") throw bad();
  return v;
}

export function list(r: Rec, key: string): unknown[] {
  const v = r[key];
  if (!Array.isArray(v)) throw bad();
  return v;
}

/** A string that may be null or absent. */
export function optStr(r: Rec, key: string): string | null {
  return r[key] === undefined || r[key] === null ? null : str(r, key);
}

/** A number that may be null or absent. */
export function optNum(r: Rec, key: string): number | null {
  return r[key] === undefined || r[key] === null ? null : num(r, key);
}

export function oneOf<const T extends readonly string[]>(
  r: Rec,
  key: string,
  allowed: T,
): T[number] {
  const v = r[key];
  const hit = allowed.find((a) => a === v);
  if (hit === undefined) throw bad();
  return hit;
}
