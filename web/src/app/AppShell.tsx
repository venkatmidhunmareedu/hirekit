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
  "rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground aria-[current=page]:bg-accent aria-[current=page]:text-accent-foreground";

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
        "inline-flex items-center gap-1.5 rounded-sm border px-2 py-1 font-mono text-xs",
        reached
          ? "border-bad bg-bad-soft text-bad"
          : warn
            ? "border-warn bg-warn-soft text-warn"
            : "border-border bg-card text-muted-foreground",
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

  return (
    <div className="min-h-screen">
      <header className="border-b bg-card print:hidden">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <Logo />
          <nav aria-label="Main" className="flex gap-1">
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
          <div className="ml-auto flex flex-wrap items-center gap-3">
            {session.user.role === "recruiter" && <BudgetPill />}
            <span className="flex items-baseline gap-2 text-sm">
              <span className="font-medium">{session.user.name}</span>
              <span className="text-muted-foreground">{session.user.role}</span>
            </span>
            <Button
              type="button"
              variant="outline"
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
        <div className="mx-auto max-w-6xl px-4 pt-4 sm:px-6">
          <Alert variant="destructive" className="flex items-center gap-2 border-bad bg-bad-soft">
            <CircleAlert aria-hidden="true" className="size-4" />
            <AlertDescription className="text-bad">
              Could not sign out. Check your connection and try again.
            </AlertDescription>
          </Alert>
        </div>
      )}
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </div>
  );
}
