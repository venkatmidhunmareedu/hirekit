import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  type Stage,
  assignInterviewer,
  changeStage,
  getAnonymizedText,
  getCandidate,
  getCandidateAssignments,
  getMyCandidates,
  getQueue,
  listInterviewers,
  listCandidates,
  overrideScore,
  rescoreRole,
  revealIdentity,
  unassignInterviewer,
  uploadResumes,
} from "./api";

export const candidateKeys = {
  role: (roleId: string) => ["candidates", roleId] as const,
  ranked: (roleId: string, stage: Stage | null, offset: number) =>
    ["candidates", roleId, "ranked", { stage, offset }] as const,
  queue: (roleId: string) => ["candidates", roleId, "queue"] as const,
  detail: (id: string) => ["candidates", id] as const,
  text: (id: string) => ["candidates", id, "text"] as const,
  interviewers: () => ["users", "interviewers"] as const,
  assignments: (id: string) => ["candidates", id, "assignments"] as const,
  mine: ["candidates", "mine"] as const,
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

export function useRescore(roleId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => rescoreRole(roleId),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: candidateKeys.role(roleId) }),
  });
}

export const candidateQueryOptions = (id: string) =>
  queryOptions({ queryKey: candidateKeys.detail(id), queryFn: () => getCandidate(id) });

export const anonymizedTextQueryOptions = (id: string) =>
  queryOptions({ queryKey: candidateKeys.text(id), queryFn: () => getAnonymizedText(id) });

export const myCandidatesQueryOptions = queryOptions({
  queryKey: candidateKeys.mine,
  queryFn: getMyCandidates,
});

/** Override a score, then refetch the candidate so the cache stays the only copy. */
export function useOverride(candidateId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (v: { criterionId: string; score: number; note: string }) =>
      overrideScore(candidateId, v.criterionId, v.score, v.note),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: candidateKeys.detail(candidateId) }),
  });
}

export function useChangeStage(candidateId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (v: { stage: Stage; reason: string | null }) =>
      changeStage(candidateId, v.stage, v.reason),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: candidateKeys.detail(candidateId) }),
  });
}

/** The revealed name lives in the mutation result only: it is never cached. */
export function useReveal(candidateId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => revealIdentity(candidateId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: candidateKeys.detail(candidateId) }),
  });
}

export const interviewersQueryOptions = () =>
  queryOptions({ queryKey: candidateKeys.interviewers(), queryFn: listInterviewers });

export const assignmentsQueryOptions = (id: string) =>
  queryOptions({
    queryKey: candidateKeys.assignments(id),
    queryFn: () => getCandidateAssignments(id),
  });

export function useAssign(candidateId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => assignInterviewer(candidateId, userId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: candidateKeys.assignments(candidateId) }),
  });
}

export function useUnassign(candidateId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => unassignInterviewer(candidateId, userId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: candidateKeys.assignments(candidateId) }),
  });
}
