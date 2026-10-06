import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  JOB_DONE,
  approveRole,
  cancelJob,
  createRole,
  getJob,
  getRole,
  listRoles,
  proposeCriteria,
  replaceCriteria,
  type CriterionInput,
} from "./api";

export const roleKeys = {
  list: ["roles"] as const,
  detail: (roleId: string) => ["roles", roleId] as const,
  job: (jobId: number) => ["jobs", jobId] as const,
};

export const rolesQueryOptions = queryOptions({
  queryKey: roleKeys.list,
  queryFn: listRoles,
});

export function roleQueryOptions(roleId: string) {
  return queryOptions({ queryKey: roleKeys.detail(roleId), queryFn: () => getRole(roleId) });
}

/** Poll a criteria proposal until it ends; a finished job refreshes the role. */
export function jobQueryOptions(jobId: number, onDone: () => void) {
  return queryOptions({
    queryKey: roleKeys.job(jobId),
    queryFn: async () => {
      const job = await getJob(jobId);
      if (job.status !== "queued" && job.status !== "running") onDone();
      return job;
    },
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status !== undefined && JOB_DONE.some((done) => done === status) ? false : 1500;
    },
  });
}

export function useCreateRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createRole,
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: roleKeys.list }),
  });
}

export function useProposeCriteria(roleId: string) {
  return useMutation({ mutationFn: () => proposeCriteria(roleId) });
}

export function useCancelJob() {
  return useMutation({ mutationFn: cancelJob });
}

/** Saving or approving puts the answer straight into the cache and refreshes the list. */
export function useSaveCriteria(roleId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (criteria: CriterionInput[]) => replaceCriteria(roleId, criteria),
    onSuccess: async (role) => {
      queryClient.setQueryData(roleKeys.detail(roleId), role);
      await queryClient.invalidateQueries({ queryKey: roleKeys.list });
    },
  });
}

export function useApproveRole(roleId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (criteriaVersion: number) => approveRole(roleId, criteriaVersion),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["roles"] }),
  });
}
