import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  type Stage,
  assignInterviewer,
  changeStage,
  getAnonymizedText,
  getCandidate,
  getMyCandidates,
  overrideScore,
  revealIdentity,
  unassignInterviewer,
} from "./api";

export const candidateKeys = {
  detail: (id: string) => ["candidates", id] as const,
  text: (id: string) => ["candidates", id, "text"] as const,
  mine: ["candidates", "mine"] as const,
};

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

export function useAssign(candidateId: string) {
  return useMutation({ mutationFn: (userId: string) => assignInterviewer(candidateId, userId) });
}

export function useUnassign(candidateId: string) {
  return useMutation({ mutationFn: (userId: string) => unassignInterviewer(candidateId, userId) });
}
