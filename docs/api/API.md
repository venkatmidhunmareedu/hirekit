# API: HireKit API v1.0.0

Generated from `backend/api/openapi.yaml` by openapi-spec (scripts/api_doc.py). Edit the spec, not this file.

**Style:** REST over HTTPS with JSON bodies, one service, one React client generated from this file (ADR-0006). · **Base path:** `/` · **Versioning:** Major in the path (/v1). No dated behaviour versions in the first build; the first breaking change is planned with the api-versioning skill.

**Authentication.** A server-side session in the HttpOnly cookie hirekit_session (ADR-0005). Every POST, PUT and DELETE also sends the session's csrf_token in the X-CSRF-Token header. A record the caller may not see is 404, never 403, so existence is not leaked. Public operations: GET /healthz, GET /readyz, POST /v1/auth/login.

**Errors.** Every 4xx and 5xx returns the error envelope; clients switch on `code`.

| Code | HTTP status | Meaning |
| --- | --- | --- |
| `unauthenticated` | 401 | No signed-in user, an expired session, or a wrong email or password |
| `csrf_failed` | 403 | The X-CSRF-Token header is missing or wrong |
| `forbidden` | 403 | The caller's role may not use this route |
| `not_found` | 404 | Missing, or not visible to this caller |
| `budget_reached` | 409 | The model budget is reached in live mode |
| `criteria_changed` | 409 | The criteria changed since the caller loaded them |
| `feedback_locked` | 409 | Feedback is already submitted and locked |
| `job_already_open` | 409 | A scoring, proposal or kit job is already open |
| `job_not_cancellable` | 409 | The job is already finished |
| `not_retryable` | 409 | The candidate does not need scoring |
| `role_not_approved` | 409 | The role is Draft; approve the criteria first |
| `same_stage` | 409 | The candidate is already in that stage |
| `scores_stale` | 409 | The score belongs to an older criteria version |
| `payload_too_large` | 413 | The request body is over the cap |
| `incomplete_feedback` | 422 | A criterion has no score or comment |
| `no_criteria` | 422 | The role has no criteria to approve |
| `too_many_files` | 422 | More than 100 files in one upload |
| `validation_error` | 422 | A field failed validation |
| `internal` | 500 | An unexpected error; quote the request_id |
| `service_unavailable` | 503 | The database cannot be reached |

## Conventions

1. Paths are plural kebab-case nouns and a non-CRUD action is a sub-resource (`POST /invoices/{id}/send`). Why: a client can guess the URL of a resource it has not seen, and verbs in paths multiply without limit.
2. JSON fields are snake_case, ids are strings, timestamps are RFC 3339 UTC with `Z`. Why: one casing and one clock remove a whole class of client parsing bugs.
3. Money is an integer `<name>_minor` plus an ISO 4217 `currency`. Why: floats cannot hold 0.10 exactly, and an amount without a currency is ambiguous.
4. Every 4xx and 5xx returns the one error envelope with a stable `code` and a `request_id`. Why: clients switch on `code`, not on English, and support finds the log line from `request_id`.
5. A record the caller may not see is 404, never 403. Why: a 403 confirms the record exists, which turns a guessed id into an oracle.
6. Every list is cursor-paginated with a capped `limit`. Why: offsets skip or repeat rows while data changes, and an uncapped page is a denial of service.
7. Every POST that creates or charges requires `Idempotency-Key`; the same key and body replays the first response for 24 hours. Why: mobile networks retry, and a retry must not create a second record or a second charge.
8. The path carries the major version and `X-API-Version` carries dated changes inside it. Why: installed clients cannot be forced to upgrade, so breaking changes need a new major and everything else a date.
9. Removal is `deprecated: true` plus a `Sunset` header and at least 90 days. Why: a removed field breaks a client nobody told, and oasdiff can only warn about what is still in the spec.
10. Every response carries the rate-limit headers and a 429 carries `Retry-After`. Why: a client that can see its budget backs off before it is throttled.
11. No Idempotency-Key header on creating POSTs. Why: The design stops duplicates in the database instead (unique open-job indexes, content-hash duplicate flags, idempotent assignment, 409 on a repeat feedback submit). Only POST /v1/roles can double-create on a retry, and a duplicate role is harmless and visible; revisit if it is not.
12. The ranked list and the job queue view use limit and offset, not cursors. Why: The order is a computed weighted total that no cursor can key on, and one role holds at most about 1,200 candidates (offset capped at 1,000); the cost log, which grows without bound, uses a cursor.
13. No X-API-Version and no rate-limit headers in the first build. Why: One client, one maintainer, local demo (HLD section 1); a hosted deployment adds both.
14. Errors carry details as an object, not a list. Why: The existing FastAPI envelope (app/core/errors.py) already returns an object and the generated client is built from it.

