# Backlog: HireKit

PRD: PRD.md   Questions: docs/product/questions.md   Built: 2026-09-30

## Story index


| Story     | Epic  | Title                                                                  | Persona                | Priority | Points | Covers                                                        | Depends on                                 |
| --------- | ----- | ---------------------------------------------------------------------- | ---------------------- | -------- | ------ | ------------------------------------------------------------- | ------------------------------------------ |
| US-02-001 | EP-01 | Route every model call through one capped, logged gateway              | Maintainer (group 02)  | Must     | TBD    | REQ-040, REQ-041, REQ-042, REQ-048, REQ-049                   | none                                       |
| US-02-002 | EP-01 | Stop model spend at the USD 8 budget                                   | Maintainer (group 02)  | Must     | TBD    | REQ-043, REQ-044                                              | US-02-001                                  |
| US-02-003 | EP-01 | Replay recorded model responses in tests and CI                        | Maintainer (group 02)  | Must     | TBD    | REQ-045, REQ-046, REQ-059                                     | US-02-001                                  |
| US-00-001 | EP-02 | Create a role and get proposed criteria                                | Recruiter (group 00)   | Must     | TBD    | REQ-001, REQ-002, REQ-003                                     | US-02-001, US-00-012                       |
| US-00-002 | EP-02 | Edit and approve criteria                                              | Recruiter (group 00)   | Must     | TBD    | REQ-004, REQ-005, REQ-006                                     | US-00-001                                  |
| US-00-003 | EP-03 | Upload resumes in bulk                                                 | Recruiter (group 00)   | Must     | TBD    | REQ-007, REQ-008, REQ-010, REQ-050, REQ-052, REQ-053          | US-00-002                                  |
| US-00-004 | EP-03 | Remove identity signals before any model call                          | Recruiter (group 00)   | Must     | TBD    | REQ-011, REQ-012, REQ-013, REQ-014, REQ-015, REQ-016, REQ-017 | US-00-003                                  |
| US-00-005 | EP-03 | Keep raw and anonymized text apart and refuse raw text at the gateway  | Recruiter (group 00)   | Must     | TBD    | REQ-009, REQ-018, REQ-047, REQ-049                            | US-00-004, US-02-001                       |
| US-00-006 | EP-04 | Score each criterion from the anonymized resume                        | Recruiter (group 00)   | Must     | TBD    | REQ-019, REQ-023                                              | US-00-005, US-00-002                       |
| US-00-007 | EP-04 | Verify quotes and downgrade unsupported scores                         | Recruiter (group 00)   | Must     | TBD    | REQ-020, REQ-021, REQ-022                                     | US-00-006                                  |
| US-00-008 | EP-04 | See a weighted total, must-haves apart, with the source of every score | Recruiter (group 00)   | Must     | TBD    | REQ-024, REQ-051                                              | US-00-007                                  |
| US-00-009 | EP-05 | Review candidates in a ranked list                                     | Recruiter (group 00)   | Must     | TBD    | REQ-025, REQ-028, REQ-029, REQ-052                            | US-00-008                                  |
| US-00-010 | EP-05 | Override a score with a note                                           | Recruiter (group 00)   | Must     | TBD    | REQ-026, REQ-027, REQ-030                                     | US-00-009                                  |
| US-00-011 | EP-05 | Move candidates through stages                                         | Recruiter (group 00)   | Must     | TBD    | REQ-030, REQ-055                                              | US-00-009                                  |
| US-00-012 | EP-05 | Enforce recruiter and interviewer permissions                          | Recruiter (group 00)   | Must     | TBD    | REQ-049, REQ-054                                              | none                                       |
| US-00-016 | EP-05 | inferred: Assign interviewers to a candidate                           | Recruiter (group 00)   | Should   | TBD    | REQ-054                                                       | US-00-012                                  |
| US-00-013 | EP-06 | Generate and edit an interview kit                                     | Recruiter (group 00)   | Should   | TBD    | REQ-031, REQ-032, REQ-033, REQ-034, REQ-035                   | US-00-002, US-02-001                       |
| US-00-014 | EP-06 | Submit scored interviewer feedback                                     | Interviewer (group 00) | Should   | TBD    | REQ-036, REQ-037, REQ-062                                     | US-00-013, US-00-016, US-00-012            |
| US-00-015 | EP-06 | Compare candidates side by side                                        | Recruiter (group 00)   | Should   | TBD    | REQ-038, REQ-039, REQ-052                                     | US-00-014, US-00-008                       |
| US-02-004 | EP-07 | Prove the core rules with automated tests                              | Maintainer (group 02)  | Must     | TBD    | REQ-056                                                       | US-00-004, US-00-007, US-02-001, US-00-012 |
| US-02-005 | EP-07 | Run the scoring agreement eval                                         | Maintainer (group 02)  | Must     | TBD    | REQ-057                                                       | US-00-008, US-02-003, US-02-007            |
| US-02-006 | EP-07 | Run the name-swap eval                                                 | Maintainer (group 02)  | Must     | TBD    | REQ-058                                                       | US-00-008, US-02-003, US-02-007            |
| US-02-007 | EP-07 | Load the seed data                                                     | Maintainer (group 02)  | Must     | TBD    | REQ-060                                                       | US-00-002                                  |




## EP-01 Keep every model call capped, logged and replayable

Goal: A maintainer can trust that all model use passes one gateway that caps tokens, logs cost, stops at USD 8 and replays recordings in tests and CI.
Covers: REQ-040, REQ-041, REQ-042, REQ-043, REQ-044, REQ-045, REQ-046, REQ-048, REQ-049, REQ-059

### US-02-001 Route every model call through one capped, logged gateway

Epic: EP-01   Priority: Must   Points: TBD (estimate)
Persona: Maintainer (group 02)   Ticket: unassigned
Covers: REQ-040, REQ-041, REQ-042, REQ-048, REQ-049   Judgement: merged from REQ-040, REQ-041, REQ-042, REQ-048

**Narrative.** As a maintainer, I want every model call to go through one gateway function, so that provider, token cap, cost logging and key handling are enforced in one place.

**Why it matters.** PRD goal 4: all model usage flows through one gateway. Nothing that calls the model can ship until this exists.

**From the PRD.**

- REQ-040: "Provider: OpenRouter. Model: `claude-haiku-4-5`."
- REQ-041: "`max_tokens` is capped at 1500. Higher requests are clamped or rejected."
- REQ-042: "Each call logs input tokens, output tokens, cost, purpose (criteria, scoring, kit, eval), role and timestamp."
- REQ-048: "API keys live in environment configuration and are never logged."
- REQ-049: "Raw resumes are visible to recruiters only. Logs never contain raw resume text or API keys."

**Preconditions.**

- A key for the provider is available in the environment configuration.

