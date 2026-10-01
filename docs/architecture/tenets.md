# System design tenets: HireKit

Rules this team holds itself to on this project. Each is here because
somebody could plausibly do the opposite, and a reviewer can point at a
breach.

## 1. The API never calls the model gateway

**The API process never imports the gateway; in the running system every model call is a job that the worker runs, and the only other callers are the maintainer's record and eval commands.**

The budget cap, the replay mode and the cost log stay in the gateway, and the API stays fast and free of provider timeouts (ADR-0004, REQ-040 to REQ-046).

_A breach looks like:_ a merge request adds a `POST /v1/roles/{id}/criteria:propose` handler that calls `gateway.complete(...)` inline instead of enqueuing a `propose_criteria` job.

## 2. Resume text reaches the model only as an AnonymizedText value

**The gateway accepts only three real classes, `AnonymizedText`, `JobDescriptionText` and `PromptText`, checks them with `isinstance` at runtime (the class each purpose requires for `input`, and `PromptText` for `system`), and only the anonymizer, the job-description intake and the prompt module construct them.**

The model never seeing identity signals is the product's central claim (REQ-018, REQ-047), so a runtime check, not a type hint that is erased or a code comment, must carry it.

_A breach looks like:_ a merge request passes `resume.raw_text` to the gateway wrapped in `JobDescriptionText(...)`, or builds `AnonymizedText(...)` outside the anonymizer "to test something quickly".

## 3. A score row exists only after its quote has been verified

**The scoring step writes a score only after `verify_quote` has run on that criterion; an unverified quote is never stored.**

REQ-020 and REQ-021 make the evidence guarantee a property of stored data, and a later cleanup job would leave a window where a fabricated quote is on screen.

_A breach looks like:_ a merge request inserts score rows straight from the model response and adds a "verify later" job to flag bad quotes afterwards.

## 4. Only an authenticated recruiter request changes a stage

**No worker, job or ranking code writes a candidate's stage; the only writer is the stage endpoint, guarded by the recruiter role.**

REQ-029 and REQ-055 forbid the system rejecting, hiding or moving candidates on its own.

_A breach looks like:_ a merge request sets `stage = 'Screened'` in the worker once scoring finishes.

## 5. Tests never open a network connection

**In replay mode the gateway does not build an HTTP client at all, and CI sets replay mode; a missing recording fails the test.**

Zero live calls in CI is a success metric (REQ-045, REQ-046, REQ-059), and an accidental live call spends the USD 8.

_A breach looks like:_ a merge request adds `if not recording: return live_call(...)` "so tests stop failing", or mocks the HTTP layer with a hand-written response instead of recording one.

## 6. Authorisation is a route dependency plus a SQL predicate

**Every resource route declares its required role as a dependency, and every interviewer query carries `AND candidate_id IN (assigned)` in SQL.**

Interviewers see only assigned candidates and never resume text (REQ-054, Q-003, Q-004), and a check after the fetch is one refactor from being skipped.

_A breach looks like:_ a merge request loads a candidate by id, then compares `candidate.interviewer_id` in Python and returns 403.

## 7. Logs, errors and job payloads carry ids, not resume text

**Log lines, exception messages and job payloads hold candidate and resume ids; resume text is read from the database when needed.**

Raw resumes are personal data and logs must never contain them (REQ-049), and a payload copy outlives the row's access rules.

_A breach looks like:_ a merge request logs `logger.info("scoring", text=anonymized)` or puts the anonymized text into the job's `payload` column.

## 8. Budget is reserved and committed before every live call

**A live model call first commits its reserved maximum cost with one `UPDATE ... WHERE spent + :reserve <= 8` and a `reserved` call_log row in their own transaction; it never reads the total and then decides, and replay never touches the budget.**

With several workers, read-then-call lets each pass the check and overshoot USD 8 (REQ-043), and a reservation that shares the score-writing transaction is rolled back by a crash while the money is already spent.

_A breach looks like:_ a merge request writes `if get_spent() < LIMIT: call_model()`, or reserves inside the transaction that later stores the scores.