## auth

Sign in, sign out, the current user.

Serves US-00-012.

| Method | Path | Does | Auth | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| POST | `/v1/auth/login` | Sign in and set the session cookie | none | 200 Signed in; the cookie is set and the CSRF token returned | 401 unauthenticated, 422 incomplete_feedback, 422 too_many_files, 422 no_criteria, 422 validation_error, 500 internal |
| POST | `/v1/auth/logout` | Sign out (deletes the session and clears the cookie) | cookieAuth or csrfToken | 204 Signed out | 401 unauthenticated, 403 csrf_failed, 403 forbidden |
| GET | `/v1/auth/me` | The signed-in user and a CSRF token | cookieAuth | 200 The session | 401 unauthenticated |

Idempotency:

- `POST /v1/auth/login`: not idempotent; a retry repeats the action.
- `POST /v1/auth/logout`: not idempotent; a retry repeats the action.

## roles

Roles, criteria, approval, proposals.

Serves US-00-001, US-00-002, US-00-012.

| Method | Path | Does | Auth | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| GET | `/v1/roles` | List roles (at most 50, newest first) | cookieAuth or csrfToken | 200 The roles | 401 unauthenticated, 403 csrf_failed, 403 forbidden |
| POST | `/v1/roles` | Create a Draft role | cookieAuth or csrfToken | 201 Created | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 422 incomplete_feedback, 422 too_many_files, 422 no_criteria, 422 validation_error |
| GET | `/v1/roles/{role_id}` | One role with its criteria and rubric | cookieAuth or csrfToken | 200 The role | 401 unauthenticated, 404 not_found |
| POST | `/v1/roles/{role_id}/criteria:propose` | Ask the model to propose criteria (enqueues a job) | cookieAuth or csrfToken | 202 Job enqueued | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 409 role_not_approved, 409 scores_stale, 409 same_stage, 409 job_already_open, 409 not_retryable, 409 job_not_cancellable, 409 feedback_locked, 409 criteria_changed, 409 budget_reached |
| PUT | `/v1/roles/{role_id}/criteria` | Replace the criteria set in place (a removed id is retired, never deleted) | cookieAuth or csrfToken | 200 The role with its new criteria | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 422 incomplete_feedback, 422 too_many_files, 422 no_criteria, 422 validation_error |
| POST | `/v1/roles/{role_id}/approve` | Approve the criteria | cookieAuth or csrfToken | 200 Approved | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 409 role_not_approved, 409 scores_stale, 409 same_stage, 409 job_already_open, 409 not_retryable, 409 job_not_cancellable, 409 feedback_locked, 409 criteria_changed, 409 budget_reached, 422 incomplete_feedback, 422 too_many_files, 422 no_criteria, 422 validation_error |

Idempotency:

- `POST /v1/roles`: not idempotent, no Idempotency-Key (finding).
- `POST /v1/roles/{role_id}/criteria:propose`: not idempotent; a retry repeats the action.
- `PUT /v1/roles/{role_id}/criteria`: idempotent by definition; a retry has the same effect.
- `POST /v1/roles/{role_id}/approve`: not idempotent; a retry repeats the action.

## resumes

Bulk upload and the per-role queue view.

Serves US-00-003.

| Method | Path | Does | Auth | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| POST | `/v1/roles/{role_id}/resumes` | Upload up to 100 PDF or DOCX files | cookieAuth or csrfToken | 207 One result per file | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 409 role_not_approved, 409 scores_stale, 409 same_stage, 409 job_already_open, 409 not_retryable, 409 job_not_cancellable, 409 feedback_locked, 409 criteria_changed, 409 budget_reached, 413 payload_too_large, 422 incomplete_feedback, 422 too_many_files, 422 no_criteria, 422 validation_error |
| GET | `/v1/roles/{role_id}/queue` | Per-file job status for the whole role (at most 200, newest first) | cookieAuth or csrfToken | 200 The queue | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found |

Idempotency:

- `POST /v1/roles/{role_id}/resumes`: not idempotent; a retry repeats the action.

## candidates

The ranked list, detail, decisions and assignments.

Serves US-00-008, US-00-009, US-00-012, US-00-016, US-00-014, US-00-005, US-00-010, US-00-011.

