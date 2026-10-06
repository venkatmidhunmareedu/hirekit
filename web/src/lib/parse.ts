import { ApiError } from "./api";

/**
 * A small checked reader for response bodies (no Zod yet, see docs/progress/HK-52.md).
 * Every accessor throws ApiError "bad_response" when the body breaks the contract.
 */
export class Reader {
  private readonly data: Record<string, unknown>;
  private readonly what: string;

  constructor(value: unknown, what: string) {
    if (typeof value !== "object" || value === null || Array.isArray(value)) {
      throw new ApiError(200, "bad_response", `The ${what} response did not match the contract`);
    }
    this.data = Object.fromEntries(Object.entries(value));
    this.what = what;
  }

  private fail(key: string): never {
    throw new ApiError(200, "bad_response", `The ${this.what} field "${key}" broke the contract`);
  }

  str(key: string): string {
    const v = this.data[key];
    return typeof v === "string" ? v : this.fail(key);
  }

  num(key: string): number {
    const v = this.data[key];
    return typeof v === "number" ? v : this.fail(key);
  }

  bool(key: string): boolean {
    const v = this.data[key];
    return typeof v === "boolean" ? v : this.fail(key);
  }

  /** A string that may be absent or null. */
  optStr(key: string): string | null {
    const v = this.data[key];
    if (v === undefined || v === null) return null;
    return typeof v === "string" ? v : this.fail(key);
  }

  /** A number that may be absent or null. */
  optNum(key: string): number | null {
    const v = this.data[key];
    if (v === undefined || v === null) return null;
    return typeof v === "number" ? v : this.fail(key);
  }

  /** A boolean that may be absent; absent means false. */
  optBool(key: string): boolean {
    const v = this.data[key];
    if (v === undefined || v === null) return false;
    return typeof v === "boolean" ? v : this.fail(key);
  }

  oneOf<T extends string>(key: string, allowed: readonly T[]): T {
    const v = this.data[key];
    const hit = allowed.find((a) => a === v);
    return hit ?? this.fail(key);
  }

  /** Like oneOf, but absent or null reads as null. */
  optOneOf<T extends string>(key: string, allowed: readonly T[]): T | null {
    const v = this.data[key];
    if (v === undefined || v === null) return null;
    return this.oneOf(key, allowed);
  }

  /** A list that may be absent (read as empty). */
  list<T>(key: string, read: (item: Reader) => T): T[] {
    const v = this.data[key];
    if (v === undefined || v === null) return [];
    if (!Array.isArray(v)) return this.fail(key);
    return v.map((item: unknown) => read(new Reader(item, `${this.what}.${key}`)));
  }
}
