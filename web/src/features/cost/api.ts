import { request } from "../../lib/api";
import { bool, rec, str } from "../../lib/guards";

export interface Budget {
  spent_usd: number;
  limit_usd: number;
  model_actions_allowed: boolean;
}

/** GET /v1/cost-log?limit=1: only the budget is read; decimal strings become numbers for display. */
export async function getBudget(): Promise<Budget> {
  const budget = rec(rec(await request("GET", "/v1/cost-log?limit=1")).budget);
  return {
    spent_usd: Number(str(budget, "spent_usd")),
    limit_usd: Number(str(budget, "limit_usd")),
    model_actions_allowed: bool(budget, "model_actions_allowed"),
  };
}
