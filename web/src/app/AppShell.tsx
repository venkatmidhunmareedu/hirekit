import { useSuspenseQuery } from "@tanstack/react-query";
import { Link, Outlet } from "@tanstack/react-router";

import { AlertIcon } from "../components/AlertIcon";
import { Logo } from "../components/Logo";
import { sessionQueryOptions, useLogout } from "../features/auth/hooks";

/** Authenticated layout (Design.md section 5): sidebar, top bar with the user, content. */
export function AppShell() {
  const { data: session } = useSuspenseQuery(sessionQueryOptions);
  const logout = useLogout();

  return (
    <div className="shell">
      <aside className="sidebar">
        <Logo />
        <nav aria-label="Main">
          <Link to="/" className="nav-link" activeOptions={{ exact: true }}>
            Roles
          </Link>
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

/** The signed-in landing page. The role list (Design.md section 8.1) is a later task. */
export function HomePage() {
  return (
    <>
      <h1>Roles</h1>
      <p className="muted">Your roles will appear here.</p>
    </>
  );
}
