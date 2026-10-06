import { request } from "../../lib/api";
import { Reader } from "../../lib/parse";
import { type Kind } from "../candidates/api";
import { type FeedbackRow, readFeedbackRow } from "../feedback/api";

// Hand-typed from backend/api/openapi.yaml: Comparison, CompareCell.
export interface CompareCell {
  criterion_id: string;
  model_score: number | null;
  override_score: number | null;
  feedback: FeedbackRow[];
  disagreement: boolean;
}

export interface Comparison {
  criteria: { id: string; name: string; kind: Kind }[];
  candidates: { candidate_id: string; candidate_no: number; cells: CompareCell[] }[];
}

/** GET /v1/compare?ids=a,b: two to four candidates. */
export async function getComparison(ids: string[]): Promise<Comparison> {
  const query = encodeURIComponent(ids.join(","));
  const r = new Reader(await request("GET", `/v1/compare?ids=${query}`), "comparison");
  return {
    criteria: r.list("criteria", (c) => ({
      id: c.str("id"),
      name: c.str("name"),
      kind: c.oneOf("kind", ["must_have", "nice_to_have"]),
    })),
    candidates: r.list("candidates", (c) => ({
      candidate_id: c.str("candidate_id"),
      candidate_no: c.num("candidate_no"),
      cells: c.list("cells", (x) => ({
        criterion_id: x.str("criterion_id"),
        model_score: x.optNum("model_score"),
        override_score: x.optNum("override_score"),
        feedback: x.list("feedback", readFeedbackRow),
        disagreement: x.bool("disagreement"),
      })),
    })),
  };
}
