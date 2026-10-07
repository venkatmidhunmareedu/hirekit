import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { Link, Outlet } from "@tanstack/react-router";
import { CircleAlert, TriangleAlert } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { Logo } from "../components/Logo";
import { sessionQueryOptions, useLogout } from "../features/auth/hooks";
import { budgetQueryOptions } from "../features/cost/hooks";

const NAV_LINK =
  "relative inline-flex h-14 items-center px-3 text-sm font-medium text-muted-foreground hover:text-foreground aria-[current=page]:text-foreground aria-[current=page]:after:absolute aria-[current=page]:after:inset-x-3 aria-[current=page]:after:bottom-0 aria-[current=page]:after:h-0.5 aria-[current=page]:after:rounded-full aria-[current=page]:after:bg-primary";

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
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-xs",
        reached
          ? "border-bad bg-bad-soft text-bad"
          : warn
            ? "border-warn bg-warn-soft text-warn"
            : "border-border bg-muted text-muted-foreground",
      )}
    >
      {(reached || warn) && <TriangleAlert aria-hidden="true" className="size-3.5" />}
      <span>{text}</span>
    </span>
  );
}

/** Authenticated layout (Design.md section 5): one header with nav, budget and user, then the content. */
export function AppShell() {
  const { data: session } = useSuspenseQuery(sessionQueryOptions);
  const logout = useLogout();
  const recruiter = session.user.role === "recruiter";

  return (
    <div className="min-h-screen bg-background">
      <header className="z-20 border-b bg-card sm:sticky sm:top-0 print:hidden">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-0 px-4 sm:px-6">
          <div className="py-3">
            <Logo />
          </div>
          <nav aria-label="Main" className="flex gap-1 max-sm:order-3">
            {session.user.role === "recruiter" && (
              <Link to="/" className={NAV_LINK} activeOptions={{ exact: true }}>
                Roles
              </Link>
            )}
            {session.user.role === "interviewer" && (
              <Link to="/me/candidates" className={NAV_LINK}>
                My candidates
              </Link>
            )}
          </nav>
          {recruiter && (
            <div className="py-2 max-sm:order-4 max-sm:ml-auto sm:ml-auto">
              <BudgetPill />
            </div>
          )}
          <div
            className={cn(
              "flex items-center gap-2 py-2 max-sm:order-2 max-sm:ml-auto",
              !recruiter && "ml-auto",
            )}
          >
            <span className="flex min-w-0 items-baseline gap-2 text-sm sm:border-l sm:pl-4">
              <span className="max-w-32 truncate font-medium sm:max-w-none">
                {session.user.name}
              </span>
              <span className="text-muted-foreground max-sm:sr-only">{session.user.role}</span>
            </span>
            <Button
              type="button"
              variant="ghost"
              className="h-10 text-muted-foreground"
              disabled={logout.isPending}
              onClick={() => {
                logout.mutate();
              }}
            >
              Sign out
            </Button>
          </div>
        </div>
      </header>
      {logout.isError && (
        <div className="mx-auto max-w-7xl px-4 pt-4 sm:px-6">
          <Alert variant="destructive" className="flex items-center gap-2 border-bad bg-bad-soft">
            <CircleAlert aria-hidden="true" className="size-4" />
            <AlertDescription className="text-bad">
              Could not sign out. Check your connection and try again.
            </AlertDescription>
          </Alert>
        </div>
      )}
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </div>
  );
}
