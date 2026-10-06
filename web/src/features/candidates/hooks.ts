import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { getQueue, listCandidates, uploadResumes, type Stage } from "./api";

export const candidateKeys = {
  role: (roleId: string) => ["candidates", roleId] as const,
  ranked: (roleId: string, stage: Stage | null, offset: number) =>
    ["candidates", roleId, "ranked", { stage, offset }] as const,
  queue: (roleId: string) => ["candidates", roleId, "queue"] as const,
};

/** The queue is polled while any file is waiting or running. */
export function queueQueryOptions(roleId: string) {
  return queryOptions({
    queryKey: candidateKeys.queue(roleId),
    queryFn: () => getQueue(roleId),
    refetchInterval: (query) => {
      const queue = query.state.data;
      return queue && queue.waiting + queue.running > 0 ? 2000 : false;
    },
  });
}

export function rankedQueryOptions(
  roleId: string,
  stage: Stage | null,
  offset: number,
  polling: boolean,
) {
  return queryOptions({
    queryKey: candidateKeys.ranked(roleId, stage, offset),
    queryFn: () => listCandidates(roleId, { stage, offset }),
    refetchInterval: polling ? 4000 : false,
  });
}

export function useUpload(roleId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) => uploadResumes(roleId, files),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: candidateKeys.role(roleId) }),
  });
}
