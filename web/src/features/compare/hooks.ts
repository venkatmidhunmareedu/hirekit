import { queryOptions } from "@tanstack/react-query";

import { getComparison } from "./api";

export const compareQueryOptions = (ids: string[]) =>
  queryOptions({ queryKey: ["compare", ids] as const, queryFn: () => getComparison(ids) });
