import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type Job,
  type Question,
  deleteQuestion,
  generateKit,
  getJob,
  getKit,
  getRoleCriteria,
  regenerateQuestion,
  updateQuestion,
} from "./api";

export const kitKeys = {
  role: (roleId: string) => ["roles", roleId, "criteria"] as const,
  kit: (roleId: string) => ["roles", roleId, "kit"] as const,
  job: (id: number | null) => ["jobs", id] as const,
};

export const roleCriteriaQueryOptions = (roleId: string) =>
  queryOptions({ queryKey: kitKeys.role(roleId), queryFn: () => getRoleCriteria(roleId) });

export const kitQueryOptions = (roleId: string) =>
  queryOptions({ queryKey: kitKeys.kit(roleId), queryFn: () => getKit(roleId) });

export function isJobDone(status: Job["status"] | undefined): boolean {
  return status !== undefined && status !== "queued" && status !== "running";
}

/** Poll a job until it ends; the kit is refetched once it has. */
export function useJobWatch(roleId: string, jobId: number | null) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: kitKeys.job(jobId),
    enabled: jobId !== null,
    queryFn: async () => {
      const job = await getJob(jobId ?? 0);
      if (isJobDone(job.status)) {
        await queryClient.invalidateQueries({ queryKey: kitKeys.kit(roleId) });
      }
      return job;
    },
    refetchInterval: (query) => (isJobDone(query.state.data?.status) ? false : 1500),
  });
}

export function useGenerateKit(roleId: string) {
  return useMutation({ mutationFn: () => generateKit(roleId) });
}

export function useRegenerate() {
  return useMutation({ mutationFn: (questionId: string) => regenerateQuestion(questionId) });
}

export function useEditQuestion(roleId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; patch: Parameters<typeof updateQuestion>[1] }) =>
      updateQuestion(v.id, v.patch),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: kitKeys.kit(roleId) }),
  });
}

/** Swap the positions of two neighbouring questions. */
export function useSwap(roleId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ([a, b]: [Question, Question]) => {
      await updateQuestion(a.id, { position: b.position });
      await updateQuestion(b.id, { position: a.position });
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: kitKeys.kit(roleId) }),
  });
}

export function useDeleteQuestion(roleId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (questionId: string) => deleteQuestion(questionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: kitKeys.kit(roleId) }),
  });
}
