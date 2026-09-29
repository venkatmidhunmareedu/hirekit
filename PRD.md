# HireKit: Product Requirements Document

Version 0.1 (draft) · Status: ready for build planning

---

## 1. Overview

HireKit is a structured hiring tool that makes resume screening and interviewing consistent, evidence-backed and bias-resistant. AI does the heavy lifting (proposing criteria, scoring, generating interview kits), but people make every decision. Every model score must point to a quote from the resume, and no candidate is ever rejected without a recruiter action.

### 1.1 Problem

- Resume screening is slow, inconsistent and easily influenced by names, gender, age, photos, religion and location.
- Scores are hard to defend because there is no evidence trail.
- Interviewers use ad hoc questions and unstructured feedback, so candidates cannot be compared fairly.

### 1.2 Solution in one paragraph

A recruiter defines a role. The model proposes must-have and nice-to-have criteria with a scoring rubric, and the recruiter edits and approves them. Resumes are uploaded in bulk, stripped of identity signals by code, and scored by the model per criterion with verified evidence quotes. The recruiter reviews a ranked list, overrides scores with notes, and moves candidates through stages. The model then generates an interview kit, interviewers submit scored feedback per criterion, and a side-by-side view compares candidates.

---

## 2. Goals and non-goals

### 2.1 Goals

1. Every criterion score is backed by a verified quote from the resume, or explicitly marked "no evidence found".
2. The model never sees name, gender, age, photo, religion or location. This is enforced in code and covered by tests.
3. Humans stay in control. Criteria need recruiter approval, scores can be overridden, and only a recruiter can reject.
4. All model usage flows through one gateway that enforces a token cap, logs cost, and stops at a hard USD 8 budget.
5. Quality is measured, not assumed: an agreement eval and a name-swap eval run in CI from recorded responses.

### 2.2 Non-goals (out of scope)

- Job board posting
- Calendar scheduling
- Retention automation

### 2.3 Stretch goal

- Per-role data-retention setting (see section 9).

---

## 3. Users and permissions

| Capability | Recruiter | Interviewer |
|---|---|---|
| Create role and job description | Yes | No |
| Edit and approve criteria and rubric | Yes | No |
| Upload resumes | Yes | No |
| View ranked list and model scores | Yes | Limited (see 3.1) |
| Override a score (note required) | Yes | No |
| Move candidates between stages | Yes | No |
| Reject a candidate | Yes (only role that can) | No |
| View interview kit | Yes | Yes |
| Submit scored feedback per criterion | Optional | Yes |
| Use comparison view | Yes | Yes |
| View gateway cost log | Yes | No |

### 3.1 Interviewer visibility

Interviewers see the interview kit, the criteria, and the candidates assigned to them. Whether they see the model's resume scores before submitting their own feedback is an open question (section 12). The safe default is to hide the model scores until their feedback is submitted, to avoid anchoring.

---

## 4. Core workflow

1. **Role setup.** The recruiter enters a job description. The model proposes must-have and nice-to-have criteria and a scoring rubric. The recruiter edits and approves. Nothing downstream runs until approval.
2. **Resume intake.** Bulk upload of PDF and DOCX files, with text extraction and a per-file status (parsed, failed, needs attention).
3. **Anonymization.** Code removes name, gender, age, photo, religion and location before any model call. The anonymized text is the only text the model sees.
4. **Scoring.** For each criterion the model returns a score and an evidence quote, or "no evidence found". Code checks that the quote exists in the resume text. Failed checks are downgraded to "no evidence found" and flagged.
5. **Ranking and review.** The recruiter sees a ranked list, overrides any score with a required note, and moves candidates through stages. There is no auto-reject.
6. **Interview kit.** Per role, the model generates questions per criterion, each with what a strong and a weak answer look like.
7. **Feedback and comparison.** Interviewers score each criterion. A comparison view shows candidates side by side.

### 4.1 Candidate stages

`New` → `Screened` → `Interview` → `Offer` → `Hired`, plus `Rejected` and `Withdrawn`.

- Moving to `Rejected` requires a recruiter action and is logged with user, time and optional reason.
- The system never changes a stage on its own.
- Every stage change is stored in a stage history.

---

