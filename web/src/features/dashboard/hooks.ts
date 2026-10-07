import { useQueries, useQuery } from "@tanstack/react-query";

import { queueQueryOptions, rankedQueryOptions } from "../candidates/hooks";
import { rolesQueryOptions } from "../roles/hooks";

import { summarizeRows } from "./shape";

/**
 * Every role with what the existing calls say about it: the queue and the first page of the ranked
 * list for approved roles. The queries are the ones the role header uses, so the cache is shared.
 */
export function usePortfolio() {
  const roles = useQuery(rolesQueryOptions);
  const approved = (roles.data ?? []).filter((r) => r.status === "approved");
  const queues = useQueries({ queries: approved.map((r) => queueQueryOptions(r.id)) });
  const pages = useQueries({
    queries: approved.map((r) => rankedQueryOptions(r.id, null, 0, false)),
  });

  const entries = (roles.data ?? []).map((role) => {
    const index = approved.findIndex((r) => r.id === role.id);
    const queue = index < 0 ? undefined : queues[index];
    const page = index < 0 ? undefined : pages[index];
    return {
      role,
      processing: queue?.data ? queue.data.waiting + queue.data.running : undefined,
      page: page?.data,
      summary: page?.data ? summarizeRows(page.data.data) : undefined,
      loading: queue?.isPending === true || page?.isPending === true,
      failed: queue?.isError === true || page?.isError === true,
    };
  });

  return {
    roles,
    entries,
    retry: () => {
      void roles.refetch();
      for (const q of [...queues, ...pages]) if (q.isError) void q.refetch();
    },
  };
}
