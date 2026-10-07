export interface Crumb {
  label: string;
  /** Absent on the current page. */
  to?: "/roles" | "/me/candidates" | "/roles/$roleId";
  roleId?: string;
}

/** The header trail for a path. Role titles come from the role list; until it loads the word "Role" stands in. */
export function crumbs(
  pathname: string,
  role: "recruiter" | "interviewer",
  roles: readonly { id: string; title: string }[],
): Crumb[] {
  if (pathname === "/") return [{ label: "Dashboard" }];
  if (pathname === "/roles") return [{ label: "Roles" }];
  if (pathname === "/compare") return [{ label: "Compare" }];
  if (pathname === "/me/candidates") return [{ label: "My candidates" }];
  const roleMatch = /^\/roles\/([^/]+)(?:\/(candidates|kit))?$/.exec(pathname);
  if (roleMatch) {
    const id = roleMatch[1] ?? "";
    const screen = roleMatch[2];
    const title = roles.find((r) => r.id === id)?.title ?? "Role";
    const trail: Crumb[] = [{ label: "Roles", to: "/roles" }];
    if (!screen) return [...trail, { label: title }];
    return [
      ...trail,
      { label: title, to: "/roles/$roleId", roleId: id },
      { label: screen === "kit" ? "Interview kit" : "Candidates" },
    ];
  }
  if (pathname.startsWith("/candidates/")) {
    return role === "interviewer"
      ? [{ label: "My candidates", to: "/me/candidates" }, { label: "Candidate" }]
      : [{ label: "Candidate" }];
  }
  return [];
}

export function initials(name: string): string {
  const letters = name
    .trim()
    .split(/\s+/)
    .filter((w) => w !== "")
    .slice(0, 2)
    .map((w) => w.charAt(0).toUpperCase());
  return letters.length > 0 ? letters.join("") : "?";
}