## 5. Functional requirements

### 5.1 Roles and criteria

| ID | Requirement |
|---|---|
| R-1 | A recruiter can create a role with a title and job description. |
| R-2 | The system calls the model once to propose must-have criteria, nice-to-have criteria and a rubric. |
| R-3 | Each criterion has a name, a type (must-have or nice-to-have), a weight, and rubric descriptors for each score level. |
| R-4 | The recruiter can add, edit, reorder and delete criteria and rubric text. |
| R-5 | A role has a status of `Draft` or `Approved`. Resume upload, scoring and kit generation are blocked while the role is `Draft`. |
| R-6 | Editing criteria after approval returns the role to `Draft` and marks existing scores as stale. Stale scores can be re-run on request. |

### 5.2 Resume intake

| ID | Requirement |
|---|---|
| I-1 | Bulk upload accepts PDF and DOCX. Other types are rejected with a clear message. |
| I-2 | Text is extracted per file. Extraction failures (scanned image, corrupt file) are listed and never silently dropped. |
| I-3 | The raw text is stored separately from the anonymized text. The model can only be given the anonymized text. |
| I-4 | Duplicate uploads are detected by content hash and flagged. |

### 5.3 Anonymization

Runs in code, before any model call, and is the only path to the model.

| ID | Requirement |
|---|---|
| A-1 | Remove or mask the candidate name, including name variants, initials and the name in headers and footers. |
| A-2 | Remove gender signals: explicit gender fields, titles (Mr, Ms, Mrs), and gendered pronouns. |
| A-3 | Remove age signals: date of birth, stated age, and graduation years or dates that reveal age where practical. |
| A-4 | Remove photos and embedded images. |
| A-5 | Remove religion signals: stated religion and religious affiliations. |
| A-6 | Remove location: address, city, state, country and postal code. |
| A-7 | Remove indirect identifiers that carry the same signals: email addresses, phone numbers, personal URLs and social profile links (names often appear in them). |
| A-8 | The gateway must only accept anonymized text. Passing raw resume text is a hard error. |

Skills, employers, job titles, projects and outcomes are kept, because they are the evidence.

**Known hard cases to test explicitly:** names in email addresses and URLs, school names that reveal location or religion, headers and footers, names that are also common words, multi-part names, pronouns inside sentences, and dates in different formats.

### 5.4 Scoring

| ID | Requirement |
|---|---|
| S-1 | For each approved criterion, the model returns a score on the rubric scale and one evidence quote, or the literal value "no evidence found". |
| S-2 | Code verifies that each quote exists in the anonymized resume text. Whitespace is normalized. No fuzzy matching that could accept invented text. |
| S-3 | A quote that fails verification is replaced by "no evidence found", the score is capped accordingly, and the item is flagged for review. |
| S-4 | A "no evidence found" criterion cannot receive a score above the lowest rubric level from the model. A recruiter override can change it, with a note. |
| S-5 | The model output is parsed against a strict schema. Malformed output is retried once and then marked as failed, never guessed. |
| S-6 | The final candidate score is a weighted total. Must-have criteria are shown separately so a strong nice-to-have cannot hide a missing must-have. |

**Proposed scale:** 0 to 4 per criterion, where 0 means no evidence. The scale is defined in the rubric and shown next to every score.

### 5.5 Ranking, overrides and stages

| ID | Requirement |
|---|---|
| K-1 | The recruiter sees candidates ranked by weighted score, with per-criterion scores, evidence quotes and flags. |
| K-2 | The recruiter can override any criterion score. A note is required. Both the model value and the override are kept and shown. |
| K-3 | Ranking is recalculated after overrides. |
| K-4 | The recruiter can filter by stage and sort by total or by any criterion. |
| K-5 | No candidate is rejected, hidden or de-ranked out of view by the system. Low scorers stay visible. |
| K-6 | Stage moves and overrides are recorded in an audit history with user and time. |

### 5.6 Interview kit

| ID | Requirement |
|---|---|
| Q-1 | Once a role is approved, the recruiter can generate an interview kit for it. |
| Q-2 | The kit contains questions per criterion. |
| Q-3 | Each question includes what a strong answer looks like and what a weak answer looks like. |
| Q-4 | The recruiter can edit or remove questions. Interviewers see the edited version. |
| Q-5 | The kit is per role and is not personalised to any candidate (avoids leaking anonymized data back into prompts). |