**Acceptance criteria.**

- AC-US-02-001-1. Given any feature (criteria, scoring, kit or eval) that needs a model response, when it calls the model, then the call goes through the gateway function, and a search of `app/` finds no other code that contacts the provider.
Covers: REQ-040
- AC-US-02-001-2. Given a call, when the gateway sends it, then the provider is OpenRouter and the model is `claude-haiku-4-5`, both read from one configuration value.
Covers: REQ-040
- AC-US-02-001-3. Given a request with `max_tokens` above 1500, when the gateway receives it, then the request is clamped to 1500 or rejected with a typed error, and the value sent never exceeds 1500.
Covers: REQ-041
- AC-US-02-001-4. Given a completed call, when it finishes, then one log row holds input tokens, output tokens, cost, purpose (criteria, scoring, kit or eval), role and timestamp.
Covers: REQ-042
- AC-US-02-001-5. Given an API key set in the environment, when the app runs and makes calls, then the key is read from environment configuration and appears in no log line or stored row.
Covers: REQ-048
- AC-US-02-001-6. Given a call log row or log line, when it is written, then it contains no resume text (raw or anonymized) and no API key.
Covers: REQ-049

**Not in this story.**

- Stopping at the USD 8 budget (US-02-002).
- Replay of recorded responses (US-02-003).
- Refusing non-anonymized input (US-00-005).

**Depends on.**

- none

**Assumptions.**

- none



### US-02-002 Stop model spend at the USD 8 budget

Epic: EP-01   Priority: Must   Points: TBD (estimate)
Persona: Maintainer (group 02)   Ticket: unassigned
Covers: REQ-043, REQ-044   Judgement: story

**Narrative.** As a maintainer, I want the gateway to stop calls once spend passes USD 8, so that the build and evals cannot overspend.

**Why it matters.** PRD goal 4: a hard USD 8 budget. Without this, a prompt-tuning loop can spend past the cap.

**From the PRD.**

- REQ-043: "The gateway keeps a running total of spend. Once the total passes USD 8, further calls are refused with a clear error."
- REQ-044: "A refused call returns a typed error that the UI shows plainly. The user never sees a silent failure."

**Preconditions.**

- Calls are being logged with their cost (US-02-001).

**Acceptance criteria.**

- AC-US-02-002-1. Given a running total below USD 8, when a call completes, then the running total increases by that call's cost and is stored.
Covers: REQ-043
- AC-US-02-002-2. Given a running total that has passed USD 8, when any new call is requested, then the gateway refuses it before contacting the provider.
Covers: REQ-043
- AC-US-02-002-3. Given a refused call, when the caller gets the result, then it is a typed budget error carrying the total and the limit.
Covers: REQ-044
- AC-US-02-002-4. Given a typed budget error, when a recruiter triggers a model action, then the UI shows "The model budget of $8.00 has been reached. No new model calls can be made.", model actions show a disabled state, and no failure is silent.
Covers: REQ-044

**Not in this story.**

- Per-role or per-user budgets (PRD non-goal: one total).
- The cost log screen (US-00-012 makes it recruiter-only).

**Depends on.**

- US-02-001: logs the cost each call adds to the total

**Assumptions.**

- none



### US-02-003 Replay recorded model responses in tests and CI

Epic: EP-01   Priority: Must   Points: TBD (estimate)
Persona: Maintainer (group 02)   Ticket: unassigned
Covers: REQ-045, REQ-046, REQ-059   Judgement: story

**Narrative.** As a maintainer, I want tests and CI to replay recorded model responses, so that they cost nothing and give the same result every time.

**Why it matters.** PRD goal 5: quality is measured from recordings in CI. Every later story's tests depend on this.

**From the PRD.**

- REQ-045: "Replay mode: tests and CI use recorded responses keyed by a hash of the request. CI makes no live calls."
- REQ-046: "A missing recording in replay mode fails the test. It never falls back to a live call."
- REQ-059: "Unit tests and both evals run from recorded responses, with zero live calls. Live re-recording is a manual, budget-checked step."

**Preconditions.**

- The gateway exists (US-02-001).

**Acceptance criteria.**

- AC-US-02-003-1. Given replay mode is on, when a request is made, then its response is looked up by a hash of the request, the model id, the prompt version and the schema-retry index (0 or 1), and returned with no network call.
Covers: REQ-045
- AC-US-02-003-2. Given replay mode and no recording for the request hash, when the request is made, then the test fails with a message naming the hash, and no live call is made.
Covers: REQ-046
- AC-US-02-003-3. Given a prompt that changed since it was recorded, when replay runs, then the hash differs and the failure says a recording exists for the same input under a different prompt or model.
Covers: REQ-046
- AC-US-02-003-4. Given the CI environment, when the CI job runs, then replay mode is forced and any attempt at a live call fails the job.
Covers: REQ-045, REQ-059
- AC-US-02-003-5. Given a maintainer who wants a fresh recording, when they run the record command, then it is manual, prints the remaining budget first, and refuses to run when the budget is used up.
Covers: REQ-059

**Not in this story.**