| Method | Path | Does | Auth | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| GET | `/v1/roles/{role_id}/candidates` | The ranked list | cookieAuth or csrfToken | 200 One page of the ranked list | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found |
| GET | `/v1/me/candidates` | The interviewer's assigned candidates (at most 200) | cookieAuth or csrfToken | 200 The candidates assigned to the caller | 401 unauthenticated, 403 csrf_failed, 403 forbidden |
| GET | `/v1/candidates/{candidate_id}` | One candidate | cookieAuth or csrfToken | 200 The candidate | 401 unauthenticated, 404 not_found |
| GET | `/v1/candidates/{candidate_id}/text` | Raw and anonymized resume text | cookieAuth or csrfToken | 200 The texts (personal data, recruiters only) | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found |
| PUT | `/v1/candidates/{candidate_id}/scores/{criterion_id}/override` | Override a criterion score with a note | cookieAuth or csrfToken | 200 The updated score cell | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 409 role_not_approved, 409 scores_stale, 409 same_stage, 409 job_already_open, 409 not_retryable, 409 job_not_cancellable, 409 feedback_locked, 409 criteria_changed, 409 budget_reached, 422 incomplete_feedback, 422 too_many_files, 422 no_criteria, 422 validation_error |
| POST | `/v1/candidates/{candidate_id}/stage` | Change the stage (the only route that writes it) | cookieAuth or csrfToken | 200 The new stage | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 409 role_not_approved, 409 scores_stale, 409 same_stage, 409 job_already_open, 409 not_retryable, 409 job_not_cancellable, 409 feedback_locked, 409 criteria_changed, 409 budget_reached, 422 incomplete_feedback, 422 too_many_files, 422 no_criteria, 422 validation_error |
| POST | `/v1/candidates/{candidate_id}:reveal-identity` | Reveal the candidate's name (audited before it is returned) | cookieAuth or csrfToken | 200 The identity (personal data) | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found |
| POST | `/v1/candidates/{candidate_id}/assignments` | Assign an interviewer (idempotent) | cookieAuth or csrfToken | 201 Assigned | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 422 incomplete_feedback, 422 too_many_files, 422 no_criteria, 422 validation_error |
| DELETE | `/v1/candidates/{candidate_id}/assignments/{user_id}` | Remove an assignment | cookieAuth or csrfToken | 204 Removed | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found |

Idempotency:

- `PUT /v1/candidates/{candidate_id}/scores/{criterion_id}/override`: idempotent by definition; a retry has the same effect.
- `POST /v1/candidates/{candidate_id}/stage`: not idempotent; a retry repeats the action.
- `POST /v1/candidates/{candidate_id}:reveal-identity`: not idempotent; a retry repeats the action.
- `POST /v1/candidates/{candidate_id}/assignments`: not idempotent, no Idempotency-Key (finding).
- `DELETE /v1/candidates/{candidate_id}/assignments/{user_id}`: idempotent by definition; a retry has the same effect.

## kit

The per-role interview kit.

Serves US-00-013, US-00-002.

| Method | Path | Does | Auth | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| POST | `/v1/roles/{role_id}/kit:generate` | Generate the interview kit (enqueues a job, one model call per criterion) | cookieAuth or csrfToken | 202 Job enqueued | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 409 role_not_approved, 409 scores_stale, 409 same_stage, 409 job_already_open, 409 not_retryable, 409 job_not_cancellable, 409 feedback_locked, 409 criteria_changed, 409 budget_reached |
| GET | `/v1/roles/{role_id}/kit` | The kit; stale when it was generated for older criteria | cookieAuth or csrfToken | 200 The kit | 401 unauthenticated, 404 not_found |
| PUT | `/v1/kit/questions/{question_id}` | Edit or reorder a question in place | cookieAuth or csrfToken | 200 The question | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 422 incomplete_feedback, 422 too_many_files, 422 no_criteria, 422 validation_error |
| DELETE | `/v1/kit/questions/{question_id}` | Delete a question | cookieAuth or csrfToken | 204 Deleted | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found |
| POST | `/v1/kit/questions/{question_id}:regenerate` | Regenerate one question (enqueues a job) | cookieAuth or csrfToken | 202 Job enqueued | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 409 role_not_approved, 409 scores_stale, 409 same_stage, 409 job_already_open, 409 not_retryable, 409 job_not_cancellable, 409 feedback_locked, 409 criteria_changed, 409 budget_reached |

Idempotency:

- `POST /v1/roles/{role_id}/kit:generate`: not idempotent; a retry repeats the action.
- `PUT /v1/kit/questions/{question_id}`: idempotent by definition; a retry has the same effect.
- `DELETE /v1/kit/questions/{question_id}`: idempotent by definition; a retry has the same effect.
- `POST /v1/kit/questions/{question_id}:regenerate`: not idempotent; a retry repeats the action.

## feedback

Interviewer feedback and its approved edits.

Serves US-00-014, US-00-015.

