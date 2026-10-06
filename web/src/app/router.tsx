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
import { CandidatesPage } from "../features/candidates/CandidatesPage";
import { RoleSetupPage } from "../features/roles/RoleSetupPage";
import { RolesPage } from "../features/roles/RolesPage";
import { ApiError } from "../lib/api";

import { AppShell } from "./AppShell";
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
  component: RolesPage,
});

const roleSetupRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/roles/$roleId",
  component: RoleSetupPage,
});

const roleCandidatesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/roles/$roleId/candidates",
  component: CandidatesPage,
});

const routeTree = rootRoute.addChildren([
  signInRoute,
  appRoute.addChildren([homeRoute, roleSetupRoute, roleCandidatesRoute]),
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
