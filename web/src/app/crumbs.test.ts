import { describe, expect, it } from "vitest";

import { crumbs, initials } from "./crumbs";

const roles = [{ id: "r1", title: "Backend engineer" }];

describe("crumbs", () => {
  it("names the dashboard and the role list", () => {
    expect(crumbs("/", "recruiter", roles)).toEqual([{ label: "Dashboard" }]);
    expect(crumbs("/roles", "recruiter", roles)).toEqual([{ label: "Roles" }]);
  });

  it("walks from Roles through the role to the screen", () => {
    expect(crumbs("/roles/r1/candidates", "recruiter", roles)).toEqual([
      { label: "Roles", to: "/roles" },
      { label: "Backend engineer", to: "/roles/$roleId", roleId: "r1" },
      { label: "Candidates" },
    ]);
    expect(crumbs("/roles/r1", "recruiter", roles)).toEqual([
      { label: "Roles", to: "/roles" },
      { label: "Backend engineer" },
    ]);
  });

  it("falls back to a plain word while the role title is not loaded", () => {
    expect(crumbs("/roles/zz/kit", "recruiter", [])[1]).toEqual({
      label: "Role",
      to: "/roles/$roleId",
      roleId: "zz",
    });
  });

  it("gives interviewers their own trail", () => {
    expect(crumbs("/me/candidates", "interviewer", [])).toEqual([{ label: "My candidates" }]);
    expect(crumbs("/candidates/c1", "interviewer", [])).toEqual([
      { label: "My candidates", to: "/me/candidates" },
      { label: "Candidate" },
    ]);
  });

  it("labels compare", () => {
    expect(crumbs("/compare", "recruiter", [])).toEqual([{ label: "Compare" }]);
  });
});

describe("initials", () => {
  it("takes the first letters of up to two words", () => {
    expect(initials("Riya Sharma")).toBe("RS");
    expect(initials("ian")).toBe("I");
    expect(initials("  ")).toBe("?");
  });
});