### 5.7 Interviewer feedback and comparison

| ID | Requirement |
|---|---|
| F-1 | An interviewer submits a score and a short comment per criterion for each candidate they interview. |
| F-2 | Feedback is locked after submission except for a recruiter-approved edit. |
| F-3 | The comparison view shows 2 to 4 candidates side by side, per criterion, with resume score, override, and interviewer scores and comments. |
| F-4 | The comparison view highlights disagreement between interviewers on the same criterion. |

---

## 6. Model gateway

Every model call in the product goes through one function. There is no other code path to the model.

| ID | Requirement |
|---|---|
| G-1 | Provider: OpenRouter. Model: `claude-haiku-4-5`. |
| G-2 | `max_tokens` is capped at 1500. Higher requests are clamped or rejected. |
| G-3 | Each call logs input tokens, output tokens, cost, purpose (criteria, scoring, kit, eval), role and timestamp. |
| G-4 | The gateway keeps a running total of spend. Once the total passes USD 8, further calls are refused with a clear error. |
| G-5 | A refused call returns a typed error that the UI shows plainly. The user never sees a silent failure. |
| G-6 | Replay mode: tests and CI use recorded responses keyed by a hash of the request. CI makes no live calls. |
| G-7 | A missing recording in replay mode fails the test. It never falls back to a live call. |
| G-8 | The gateway rejects input that has not been through the anonymizer. |
| G-9 | API keys live in environment configuration and are never logged. |

### 6.1 Budget planning

Rough call volume for the full build and eval cycle, to confirm USD 8 is enough:

- Criteria proposals for 2 roles (plus regeneration)
- Scoring for 40 resumes across their role's criteria
- Name-swap variants for 20 resumes (another 20 scoring runs, or 40 with both versions)
- Interview kit generation for 2 roles
- Re-runs while tuning prompts

Live runs should be done deliberately and recorded once, then replayed. Prompt changes invalidate recordings and need a fresh live run within budget.

---

## 7. Data model (rough)

- **User:** id, name, role (`recruiter` or `interviewer`).
- **Role:** id, title, job description, status (`Draft` or `Approved`), retention setting (stretch).
- **Criterion:** id, role id, name, type (must or nice), weight, order.
- **Rubric level:** criterion id, score value, descriptor.
- **Candidate:** id, role id, stage, created at.
- **ResumeText:** candidate id, raw text, anonymized text, source file, content hash.
- **Score:** candidate id, criterion id, model value, evidence quote, quote verified flag, override value, override note, overridden by, stale flag.
- **StageHistory:** candidate id, from stage, to stage, user, time, reason.
- **InterviewKit:** role id, questions.
- **Question:** kit id, criterion id, text, strong answer, weak answer.
- **Feedback:** candidate id, interviewer id, criterion id, score, comment, submitted at.
- **CallLog:** id, purpose, input tokens, output tokens, cost, running total, replayed flag, time.

Raw resume text is personal data. Access to it is limited to recruiters.

---

## 8. Quality, testing and evals

### 8.1 Tests

| Area | What must be proven |
|---|---|
| Anonymizer | Each of the six fields is removed, with the hard cases listed in 5.3. |
| Quote verification | Fabricated, altered and partial quotes are caught. Whitespace differences are tolerated. |
| Gateway | Budget cutoff at USD 8, `max_tokens` cap, per-call logging, replay mode, refusal of non-anonymized input. |
| Permissions | Interviewers cannot reject, edit criteria, upload resumes or override scores. |
| Workflow | Nothing runs on a `Draft` role. No stage change happens without a user action. |

### 8.2 Eval 1: scoring agreement

- **Data:** 40 synthetic resumes written by Claude Code, with Claude Code's own per-criterion scores as the labels.
- **Method:** run the tool's scoring on the same 40 resumes and compare per criterion.
- **Metrics:** exact agreement, agreement within 1 point, and weighted kappa.
- **Proposed pass threshold:** at least 80% of criterion scores within 1 point of the label (to be confirmed once a baseline run exists).
- **Note:** the labels come from another model, not from human hiring experts, so this measures consistency with a reference, not ground truth about candidate quality. Say this in the eval report.

