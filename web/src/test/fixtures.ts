// Response bodies shaped like backend/api/openapi.yaml, for tests that mock the network.
export const CAND = "30000000-0000-4000-8000-000000000001";
export const ROLE = "20000000-0000-4000-8000-000000000001";
export const CRIT_A = "40000000-0000-4000-8000-00000000000a";
export const CRIT_B = "40000000-0000-4000-8000-00000000000b";
export const CRIT_C = "40000000-0000-4000-8000-00000000000c";
export const INTERVIEWER = {
  user: {
    id: "00000000-0000-4000-8000-000000000002",
    name: "Ian",
    email: "ian@example.com",
    role: "interviewer",
  },
  csrf_token: "csrf-int",
};

export const QUOTE = "Led a team of five engineers on the payments API";

export const scores = [
  {
    criterion_id: CRIT_A,
    criterion_name: "Backend experience",
    kind: "must_have",
    status: "scored",
    model_score: 3,
    override_score: null,
    source: "model_suggestion",
    stale: false,
    quote: QUOTE,
    flag_reason: null,
    override_note: null,
  },
  {
    criterion_id: CRIT_B,
    criterion_name: "Incident response",
    kind: "must_have",
    status: "no_evidence",
    model_score: 0,
    override_score: null,
    source: "no_evidence_found",
    stale: false,
    quote: null,
    flag_reason: null,
    override_note: null,
  },
  {
    criterion_id: CRIT_C,
    criterion_name: "Mentoring",
    kind: "nice_to_have",
    status: "no_evidence",
    model_score: 0,
    override_score: 2,
    source: "recruiter_override",
    stale: false,
    quote: null,
    flag_reason: "quote not in text",
    override_note: "Mentioned in the interview",
  },
];

export const candidate = {
  id: CAND,
  candidate_no: 14,
  role_id: ROLE,
  stage: "screened",
  processing_status: "done",
  scores,
  audit: [
    {
      id: 1,
      kind: "stage_change",
      actor_id: "a",
      from_stage: "new",
      to_stage: "screened",
      created_at: "2026-10-05T10:00:00Z",
    },
  ],
};

export const role = {
  id: ROLE,
  title: "Backend engineer",
  job_description: "x",
  status: "approved",
  criteria_version: 1,
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
  criteria: [
    {
      id: CRIT_A,
      name: "Backend experience",
      kind: "must_have",
      weight: 2,
      position: 1,
      rubric: [],
    },
    {
      id: CRIT_B,
      name: "Incident response",
      kind: "must_have",
      weight: 1,
      position: 2,
      rubric: [],
    },
    { id: CRIT_C, name: "Mentoring", kind: "nice_to_have", weight: 1, position: 3, rubric: [] },
  ],
};
