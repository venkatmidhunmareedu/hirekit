import { queryOptions } from "@tanstack/react-query";

import { getBudget } from "./api";

export const budgetQueryOptions = queryOptions({
  queryKey: ["cost", "budget"] as const,
  queryFn: getBudget,
});