### 8.3 Eval 2: name-swap

- **Data:** 20 resumes.
- **Method:** swap the candidate name (and any name-linked signals) **before** anonymization, run the full pipeline on both versions, and compare scores.
- **Pass condition:** no criterion score differs by more than 1 point between versions. Ideally the anonymized text is identical, so scores match exactly.
- **Purpose:** proves the anonymizer removes the signal. Swap names before anonymization so the test actually exercises the pipeline.
- **Coverage:** include swaps across different name origins and genders.

### 8.4 CI

- Unit tests and both evals run from recorded responses, with zero live calls.
- Live re-recording is a manual, budget-checked step.

---

## 9. Stretch: data-retention setting

- Per role, the recruiter can set how long candidate data is kept (for example 30, 90 or 180 days after the role closes).
- When the period ends, raw resume text and candidate records are deleted, and only anonymized aggregate data remains.
- This is a setting and a deletion job for stored data only. It is not retention marketing or candidate re-engagement, which is out of scope.

---

## 10. Non-functional requirements

- **Privacy:** raw resumes are visible to recruiters only. Logs never contain raw resume text or API keys.
- **Reliability:** upload of 100 resumes completes without blocking the UI, with per-file progress.
- **Transparency:** every score shows its source (model, verified quote, or override with note).
- **Accessibility:** WCAG 2.1 AA for text contrast and keyboard navigation.
- **Performance:** scoring one resume returns in a reasonable time for a batch run, with a visible queue.

---

## 11. Success metrics

| Metric | Target |
|---|---|
| Anonymizer test suite | 100% pass |
| Name-swap eval | 20 of 20 within 1 point |
| Scoring agreement (within 1 point) | 80% or higher (baseline to confirm) |
| Scores with a verified quote or "no evidence found" | 100% |
| Live model calls in CI | 0 |
| Total model spend in build and evals | At or below USD 8 |
| Candidates rejected without a recruiter action | 0 |

---

## 12. Open questions

1. Should interviewers see model resume scores before submitting their own feedback, or only after?
2. Should the recruiter's ranked list show candidate names by default, or anonymized IDs with an explicit "reveal identity" action?
3. Is the 0 to 4 scale right, or does the team prefer 1 to 5?
4. Which criteria weights are fixed by type, and which are editable per criterion?
5. Should auth be a simple seeded login for the first version, or a real provider?
6. Are human-written labels for a subset of resumes worth adding later, so the agreement eval is not model-vs-model only?

---

## 13. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Anonymization leaks through emails, URLs, school names or dates | Explicit tests for each channel, and the gateway refuses non-anonymized input. |
| Quote checking that is too strict or too loose | Normalize whitespace only, and never fuzzy-match to the point of accepting invented text. |
| Budget exhausted by evals | Record once, replay in CI, and make the gateway cut off cleanly at USD 8. |
| Name-swap test passes for the wrong reason | Swap names before anonymization so the test proves the pipeline does the work. |
| Over-trust in model scores | Show evidence next to every score, keep overrides one click away, and keep humans in every decision. |
| Eval labels come from a model | State the limitation, and add human labels later. |
| Bias signals that are not on the six-field list | Treat the list as a floor, and review test failures for new signals. |

---

## 14. Seed data

- 2 roles with job descriptions and approved criteria.
- 40 synthetic resumes written by Claude Code, split across the 2 roles, in PDF and DOCX, with varied strength levels and formats.
- Claude Code labels for those resumes (the eval ground truth).
- 20 of the resumes prepared as name-swap pairs.
- Synthetic data must contain no real people.

---

## 15. Build order

1. Data model, roles and auth
2. Gateway with budget cap and replay
3. Anonymizer with tests
4. Criteria proposal and approval flow
5. Resume upload, parsing and scoring with quote check
6. Ranked list, overrides and stages
7. Interview kit generation
8. Interviewer feedback and comparison view
9. Seed data, then evals
10. Stretch: retention setting

---

## 16. Product name and brand

The product is called **HireKit**. Visual identity and UI rules are in `Design.md`.