- The evals themselves (US-02-005, US-02-006).
- Choosing which requests to record (each story's tests do that).

**Depends on.**

- US-02-001: the single path that replay wraps

**Assumptions.**

- none



## EP-02 Define a role and approve its criteria

Goal: A recruiter turns a job description into approved criteria and a rubric that unlock the rest of the workflow.
Covers: REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006

### US-00-001 Create a role and get proposed criteria

Epic: EP-02   Priority: Must   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-001, REQ-002, REQ-003   Judgement: merged from REQ-001, REQ-002, REQ-003

**Narrative.** As a recruiter, I want to create a role from a job description and get proposed criteria, so that I start from a structured draft instead of a blank page.

**Why it matters.** PRD goal 1: every score rests on approved criteria. The proposal is the recruiter's starting point.

**From the PRD.**

- REQ-001: "A recruiter can create a role with a title and job description."
- REQ-002: "The system calls the model once to propose must-have criteria, nice-to-have criteria and a rubric."
- REQ-003: "Each criterion has a name, a type (must-have or nice-to-have), a weight, and rubric descriptors for each score level."

**Preconditions.**

- A signed-in recruiter (US-00-012).

**Acceptance criteria.**

- AC-US-00-001-1. Given a signed-in recruiter, when they enter a title and job description and save, then a role exists with status Draft.
Covers: REQ-001
- AC-US-00-001-2. Given a Draft role with a job description, when the recruiter asks for criteria, then the system makes one model call and shows proposed must-have and nice-to-have criteria with a rubric.
Covers: REQ-002
- AC-US-00-001-3. Given a proposal, when it is shown, then each criterion has a name, a type (must-have or nice-to-have), a weight and rubric descriptors for each score level.
Covers: REQ-003
- AC-US-00-001-4. Given the model call is in progress, when the recruiter cancels or the call fails, then the role stays Draft, nothing is approved, and the reason is shown.
Covers: REQ-002

**Not in this story.**

- Editing and approving the criteria (US-00-002).
- Which weights are fixed by type (Q-001).

**Depends on.**

- US-02-001: the gateway the proposal call goes through
- US-00-012: the signed-in recruiter

**Assumptions.**

- Weights are editable per criterion, with defaults by type (Q-001).



### US-00-002 Edit and approve criteria

Epic: EP-02   Priority: Must   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-004, REQ-005, REQ-006   Judgement: story

**Narrative.** As a recruiter, I want to edit the criteria and approve them, so that nothing downstream runs until I am satisfied with them.

**Why it matters.** PRD goal 3: humans stay in control. Approval is the first point where a person signs off.

**From the PRD.**

- REQ-004: "The recruiter can add, edit, reorder and delete criteria and rubric text."
- REQ-005: "A role has a status of `Draft` or `Approved`. Resume upload, scoring and kit generation are blocked while the role is `Draft`."
- REQ-006: "Editing criteria after approval returns the role to `Draft` and marks existing scores as stale. Stale scores can be re-run on request."

**Preconditions.**

- A role with proposed criteria (US-00-001).

**Acceptance criteria.**

- AC-US-00-002-1. Given proposed criteria, when the recruiter adds, edits, reorders or deletes a criterion or edits rubric text, then the change is saved in the draft.
Covers: REQ-004
- AC-US-00-002-2. Given a Draft role, when the recruiter opens approval, then a confirmation summarises what unlocks (upload, scoring, kit) and approving sets the role to Approved.
Covers: REQ-005
- AC-US-00-002-3. Given a Draft role, when the recruiter tries to upload resumes, start scoring or generate a kit, then each is blocked with a message that says to approve the criteria.
Covers: REQ-005
- AC-US-00-002-4. Given an Approved role, when the recruiter edits any criterion or rubric text, then the role returns to Draft.
Covers: REQ-006
- AC-US-00-002-5. Given a role that returned to Draft, when the recruiter opens its candidates, then existing scores are marked stale and a re-run action is offered; nothing re-runs unless the recruiter asks.
Covers: REQ-006
- AC-US-00-002-6. Given a role that returned to Draft, when the recruiter opens the kit, then the kit is marked stale and regeneration is offered (Q-005).
Covers: REQ-006

**Not in this story.**

- Generating criteria (US-00-001).
- Re-scoring itself (US-00-006 runs it).

**Depends on.**

- US-00-001: the proposal to edit

**Assumptions.**

- The kit is marked stale as well when criteria change (Q-005).



## EP-03 Bring resumes in without identity signals

Goal: A recruiter uploads resumes in bulk and knows the model only ever sees anonymized text.
Covers: REQ-007, REQ-008, REQ-009, REQ-010, REQ-011, REQ-012, REQ-013, REQ-014, REQ-015, REQ-016, REQ-017, REQ-018, REQ-047, REQ-049, REQ-050, REQ-052, REQ-053

### US-00-003 Upload resumes in bulk

Epic: EP-03   Priority: Must   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-007, REQ-008, REQ-010, REQ-050, REQ-052, REQ-053   Judgement: merged from REQ-007, REQ-008, REQ-010, plus qualities REQ-050, REQ-052, REQ-053

**Narrative.** As a recruiter, I want to upload many PDF and DOCX resumes at once and see each file's status, so that I can get a batch into the pipeline without babysitting it.

**Why it matters.** PRD goal 1 and section 10: 100 resumes must not block the screen, and failures must not disappear.

**From the PRD.**

- REQ-007: "Bulk upload accepts PDF and DOCX. Other types are rejected with a clear message."
- REQ-008: "Text is extracted per file. Extraction failures (scanned image, corrupt file) are listed and never silently dropped."
- REQ-010: "Duplicate uploads are detected by content hash and flagged."
- REQ-050: "Upload of 100 resumes completes without blocking the UI, with per-file progress."
- REQ-052: "WCAG 2.1 AA for text contrast and keyboard navigation."
- REQ-053: "Scoring one resume returns in a reasonable time for a batch run, with a visible queue."

**Preconditions.**

- An Approved role (US-00-002).

**Acceptance criteria.**

- AC-US-00-003-1. Given an Approved role, when the recruiter uploads PDF or DOCX files, then each file is accepted and shown as a row with a status.
Covers: REQ-007
- AC-US-00-003-2. Given a file that is not PDF or DOCX, when it is uploaded, then it is rejected with a message that names the accepted types.
Covers: REQ-007
- AC-US-00-003-3. Given a scanned image or corrupt file, when text extraction fails, then the file stays in the list as failed with a plain reason and a retry action, and is never silently dropped.
Covers: REQ-008
- AC-US-00-003-4. Given a file whose content hash matches an earlier upload for the role, when it is uploaded, then it is flagged as a duplicate.
Covers: REQ-010
- AC-US-00-003-5. Given 100 resumes uploaded together, when processing runs, then the UI stays usable and each file shows its own status (queued, parsing, anonymizing, scoring, done, failed).
Covers: REQ-050
- AC-US-00-003-6. Given a batch that is processing, when the recruiter views the list, then a visible queue shows how many files wait and which one is running.
Covers: REQ-053
- AC-US-00-003-7. Given the upload area, when used by keyboard only and checked at WCAG 2.1 AA, then every control is reachable and text contrast passes.
Covers: REQ-052

**Not in this story.**

- Removing identity signals (US-00-004).
- Scoring (US-00-006).
- Scanned-image OCR (PRD lists it only as a failure).

**Depends on.**

- US-00-002: an Approved role is required before upload

**Assumptions.**

- none



### US-00-004 Remove identity signals before any model call

Epic: EP-03   Priority: Must   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-011, REQ-012, REQ-013, REQ-014, REQ-015, REQ-016, REQ-017   Judgement: merged from REQ-011 to REQ-017

**Narrative.** As a recruiter, I want identity signals removed from every resume in code, so that the model never sees who the candidate is.

**Why it matters.** PRD goal 2: the model never sees name, gender, age, photo, religion or location, enforced in code and covered by tests.

**From the PRD.**

- REQ-011: "Remove or mask the candidate name, including name variants, initials and the name in headers and footers."
- REQ-012: "Remove gender signals: explicit gender fields, titles (Mr, Ms, Mrs), and gendered pronouns."
- REQ-013: "Remove age signals: date of birth, stated age, and graduation years or dates that reveal age where practical."
- REQ-014: "Remove photos and embedded images."
- REQ-015: "Remove religion signals: stated religion and religious affiliations."
- REQ-016: "Remove location: address, city, state, country and postal code."
- REQ-017: "Remove indirect identifiers that carry the same signals: email addresses, phone numbers, personal URLs and social profile links (names often appear in them)."

**Preconditions.**

- Text has been extracted from an uploaded resume (US-00-003).

**Acceptance criteria.**

- AC-US-00-004-1. Given a resume with the candidate's name, name variants, initials, or the name in a header or footer, when it is anonymized, then each is removed or masked.
Covers: REQ-011
- AC-US-00-004-2. Given a resume with a gender field, a title (Mr, Ms, Mrs) or gendered pronouns in sentences, when it is anonymized, then each is removed or neutralised.
Covers: REQ-012
- AC-US-00-004-3. Given a resume with a date of birth, a stated age, or graduation years or dates that reveal age, when it is anonymized, then they are removed where practical, in every date format the tests cover.
Covers: REQ-013
- AC-US-00-004-4. Given a resume with photos or embedded images, when it is anonymized, then all are removed.
Covers: REQ-014
- AC-US-00-004-5. Given a resume with a stated religion or religious affiliation, when it is anonymized, then it is removed.
Covers: REQ-015
- AC-US-00-004-6. Given a resume with an address, city, state, country or postal code, when it is anonymized, then each is removed.
Covers: REQ-016
- AC-US-00-004-7. Given a resume with email addresses, phone numbers, personal URLs or social links (including names inside them), when it is anonymized, then each is removed, and skills, employers, job titles, projects and outcomes are kept.
Covers: REQ-017

**Not in this story.**

- Refusing raw text at the gateway (US-00-005).
- Proxy signals such as school names, clubs or career gaps, which remain a known limit and are never claimed as removed (see docs/designs/hirekit-build-plan.md).

**Depends on.**

- US-00-003: provides the extracted text

**Assumptions.**

- none



### US-00-005 Keep raw and anonymized text apart and refuse raw text at the gateway

Epic: EP-03   Priority: Must   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-009, REQ-018, REQ-047, REQ-049   Judgement: merged from REQ-009, REQ-018, REQ-047, plus quality REQ-049

**Narrative.** As a recruiter, I want raw and anonymized text stored apart and the gateway to refuse raw text, so that no code path can send identity data to the model.

**Why it matters.** PRD goals 2 and 3: the anonymizer is the only path to the model, and raw resumes are personal data.

**From the PRD.**

- REQ-009: "The raw text is stored separately from the anonymized text. The model can only be given the anonymized text."
- REQ-018: "The gateway must only accept anonymized text. Passing raw resume text is a hard error."
- REQ-047: "The gateway rejects input that has not been through the anonymizer."
- REQ-049: "Raw resumes are visible to recruiters only. Logs never contain raw resume text or API keys."

**Preconditions.**

- Anonymization exists (US-00-004) and the gateway exists (US-02-001).

**Acceptance criteria.**

- AC-US-00-005-1. Given a parsed resume, when it is stored, then raw text and anonymized text are held in separate fields.
Covers: REQ-009
- AC-US-00-005-2. Given a scoring or eval call, when its input is built, then only the anonymized text is passed to the model.
Covers: REQ-009
- AC-US-00-005-3. Given raw resume text passed to the gateway, when the call is made, then the gateway raises a hard error and makes no provider call.
Covers: REQ-018, REQ-047
- AC-US-00-005-4. Given resume-derived input that carries no anonymizer mark, when it is sent for any purpose that uses resume text (scoring, eval), then the gateway rejects it.
Covers: REQ-047
- AC-US-00-005-5. Given a non-recruiter account, when it requests raw resume text, then access is denied, and a recruiter can read it.
Covers: REQ-049
- AC-US-00-005-6. Given a resume that is processed or fails, when the app logs the event, then the log line contains no raw resume text.
Covers: REQ-049

**Not in this story.**

- The anonymizer rules themselves (US-00-004).
- Retention and deletion of stored data (Q-012).

**Depends on.**

- US-00-004: produces the anonymized text
- US-02-001: the gateway that refuses raw text

**Assumptions.**

- none



## EP-04 Score every criterion with checked evidence

Goal: A recruiter gets a per-criterion score whose evidence quote code has verified, and a total that cannot hide a missing must-have.
Covers: REQ-019, REQ-020, REQ-021, REQ-022, REQ-023, REQ-024, REQ-051

### US-00-006 Score each criterion from the anonymized resume

Epic: EP-04   Priority: Must   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-019, REQ-023   Judgement: merged from REQ-019, REQ-023

**Narrative.** As a recruiter, I want each criterion scored with an evidence quote, so that I can check the reason for every score.

**Why it matters.** PRD goal 1: every score is backed by a quote or is marked "no evidence found".

**From the PRD.**

- REQ-019: "For each approved criterion, the model returns a score on the rubric scale and one evidence quote, or the literal value "no evidence found"."
- REQ-023: "The model output is parsed against a strict schema. Malformed output is retried once and then marked as failed, never guessed."

**Preconditions.**

- An Approved role and an anonymized resume (US-00-002, US-00-005).

**Acceptance criteria.**

- AC-US-00-006-1. Given an Approved role and an anonymized resume, when scoring runs, then for each approved criterion the model returns a score on the rubric scale and one evidence quote, or the literal "no evidence found".
Covers: REQ-019
- AC-US-00-006-2. Given scores shown anywhere, when they render, then the scale (0 to 4, where 0 means no evidence) is shown beside them (Q-009).
Covers: REQ-019
- AC-US-00-006-3. Given model output that does not match the schema, when it is parsed, then scoring for that resume is retried once.
Covers: REQ-023
- AC-US-00-006-4. Given a second malformed output, when the retry fails, then that criterion is marked failed for the resume, no value is guessed, and the failure is listed.
Covers: REQ-023
- AC-US-00-006-5. Given a failed criterion, when the recruiter views the candidate, then a re-run action is offered.
Covers: REQ-023

**Not in this story.**

- Checking the quote against the text (US-00-007).
- The weighted total (US-00-008).

**Depends on.**

- US-00-005: the anonymized input
- US-00-002: the approved criteria

**Assumptions.**

- The scale is 0 to 4 (Q-009).



### US-00-007 Verify quotes and downgrade unsupported scores

Epic: EP-04   Priority: Must   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-020, REQ-021, REQ-022   Judgement: merged from REQ-020, REQ-021, REQ-022

**Narrative.** As a recruiter, I want each quote checked against the resume text and unsupported scores downgraded, so that no score rests on invented text.

**Why it matters.** PRD goal 1: the evidence guarantee is code, not trust in the model.

**From the PRD.**

- REQ-020: "Code verifies that each quote exists in the anonymized resume text. Whitespace is normalized. No fuzzy matching that could accept invented text."
- REQ-021: "A quote that fails verification is replaced by "no evidence found", the score is capped accordingly, and the item is flagged for review."
- REQ-022: "A "no evidence found" criterion cannot receive a score above the lowest rubric level from the model. A recruiter override can change it, with a note."

**Preconditions.**

- Scores with quotes exist (US-00-006).

**Acceptance criteria.**

- AC-US-00-007-1. Given a returned quote, when it is verified, then it must appear in the anonymized text after whitespace normalization and no other change.
Covers: REQ-020
- AC-US-00-007-2. Given a quote with a changed word, a fabricated sentence or text that is not contiguous in the resume, when it is verified, then it fails, and no fuzzy match is applied.
Covers: REQ-020
- AC-US-00-007-3. Given a quote that failed verification, when scoring finishes, then the quote is replaced by "no evidence found".
Covers: REQ-021
- AC-US-00-007-4. Given a replaced quote, when the score is stored, then the score is capped accordingly and the item is flagged with a line that says why.
Covers: REQ-021
- AC-US-00-007-5. Given "no evidence found", when the model score is above the lowest rubric level (0, Q-011), then the stored model score is capped at that level.
Covers: REQ-022
- AC-US-00-007-6. Given a capped criterion, when the recruiter overrides it with a note, then the override value is accepted.
Covers: REQ-022

**Not in this story.**

- Manual override UI (US-00-010).
- Judging whether a verified quote supports the score; the UI says only that the text exists in the resume.

**Depends on.**

- US-00-006: the scores and quotes to verify

**Assumptions.**

- none



### US-00-008 See a weighted total, must-haves apart, with the source of every score

Epic: EP-04   Priority: Must   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-024, REQ-051   Judgement: merged from REQ-024, plus quality REQ-051

**Narrative.** As a recruiter, I want a weighted total with must-haves shown apart and the source of each score, so that a strong nice-to-have cannot hide a missing must-have.

**Why it matters.** PRD goals 1 and 3: totals must be inspectable and must not mask gaps.

**From the PRD.**

- REQ-024: "The final candidate score is a weighted total. Must-have criteria are shown separately so a strong nice-to-have cannot hide a missing must-have."
- REQ-051: "Every score shows its source (model, verified quote, or override with note)."

**Preconditions.**

- Verified scores exist (US-00-007).

**Acceptance criteria.**

- AC-US-00-008-1. Given scored criteria, when the total is computed, then it is the weighted sum using each criterion's weight.
Covers: REQ-024
- AC-US-00-008-2. Given a candidate, when the total shows, then must-have coverage (how many must-haves have verified evidence) is shown beside it.
Covers: REQ-024
- AC-US-00-008-3. Given a candidate with strong nice-to-haves and a must-have with no evidence, when the recruiter views the row, then the missing must-have is visible without opening the detail.
Covers: REQ-024
- AC-US-00-008-4. Given any score, when it is shown, then it carries its source: "Model suggestion" with a verified quote, "no evidence found", or "Recruiter override" with the note.
Covers: REQ-051
- AC-US-00-008-5. Given a total, when the recruiter selects it, then it links to the per-criterion scores and evidence that produced it.
Covers: REQ-051

**Not in this story.**

- Ranking and filters (US-00-009).
- Weights being fixed or editable (Q-001).

**Depends on.**

- US-00-007: verified scores

**Assumptions.**

- none



## EP-05 Review, override and decide

Goal: A recruiter reviews a ranked list, overrides scores with a note, moves candidates through stages and is the only role that can reject.
Covers: REQ-025, REQ-026, REQ-027, REQ-028, REQ-029, REQ-030, REQ-049, REQ-052, REQ-054, REQ-055

### US-00-009 Review candidates in a ranked list

Epic: EP-05   Priority: Must   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-025, REQ-028, REQ-029, REQ-052   Judgement: merged from REQ-025, REQ-028, REQ-029, plus quality REQ-052

**Narrative.** As a recruiter, I want a ranked list with filters and sorting, so that I can review many candidates quickly without anyone being hidden.

**Why it matters.** PRD goal 3: humans decide, and the system never hides a low scorer.

**From the PRD.**

- REQ-025: "The recruiter sees candidates ranked by weighted score, with per-criterion scores, evidence quotes and flags."
- REQ-028: "The recruiter can filter by stage and sort by total or by any criterion."
- REQ-029: "No candidate is rejected, hidden or de-ranked out of view by the system. Low scorers stay visible."
- REQ-052: "WCAG 2.1 AA for text contrast and keyboard navigation."

**Preconditions.**

- Totals exist (US-00-008).

**Acceptance criteria.**

- AC-US-00-009-1. Given scored candidates for a role, when the recruiter opens the list, then candidates are ranked by weighted score with per-criterion scores, evidence quotes and flags.
Covers: REQ-025
- AC-US-00-009-2. Given the list, when it renders, then candidates appear as IDs (for example C-014), not names, until the recruiter uses "Reveal identity", which is logged (Q-007).
Covers: REQ-025
- AC-US-00-009-3. Given the list, when the recruiter filters by stage or sorts by the total or by any criterion, then the list updates accordingly.
Covers: REQ-028
- AC-US-00-009-4. Given any score, when candidates are ranked, then the system never rejects, hides or collapses a candidate, and low scorers stay visible.
Covers: REQ-029
- AC-US-00-009-5. Given a keyboard-only user, when they use the table, then the active sort is announced and every control is reachable, at WCAG 2.1 AA contrast.
Covers: REQ-052

**Not in this story.**

- Overrides (US-00-010).
- Stage moves (US-00-011).

**Depends on.**

- US-00-008: the totals to rank

**Assumptions.**

- Names are hidden by default with a logged reveal (Q-007).



### US-00-010 Override a score with a note

Epic: EP-05   Priority: Must   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-026, REQ-027, REQ-030   Judgement: merged from REQ-026, REQ-027, REQ-030

**Narrative.** As a recruiter, I want to override any criterion score with a note, so that my judgement wins over the model's and the reason is recorded.

**Why it matters.** PRD goal 3: scores can be overridden, and both values are kept.

**From the PRD.**

- REQ-026: "The recruiter can override any criterion score. A note is required. Both the model value and the override are kept and shown."
- REQ-027: "Ranking is recalculated after overrides."
- REQ-030: "Stage moves and overrides are recorded in an audit history with user and time."

**Preconditions.**

- A scored candidate (US-00-009).

**Acceptance criteria.**

- AC-US-00-010-1. Given a criterion score, when the recruiter overrides it with a note of at least 10 characters, then the override is saved.
Covers: REQ-026
- AC-US-00-010-2. Given the override dialog, when the note is empty or under 10 characters, then Save is disabled.
Covers: REQ-026
- AC-US-00-010-3. Given an override, when the criterion row shows, then both the model value and the override are shown.
Covers: REQ-026
- AC-US-00-010-4. Given a saved override, when totals are recalculated, then the ranking is recomputed using the override.
Covers: REQ-027
- AC-US-00-010-5. Given an override, when it is saved, then the audit history records user, time, old value, new value and note.
Covers: REQ-030

**Not in this story.**

- Stage history (US-00-011).
- Overriding a stale score without re-running it (the stale banner offers re-run instead).

**Depends on.**

- US-00-009: the ranked list the override changes

**Assumptions.**

- none



### US-00-011 Move candidates through stages

Epic: EP-05   Priority: Must   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-030, REQ-055   Judgement: story from REQ-055

**Narrative.** As a recruiter, I want to move candidates through stages and be the only one who can reject, so that no candidate is rejected by the system.

**Why it matters.** PRD goal 3: only a recruiter can reject, and the system never changes a stage on its own.

**From the PRD.**

- REQ-030: "Stage moves and overrides are recorded in an audit history with user and time."
- REQ-055: "Moving to `Rejected` requires a recruiter action and is logged with user, time and optional reason. The system never changes a stage on its own. Every stage change is stored in a stage history."

**Preconditions.**

- A candidate exists for the role.

**Acceptance criteria.**

- AC-US-00-011-1. Given a candidate, when the recruiter changes the stage among New, Screened, Interview, Offer, Hired or Withdrawn, then the stage updates.
Covers: REQ-055
- AC-US-00-011-2. Given a stage change, when it is saved, then the stage history records from, to, user, time and optional reason.
Covers: REQ-030, REQ-055
- AC-US-00-011-3. Given the recruiter picks Rejected, when they confirm the dialog with an optional reason, then the candidate moves to Rejected and the record is logged under their name.
Covers: REQ-055
- AC-US-00-011-4. Given scoring or ranking finishes or scores change, when the list refreshes, then no candidate's stage changes on its own.
Covers: REQ-055

**Not in this story.**

- Permission checks for non-recruiters (US-00-012).
- Emails or notifications on stage change (not in the PRD).

**Depends on.**

- US-00-009: the list where stages are shown

**Assumptions.**

- none



### US-00-012 Enforce recruiter and interviewer permissions

Epic: EP-05   Priority: Must   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-049, REQ-054   Judgement: story from REQ-054, plus quality REQ-049

**Narrative.** As a recruiter, I want the service itself to enforce who can do what, so that an interviewer cannot reject, edit criteria, upload or override, whatever the screen shows.

**Why it matters.** PRD goal 3: humans stay in control and roles limit power. Every other story assumes it.

**From the PRD.**

- REQ-049: "Raw resumes are visible to recruiters only. Logs never contain raw resume text or API keys."
- REQ-054: "Interviewers cannot reject, edit criteria, upload resumes or override scores. (PRD section 3 table and section 8.1; only a recruiter can reject, view the cost log, or approve criteria)"

**Preconditions.**

- Seeded recruiter and interviewer accounts exist (Q-002).

**Acceptance criteria.**

- AC-US-00-012-1. Given a recruiter session, when they use the app, then they can create roles, edit and approve criteria, upload resumes, override scores, move stages, reject and view the cost log.
Covers: REQ-054
- AC-US-00-012-2. Given an interviewer session, when they attempt to reject, edit criteria, upload resumes, override scores or move stages, then the service refuses each, not only the UI.
Covers: REQ-054
- AC-US-00-012-3. Given an interviewer session, when they open the app, then they see the kit, the criteria and only the candidates assigned to them.
Covers: REQ-054
- AC-US-00-012-4. Given an interviewer session, when they request the gateway cost log, then the request is refused.
Covers: REQ-054
- AC-US-00-012-5. Given a request with no signed-in user, when it reaches the service, then it is refused.
Covers: REQ-054
- AC-US-00-012-6. Given an interviewer session, when they request any candidate's raw or anonymized resume text, then the request is refused (Q-003).
Covers: REQ-049

**Not in this story.**

- A real identity provider (Q-002 assumes seeded logins).
- Assigning interviewers (US-00-016).

**Depends on.**

- none

**Assumptions.**

- Seeded logins for v1 (Q-002). Interviewers see no resume text (Q-003).



### US-00-016 inferred: Assign interviewers to a candidate

Epic: EP-05   Priority: Should   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-054   Judgement: inferred: implements the "assigned to them" part of REQ-054; no statement creates assignments

**Narrative.** As a recruiter, I want to assign interviewers to a candidate, so that each interviewer sees only the candidates they interview.

**Why it matters.** PRD goal 3: needed by the permission rule that scopes interviewers to assigned candidates.

**From the PRD.**

- REQ-054: "Interviewers cannot reject, edit criteria, upload resumes or override scores. (PRD section 3 table and section 8.1; only a recruiter can reject, view the cost log, or approve criteria)"

**Preconditions.**

- An interviewer account and a candidate exist.

**Acceptance criteria.**

- AC-US-00-016-1. Given a candidate, when the recruiter assigns an interviewer, then the interviewer can see that candidate and the kit.
Covers: REQ-054
- AC-US-00-016-2. Given an assignment, when the recruiter removes it, then the interviewer no longer sees the candidate.
Covers: REQ-054
- AC-US-00-016-3. Given an interviewer, when they try to assign anyone, then the service refuses.
Covers: REQ-054

**Not in this story.**

- Scheduling interviews (PRD non-goal: calendar scheduling).

**Depends on.**

- US-00-012: role checks

**Assumptions.**

- Recruiters assign interviewers per candidate (Q-004).



## EP-06 Interview with a kit, feedback and comparison

Goal: A recruiter generates an interview kit, interviewers submit scored feedback, and candidates are compared side by side.
Covers: REQ-031, REQ-032, REQ-033, REQ-034, REQ-035, REQ-036, REQ-037, REQ-038, REQ-039, REQ-052, REQ-062

### US-00-013 Generate and edit an interview kit

Epic: EP-06   Priority: Should   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-031, REQ-032, REQ-033, REQ-034, REQ-035   Judgement: merged from REQ-031 to REQ-035

**Narrative.** As a recruiter, I want a per-role interview kit I can edit, so that every interviewer asks comparable questions with a shared view of strong and weak answers.

**Why it matters.** PRD problem statement: unstructured interviews cannot be compared fairly.

**From the PRD.**

- REQ-031: "Once a role is approved, the recruiter can generate an interview kit for it."
- REQ-032: "The kit contains questions per criterion."
- REQ-033: "Each question includes what a strong answer looks like and what a weak answer looks like."
- REQ-034: "The recruiter can edit or remove questions. Interviewers see the edited version."
- REQ-035: "The kit is per role and is not personalised to any candidate (avoids leaking anonymized data back into prompts)."

**Preconditions.**

- An Approved role (US-00-002).

**Acceptance criteria.**

- AC-US-00-013-1. Given an Approved role, when the recruiter asks to generate a kit, then a kit is generated for that role, one model call per criterion so that no call passes the 1,500 token cap; for a Draft role the action is blocked.
Covers: REQ-031
- AC-US-00-013-2. Given a generated kit, when it is viewed, then it holds questions grouped by criterion.
Covers: REQ-032
- AC-US-00-013-3. Given each question, when it is shown, then it has a description of a strong answer and of a weak answer.
Covers: REQ-033
- AC-US-00-013-4. Given the kit prompt, when it is built, then it contains the job description and criteria and no candidate data.
Covers: REQ-035
- AC-US-00-013-5. Given a question, when the recruiter edits, reorders, deletes or regenerates it, then the change is saved.
Covers: REQ-034
- AC-US-00-013-6. Given an interviewer opening the kit, when edits exist, then they see the edited version, read-only.
Covers: REQ-034

**Not in this story.**

- Personalised questions for a candidate (PRD: kit is per role).
- Feedback (US-00-014).

**Depends on.**

- US-00-002: approved criteria
- US-02-001: the gateway the kit call goes through

**Assumptions.**

- none



### US-00-014 Submit scored interviewer feedback

Epic: EP-06   Priority: Should   Points: TBD (estimate)
Persona: Interviewer (group 00)   Ticket: unassigned
Covers: REQ-036, REQ-037, REQ-062   Judgement: merged from REQ-036, REQ-037, REQ-062

**Narrative.** As an interviewer, I want to score each criterion and comment, so that my feedback is structured and comparable.

**Why it matters.** PRD problem statement: unstructured feedback makes fair comparison impossible.

**From the PRD.**

- REQ-036: "An interviewer submits a score and a short comment per criterion for each candidate they interview."
- REQ-037: "Feedback is locked after submission except for a recruiter-approved edit."
- REQ-062: "The safe default is to hide the model scores until their feedback is submitted, to avoid anchoring."

**Preconditions.**

- An assigned candidate and a kit (US-00-016, US-00-013).

**Acceptance criteria.**

- AC-US-00-014-1. Given an assigned interviewer and a candidate they interview, when they open the form, then it shows one section per criterion with the kit questions, a score selector matching the rubric scale, and a comment field.
Covers: REQ-036
- AC-US-00-014-2. Given every criterion scored and commented, when the interviewer submits, then the feedback is saved.
Covers: REQ-036
- AC-US-00-014-3. Given a criterion without a score, when the interviewer tries to submit, then Submit is disabled and progress (for example "3 of 6 criteria scored") is shown.
Covers: REQ-036
- AC-US-00-014-4. Given submitted feedback, when the interviewer reopens the form, then it is read-only.
Covers: REQ-037
- AC-US-00-014-5. Given a recruiter-approved edit, when the interviewer changes their feedback, then the change is saved and recorded.
Covers: REQ-037
- AC-US-00-014-6. Given an interviewer who has not submitted, when they view the candidate, then model resume scores are hidden.
Covers: REQ-062
- AC-US-00-014-7. Given an interviewer who has submitted, when they view the candidate, then model scores are shown.
Covers: REQ-062

**Not in this story.**

- The comparison view (US-00-015).
- Assigning interviewers (US-00-016).

**Depends on.**

- US-00-013: the kit shown in the form
- US-00-016: assignment
- US-00-012: role checks

**Assumptions.**

- Model scores stay hidden until submit (Q-008).



### US-00-015 Compare candidates side by side

Epic: EP-06   Priority: Should   Points: TBD (estimate)
Persona: Recruiter (group 00)   Ticket: unassigned
Covers: REQ-038, REQ-039, REQ-052, REQ-062   Judgement: merged from REQ-038, REQ-039, plus quality REQ-052 and REQ-062 (decisions.md conflict 4)

**Narrative.** As a recruiter, I want to compare two to four candidates by criterion, so that I can see where they differ and where interviewers disagree.

**Why it matters.** PRD problem statement: candidates cannot be compared fairly without a shared view.

**From the PRD.**

- REQ-038: "The comparison view shows 2 to 4 candidates side by side, per criterion, with resume score, override, and interviewer scores and comments."
- REQ-039: "The comparison view highlights disagreement between interviewers on the same criterion."
- REQ-052: "WCAG 2.1 AA for text contrast and keyboard navigation."

**Preconditions.**

- Scores exist and at least two candidates have feedback (US-00-008, US-00-014).

**Acceptance criteria.**

- AC-US-00-015-1. Given two to four selected candidates, when the recruiter opens the comparison view, then candidates appear side by side with criteria as rows grouped by must-have and nice-to-have.
Covers: REQ-038
- AC-US-00-015-2. Given a cell, when it is shown, then it holds the resume score, any override, and interviewer scores and comments.
Covers: REQ-038
- AC-US-00-015-3. Given fewer than two or more than four candidates selected, when compare is opened, then it is refused with a message.
Covers: REQ-038
- AC-US-00-015-4. Given interviewers who scored the same criterion differently, when the view renders, then the disagreement is marked with a warning icon and a tooltip.
Covers: REQ-039
- AC-US-00-015-5. Given a keyboard-only user, when they use the view, then every control is reachable at WCAG 2.1 AA contrast.
Covers: REQ-052
- AC-US-00-015-6. Given an interviewer who has not submitted feedback for a candidate, when they open the comparison view, then that candidate's resume score and override cells are hidden for them and no evidence quote is shown; the hiding is done by the query, not by the client.
Covers: REQ-062

**Not in this story.**

- Exporting the comparison (not in the PRD).
- Hiding model scores from interviewers before submit (US-00-014, Q-008).

**Depends on.**

- US-00-014: interviewer scores
- US-00-008: resume scores

**Assumptions.**

- none



## EP-07 Prove the rules and the quality

Goal: A maintainer runs tests and two evals from recordings and shows the demo, all inside the USD 8 budget.
Covers: REQ-056, REQ-057, REQ-058, REQ-060

### US-02-004 Prove the core rules with automated tests

Epic: EP-07   Priority: Must   Points: TBD (estimate)
Persona: Maintainer (group 02)   Ticket: unassigned
Covers: REQ-056   Judgement: story from REQ-056

**Narrative.** As a maintainer, I want automated tests for the rules that carry the fairness and budget claims, so that a regression fails the build.

**Why it matters.** PRD goals 2 to 5: each rule is enforced in code and covered by tests.

**From the PRD.**

- REQ-056: "Anonymizer: each of the six fields is removed, with the hard cases listed in 5.3. Quote verification: fabricated, altered and partial quotes are caught. Gateway: budget cutoff at USD 8, `max_tokens` cap, per-call logging, replay mode, refusal of non-anonymized input. Permissions and workflow tests as listed. (PRD section 8.1 table, joined)"

**Preconditions.**

- The anonymizer, quote check, gateway, permissions and workflow gates exist.

**Acceptance criteria.**

- AC-US-02-004-1. Given the anonymizer suite, when it runs, then each of the six fields is shown removed, with tests for names in emails and URLs, school names that reveal location or religion, headers and footers, names that are also common words, multi-part names, pronouns inside sentences, and dates in different formats.
Covers: REQ-056
- AC-US-02-004-2. Given the quote suite, when it runs, then fabricated, altered and partial quotes are caught and whitespace differences are tolerated.
Covers: REQ-056
- AC-US-02-004-3. Given the gateway suite, when it runs, then it proves the USD 8 cutoff, the `max_tokens` cap, per-call logging, replay mode and refusal of non-anonymized input.
Covers: REQ-056
- AC-US-02-004-4. Given the permissions suite, when it runs, then it proves interviewers cannot reject, edit criteria, upload resumes or override scores.
Covers: REQ-056
- AC-US-02-004-5. Given the workflow suite, when it runs, then it proves nothing runs on a Draft role and no stage changes without a user action.
Covers: REQ-056

**Not in this story.**

- The two evals (US-02-005, US-02-006).
- Frontend end-to-end tests (added by the stories that build screens).

**Depends on.**

- US-00-004: the anonymizer
- US-00-007: the quote check
- US-02-001: the gateway
- US-00-012: permissions

**Assumptions.**

- none



### US-02-005 Run the scoring agreement eval

Epic: EP-07   Priority: Must   Points: TBD (estimate)
Persona: Maintainer (group 02)   Ticket: unassigned
Covers: REQ-057   Judgement: story from REQ-057

**Narrative.** As a maintainer, I want to compare the tool's scores with reference labels, so that I can report how consistent scoring is.

**Why it matters.** PRD goal 5: quality is measured, not assumed.

**From the PRD.**

- REQ-057: "Proposed pass threshold: at least 80% of criterion scores within 1 point of the label (to be confirmed once a baseline run exists)."

**Preconditions.**

- Seed resumes and labels exist (US-02-007) and replay works (US-02-003).

**Acceptance criteria.**

- AC-US-02-005-1. Given 40 synthetic resumes with labels, when the eval runs from recorded responses, then per-criterion scores are compared with the labels.
Covers: REQ-057
- AC-US-02-005-2. Given the comparison, when the report is produced, then it shows exact agreement, agreement within 1 point, and weighted kappa.
Covers: REQ-057
- AC-US-02-005-3. Given the results, when at least 80% of criterion scores are within 1 point of the label, then the eval passes; the threshold is confirmed after a baseline run.
Covers: REQ-057
- AC-US-02-005-4. Given the report, when it is read, then it states the labels come from another model, so the result measures consistency with a reference and is not ground truth (Q-010).
Covers: REQ-057

**Not in this story.**

- Human-written labels (Q-010).
- The name-swap eval (US-02-006).

**Depends on.**

- US-00-008: the pipeline's scores
- US-02-003: recordings
- US-02-007: data and labels

**Assumptions.**

- No human labels in the first build (Q-010).



### US-02-006 Run the name-swap eval

Epic: EP-07   Priority: Must   Points: TBD (estimate)
Persona: Maintainer (group 02)   Ticket: unassigned
Covers: REQ-058   Judgement: story from REQ-058

**Narrative.** As a maintainer, I want to swap names before anonymization and compare scores, so that I can show the anonymizer removes the name signal.

**Why it matters.** PRD goal 2: the anonymizer's effect is tested, not claimed.

**From the PRD.**

- REQ-058: "Swap the candidate name (and any name-linked signals) **before** anonymization, run the full pipeline on both versions, and compare scores."

**Preconditions.**

- Name-swap pairs exist (US-02-007) and replay works (US-02-003).

**Acceptance criteria.**

- AC-US-02-006-1. Given 20 resumes prepared as name-swap pairs across different name origins and genders, when the eval runs, then the name and any name-linked signals are swapped before anonymization.
Covers: REQ-058
- AC-US-02-006-2. Given each pair, when the eval runs, then the full pipeline runs on both versions from recordings.
Covers: REQ-058
- AC-US-02-006-3. Given the results, when no criterion score differs by more than 1 point in all 20 pairs, then the eval passes; identical anonymized text and equal scores is the ideal.
Covers: REQ-058
- AC-US-02-006-4. Given a failed pair, when the report is produced, then it lists the pair, criterion, both scores and a diff of the anonymized texts.
Covers: REQ-058
- AC-US-02-006-5. Given the report, when it is read, then it states it shows removal of the named signals and not absence of proxy bias.
Covers: REQ-058

**Not in this story.**

- The agreement eval (US-02-005).

**Depends on.**

- US-00-008: the pipeline's scores
- US-02-003: recordings
- US-02-007: pairs

**Assumptions.**

- none



### US-02-007 Load the seed data

Epic: EP-07   Priority: Must   Points: TBD (estimate)
Persona: Maintainer (group 02)   Ticket: unassigned
Covers: REQ-060   Judgement: story from REQ-060

**Narrative.** As a maintainer, I want seeded roles, resumes and labels, so that evals and the demo run on the same known data.

**Why it matters.** PRD goal 5: the evals and the demo need synthetic data with no real people.

**From the PRD.**

- REQ-060: "2 roles with job descriptions and approved criteria. 40 synthetic resumes written by Claude Code, split across the 2 roles, in PDF and DOCX, with varied strength levels and formats. Claude Code labels for those resumes (the eval ground truth). 20 of the resumes prepared as name-swap pairs. Synthetic data must contain no real people."

**Preconditions.**

- A way to create roles and criteria (US-00-002).

**Acceptance criteria.**

- AC-US-02-007-1. Given the seed command, when it runs, then two roles exist with job descriptions and approved criteria.
Covers: REQ-060
- AC-US-02-007-2. Given the seed, when it runs, then 40 synthetic resumes exist, split across the two roles, in PDF and DOCX, with varied strength levels and formats.
Covers: REQ-060
- AC-US-02-007-3. Given the seed, when it runs, then labels exist for those resumes as the eval ground truth.
Covers: REQ-060
- AC-US-02-007-4. Given the seed, when it runs, then 20 of the resumes are prepared as name-swap pairs.
Covers: REQ-060
- AC-US-02-007-5. Given the seed data, when reviewed, then it contains no real people.
Covers: REQ-060

**Not in this story.**

- Any real candidate data.

**Depends on.**

- US-00-002: roles and approved criteria

**Assumptions.**

- none

