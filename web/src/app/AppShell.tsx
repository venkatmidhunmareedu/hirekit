import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import { CircleAlert, TriangleAlert } from "lucide-react";
import { MotionConfig, motion } from "motion/react";
import { Fragment } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import { sessionQueryOptions, useLogout } from "../features/auth/hooks";
import { budgetQueryOptions } from "../features/cost/hooks";
import { rolesQueryOptions } from "../features/roles/hooks";

import { AppSidebar } from "./AppSidebar";
import { UserMenu } from "./UserMenu";
import { crumbs } from "./crumbs";

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
      <span className="max-sm:sr-only">{text}</span>
      <span aria-hidden="true" className="sm:hidden">
        {reached ? "Reached" : `USD ${spent.toFixed(2)}`}
      </span>
    </span>
  );
}

/** Where you are: the trail on wide screens, the current page alone on narrow ones. */
function Trail({ recruiter }: { recruiter: boolean }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const roles = useQuery({ ...rolesQueryOptions, enabled: recruiter });
  const trail = crumbs(pathname, recruiter ? "recruiter" : "interviewer", roles.data ?? []);
  return (
    <Breadcrumb className="min-w-0">
      <BreadcrumbList className="flex-nowrap">
        {trail.map((crumb, index) => {
          const last = index === trail.length - 1;
          return (
            <Fragment key={crumb.label}>
              {index > 0 && <BreadcrumbSeparator className={cn(!last && "max-sm:hidden")} />}
              <BreadcrumbItem className={cn("min-w-0", !last && "max-sm:hidden")}>
                {crumb.to === undefined ? (
                  <BreadcrumbPage className="truncate font-medium">{crumb.label}</BreadcrumbPage>
                ) : (
                  <BreadcrumbLink asChild>
                    {crumb.to === "/roles/$roleId" && crumb.roleId !== undefined ? (
                      <Link to="/roles/$roleId" params={{ roleId: crumb.roleId }}>
                        {crumb.label}
                      </Link>
                    ) : (
                      <Link to={crumb.to === "/me/candidates" ? "/me/candidates" : "/roles"}>
                        {crumb.label}
                      </Link>
                    )}
                  </BreadcrumbLink>
                )}
              </BreadcrumbItem>
            </Fragment>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}

/** Authenticated layout (Design.md section 5): sidebar, a slim top bar, then the content. */
export function AppShell() {
  const { data: session } = useSuspenseQuery(sessionQueryOptions);
  const logout = useLogout();
  const recruiter = session.user.role === "recruiter";
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <MotionConfig reducedMotion="user">
      <TooltipProvider delayDuration={300}>
        <SidebarProvider defaultOpen>
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:ring-2 focus:ring-ring"
          >
            Skip to content
          </a>
          <AppSidebar recruiter={recruiter} />
          <div className="flex min-w-0 flex-1 flex-col">
            <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b bg-card px-3 sm:px-4 print:hidden">
              <SidebarTrigger className="size-10" />
              <Trail recruiter={recruiter} />
              <div className="ml-auto flex shrink-0 items-center gap-2">
                {recruiter && <BudgetPill />}
                <UserMenu
                  user={session.user}
                  signingOut={logout.isPending}
                  onSignOut={() => {
                    logout.mutate();
                  }}
                />
              </div>
            </header>
            {logout.isError && (
              <div className="mx-auto w-full max-w-7xl px-4 pt-4 sm:px-6">
                <Alert
                  variant="destructive"
                  className="flex items-center gap-2 border-bad bg-bad-soft"
                >
                  <CircleAlert aria-hidden="true" className="size-4" />
                  <AlertDescription className="text-bad">
                    Could not sign out. Check your connection and try again.
                  </AlertDescription>
                </Alert>
              </div>
            )}
            <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
              <motion.div
                key={pathname}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
              >
                <Outlet />
              </motion.div>
            </main>
          </div>
        </SidebarProvider>
      </TooltipProvider>
    </MotionConfig>
  );
}
