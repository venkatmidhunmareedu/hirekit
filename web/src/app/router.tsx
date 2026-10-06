import { type QueryClient } from "@tanstack/react-query";
import {
  type RouterHistory,
  Outlet,
  createRootRouteWithContext,
  createRoute,
  createRouter,
  redirect,
} from "@tanstack/react-router";

import { SignInPage } from "../features/auth/SignInPage";
import { sessionQueryOptions } from "../features/auth/hooks";
import { CandidateDetailPage } from "../features/candidates/CandidateDetailPage";
import { MyCandidatesPage } from "../features/candidates/MyCandidatesPage";
import { ComparePage } from "../features/compare/ComparePage";
import { KitPage } from "../features/kit/KitPage";
import { ApiError } from "../lib/api";

import { AppShell, HomePage } from "./AppShell";
import { RouteError } from "./RouteError";

const rootRoute = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: Outlet,
});

const signInRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/sign-in",
  component: SignInPage,
});

// The route guard: every route under here needs a session. A 401 from
// /v1/auth/me sends the user to sign-in; any other failure shows RouteError.
const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "app",
  beforeLoad: async ({ context }) => {
    try {
      await context.queryClient.query(sessionQueryOptions);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        throw redirect({ to: "/sign-in" });
      }
      throw error;
    }
  },
  component: AppShell,
});

const homeRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/",
  component: HomePage,
});

// HK-68 screens: candidate detail, my candidates, interview kit, compare.
const candidateRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/candidates/$candidateId",
  component: function CandidateRoute() {
    const { candidateId } = candidateRoute.useParams();
    // key: per-candidate state (drafts, dialogs) must not survive a param change.
    return <CandidateDetailPage key={candidateId} candidateId={candidateId} />;
  },
});

const myCandidatesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/me/candidates",
  component: MyCandidatesPage,
});

const kitRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/roles/$roleId/kit",
  component: function KitRoute() {
    const { roleId } = kitRoute.useParams();
    return <KitPage key={roleId} roleId={roleId} />;
  },
});

// ids is the API's own parameter name: two to four candidate ids, comma separated.
const compareRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/compare",
  validateSearch: (search: Record<string, unknown>) => ({
    ids: typeof search.ids === "string" ? search.ids : "",
  }),
  component: function CompareRoute() {
    const { ids } = compareRoute.useSearch();
    const list = ids
      .split(",")
      .map((id) => id.trim())
      .filter((id) => id !== "");
    return <ComparePage ids={list} />;
  },
});

const routeTree = rootRoute.addChildren([
  signInRoute,
  appRoute.addChildren([homeRoute, candidateRoute, myCandidatesRoute, kitRoute, compareRoute]),
]);

/** Build the router; tests pass a memory history. */
export function createAppRouter(queryClient: QueryClient, history?: RouterHistory) {
  return createRouter({
    routeTree,
    context: { queryClient },
    defaultErrorComponent: RouteError,
    ...(history && { history }),
  });
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
