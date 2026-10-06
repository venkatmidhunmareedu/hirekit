import { queryOptions, useMutation, useQueryClient } from "@tanstack/react-query";

import { candidateKeys } from "../candidates/hooks";

import { type FeedbackItem, approveEdit, getFeedback, submitFeedback } from "./api";

export const feedbackKeys = { list: (candidateId: string) => ["feedback", candidateId] as const };

export const feedbackQueryOptions = (candidateId: string) =>
  queryOptions({
    queryKey: feedbackKeys.list(candidateId),
    queryFn: () => getFeedback(candidateId),
  });

/** Submitting reveals the model scores to an interviewer, so the candidate is refetched too. */
export function useSubmitFeedback(candidateId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (v: { items: FeedbackItem[]; isEdit: boolean }) =>
      submitFeedback(candidateId, v.items, v.isEdit),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: feedbackKeys.list(candidateId) });
      await queryClient.invalidateQueries({ queryKey: candidateKeys.detail(candidateId) });
      await queryClient.invalidateQueries({ queryKey: candidateKeys.mine });
    },
  });
}

export function useApproveEdit(candidateId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (interviewerId: string) => approveEdit(candidateId, interviewerId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: feedbackKeys.list(candidateId) }),
  });
}
