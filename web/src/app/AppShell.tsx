import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { Link, Outlet } from "@tanstack/react-router";

import { AlertIcon } from "../components/AlertIcon";
import { Logo } from "../components/Logo";
import { sessionQueryOptions, useLogout } from "../features/auth/hooks";
import { budgetQueryOptions } from "../features/cost/hooks";

/** Model spend against the USD limit: icon and text, never color alone. Not a link: no call log page exists. */
function BudgetPill() {
  const budget = useQuery(budgetQueryOptions);
  if (!budget.data) return null;
  const { spent_usd: spent, limit_usd: limit, model_actions_allowed: allowed } = budget.data;
  const reached = !allowed || spent >= limit;
  const warn = !reached && spent >= limit * 0.75;
  const text = reached
    ? "Budget reached"
    : `Budget USD ${spent.toFixed(2)} of ${limit.toFixed(2)}${warn ? ", nearly used" : ""}`;
  return (
    <span className={`pill${reached ? " pill-danger" : warn ? " pill-warning" : ""}`}>
      {(reached || warn) && <AlertIcon />}
      <span>{text}</span>
    </span>
  );
}

/** Authenticated layout (Design.md section 5): sidebar, top bar with the user, content. */
export function AppShell() {
  const { data: session } = useSuspenseQuery(sessionQueryOptions);
  const logout = useLogout();

  return (
    <div className="shell">
      <aside className="sidebar">
        <Logo />
        <nav aria-label="Main">
          {session.user.role === "recruiter" && (
            <Link to="/" className="nav-link" activeOptions={{ exact: true }}>
              Roles
            </Link>
          )}
          {session.user.role === "interviewer" && (
            <Link to="/me/candidates" className="nav-link">
              My candidates
            </Link>
          )}
        </nav>
      </aside>
      <div className="shell-main">
        <header className="topbar">
          <span className="topbar-user">
            <span>{session.user.name}</span>
            <span className="muted">{session.user.role}</span>
          </span>
          {session.user.role === "recruiter" && <BudgetPill />}
          <button
            type="button"
            className="btn btn-secondary"
            disabled={logout.isPending}
            onClick={() => {
              logout.mutate();
            }}
          >
            Sign out
          </button>
        </header>
        {logout.isError && (
          <p role="alert" className="notice notice-danger">
            <AlertIcon />
            <span>Could not sign out. Check your connection and try again.</span>
          </p>
        )}
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