| Method | Path | Does | Auth | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| GET | `/v1/candidates/{candidate_id}/feedback` | Feedback (a recruiter sees every interviewer's, an interviewer only their own) | cookieAuth or csrfToken | 200 The feedback | 401 unauthenticated, 404 not_found |
| POST | `/v1/candidates/{candidate_id}/feedback` | Submit feedback for every criterion (locks it) | cookieAuth or csrfToken | 201 Submitted | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 409 role_not_approved, 409 scores_stale, 409 same_stage, 409 job_already_open, 409 not_retryable, 409 job_not_cancellable, 409 feedback_locked, 409 criteria_changed, 409 budget_reached, 422 incomplete_feedback, 422 too_many_files, 422 no_criteria, 422 validation_error |
| PUT | `/v1/candidates/{candidate_id}/feedback` | Save an approved edit and lock it again | cookieAuth or csrfToken | 200 Saved | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 409 role_not_approved, 409 scores_stale, 409 same_stage, 409 job_already_open, 409 not_retryable, 409 job_not_cancellable, 409 feedback_locked, 409 criteria_changed, 409 budget_reached, 422 incomplete_feedback, 422 too_many_files, 422 no_criteria, 422 validation_error |
| POST | `/v1/candidates/{candidate_id}/feedback/{interviewer_id}:approve-edit` | Unlock one interviewer's feedback for an edit | cookieAuth or csrfToken | 200 Unlocked | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found |

Idempotency:

- `POST /v1/candidates/{candidate_id}/feedback`: not idempotent, no Idempotency-Key (finding).
- `PUT /v1/candidates/{candidate_id}/feedback`: idempotent by definition; a retry has the same effect.
- `POST /v1/candidates/{candidate_id}/feedback/{interviewer_id}:approve-edit`: not idempotent; a retry repeats the action.

## compare

Side-by-side comparison of two to four candidates.

Serves US-00-015.

| Method | Path | Does | Auth | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| GET | `/v1/compare` | Compare two to four candidates by criterion | cookieAuth or csrfToken | 200 The comparison | 401 unauthenticated, 404 not_found, 422 no_criteria, 422 validation_error |

## jobs

Background jobs the Worker runs.

Serves US-00-002, US-00-006, US-00-003, US-00-001.

| Method | Path | Does | Auth | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| POST | `/v1/roles/{role_id}:rescore` | Re-run scoring for every candidate that needs it | cookieAuth or csrfToken | 202 Jobs enqueued | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 409 role_not_approved, 409 scores_stale, 409 same_stage, 409 job_already_open, 409 not_retryable, 409 job_not_cancellable, 409 feedback_locked, 409 criteria_changed, 409 budget_reached |
| POST | `/v1/candidates/{candidate_id}:retry` | Enqueue a new scoring job for a candidate that needs scoring | cookieAuth or csrfToken | 202 Job enqueued | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 409 role_not_approved, 409 scores_stale, 409 same_stage, 409 job_already_open, 409 not_retryable, 409 job_not_cancellable, 409 feedback_locked, 409 criteria_changed, 409 budget_reached |
| GET | `/v1/jobs/{job_id}` | A job's status | cookieAuth or csrfToken | 200 The job | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found |
| POST | `/v1/jobs/{job_id}:cancel` | Cancel a queued or running job | cookieAuth or csrfToken | 200 Cancelled | 401 unauthenticated, 403 csrf_failed, 403 forbidden, 404 not_found, 409 role_not_approved, 409 scores_stale, 409 same_stage, 409 job_already_open, 409 not_retryable, 409 job_not_cancellable, 409 feedback_locked, 409 criteria_changed, 409 budget_reached |

Idempotency:

- `POST /v1/roles/{role_id}:rescore`: not idempotent; a retry repeats the action.
- `POST /v1/candidates/{candidate_id}:retry`: not idempotent; a retry repeats the action.
- `POST /v1/jobs/{job_id}:cancel`: not idempotent; a retry repeats the action.

## cost

The model budget and the call log.

Serves US-00-012, US-02-002.

| Method | Path | Does | Auth | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| GET | `/v1/cost-log` | The model budget and the call log (cursor, newest first) | cookieAuth or csrfToken | 200 One page | 401 unauthenticated, 403 csrf_failed, 403 forbidden |

## health

Liveness and readiness.

Serves unnumbered.

| Method | Path | Does | Auth | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| GET | `/healthz` | Liveness | none | 200 The process is up | none |
| GET | `/readyz` | Readiness (the database answers) | none | 200 Ready | 503 service_unavailable |

## Findings

Raised by the generator; each is a change to the spec or a decision to record.

- POST /v1/roles: creates (201) with no Idempotency-Key; a retried request makes a second record
- POST /v1/candidates/{candidate_id}/assignments: creates (201) with no Idempotency-Key; a retried request makes a second record
- POST /v1/candidates/{candidate_id}/feedback: creates (201) with no Idempotency-Key; a retried request makes a second record
