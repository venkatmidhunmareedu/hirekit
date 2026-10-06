import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";

import { ApiError } from "../../lib/api";

import { getCurrentUser, login, logout } from "./api";

export const authKeys = { session: ["auth", "session"] as const };

/** The signed-in session. The cache is its only copy; a 401 is not retried. */
export const sessionQueryOptions = queryOptions({
  queryKey: authKeys.session,
  queryFn: getCurrentUser,
  retry: false,
  staleTime: 60_000,
});

/** Sign in, then put the session straight into the cache. */
export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      login(email, password),
    onSuccess: (session) => {
      queryClient.setQueryData(authKeys.session, session);
    },
  });
}

/** Sign out, drop every cached answer, and go to the sign-in screen. */
export function useLogout() {
  const queryClient = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      queryClient.clear();
      await router.navigate({ to: "/sign-in" });
    },
  });
}

/** Plain-language copy for a failed sign-in (Design.md section 10: what happened, what next). */
export function signInErrorMessage(error: Error): string {
  if (error instanceof ApiError && error.status === 401) {
    return "The email or password is not right. Check both and try again.";
  }
  if (error instanceof ApiError && error.status === 0) {
    return "Could not reach the server. Check your connection and try again.";
  }
  return "Something went wrong. Try again in a moment.";
}
