# Coverage: PRD statements to stories

PRD: PRD.md   Backlog: docs/product/backlog.md   Built: 2026-09-30

## Statements (inline, from PRD.md)

The PRD numbers its statements R-1, I-1, A-1 and so on. This table gives each a permanent REQ id, in PRD order. `prd` can move it into a PRD later.

| REQ | PRD ref | Statement |
| --- | --- | --- |
| REQ-001 | R-1 | "A recruiter can create a role with a title and job description." |
| REQ-002 | R-2 | "The system calls the model once to propose must-have criteria, nice-to-have criteria and a rubric." |
| REQ-003 | R-3 | "Each criterion has a name, a type (must-have or nice-to-have), a weight, and rubric descriptors for each score level." |
| REQ-004 | R-4 | "The recruiter can add, edit, reorder and delete criteria and rubric text." |
| REQ-005 | R-5 | "A role has a status of `Draft` or `Approved`. Resume upload, scoring and kit generation are blocked while the role is `Draft`." |
| REQ-006 | R-6 | "Editing criteria after approval returns the role to `Draft` and marks existing scores as stale. Stale scores can be re-run on request." |
| REQ-007 | I-1 | "Bulk upload accepts PDF and DOCX. Other types are rejected with a clear message." |
| REQ-008 | I-2 | "Text is extracted per file. Extraction failures (scanned image, corrupt file) are listed and never silently dropped." |
| REQ-009 | I-3 | "The raw text is stored separately from the anonymized text. The model can only be given the anonymized text." |
| REQ-010 | I-4 | "Duplicate uploads are detected by content hash and flagged." |
| REQ-011 | A-1 | "Remove or mask the candidate name, including name variants, initials and the name in headers and footers." |
| REQ-012 | A-2 | "Remove gender signals: explicit gender fields, titles (Mr, Ms, Mrs), and gendered pronouns." |
| REQ-013 | A-3 | "Remove age signals: date of birth, stated age, and graduation years or dates that reveal age where practical." |
| REQ-014 | A-4 | "Remove photos and embedded images." |
| REQ-015 | A-5 | "Remove religion signals: stated religion and religious affiliations." |
| REQ-016 | A-6 | "Remove location: address, city, state, country and postal code." |
| REQ-017 | A-7 | "Remove indirect identifiers that carry the same signals: email addresses, phone numbers, personal URLs and social profile links (names often appear in them)." |
| REQ-018 | A-8 | "The gateway must only accept anonymized text. Passing raw resume text is a hard error." |
| REQ-019 | S-1 | "For each approved criterion, the model returns a score on the rubric scale and one evidence quote, or the literal value "no evidence found"." |
| REQ-020 | S-2 | "Code verifies that each quote exists in the anonymized resume text. Whitespace is normalized. No fuzzy matching that could accept invented text." |
| REQ-021 | S-3 | "A quote that fails verification is replaced by "no evidence found", the score is capped accordingly, and the item is flagged for review." |
| REQ-022 | S-4 | "A "no evidence found" criterion cannot receive a score above the lowest rubric level from the model. A recruiter override can change it, with a note." |
| REQ-023 | S-5 | "The model output is parsed against a strict schema. Malformed output is retried once and then marked as failed, never guessed." |
| REQ-024 | S-6 | "The final candidate score is a weighted total. Must-have criteria are shown separately so a strong nice-to-have cannot hide a missing must-have." |
| REQ-025 | K-1 | "The recruiter sees candidates ranked by weighted score, with per-criterion scores, evidence quotes and flags." |
| REQ-026 | K-2 | "The recruiter can override any criterion score. A note is required. Both the model value and the override are kept and shown." |
| REQ-027 | K-3 | "Ranking is recalculated after overrides." |
| REQ-028 | K-4 | "The recruiter can filter by stage and sort by total or by any criterion." |
| REQ-029 | K-5 | "No candidate is rejected, hidden or de-ranked out of view by the system. Low scorers stay visible." |
| REQ-030 | K-6 | "Stage moves and overrides are recorded in an audit history with user and time." |
| REQ-031 | Q-1 | "Once a role is approved, the recruiter can generate an interview kit for it." |
| REQ-032 | Q-2 | "The kit contains questions per criterion." |
| REQ-033 | Q-3 | "Each question includes what a strong answer looks like and what a weak answer looks like." |
| REQ-034 | Q-4 | "The recruiter can edit or remove questions. Interviewers see the edited version." |
| REQ-035 | Q-5 | "The kit is per role and is not personalised to any candidate (avoids leaking anonymized data back into prompts)." |
| REQ-036 | F-1 | "An interviewer submits a score and a short comment per criterion for each candidate they interview." |
| REQ-037 | F-2 | "Feedback is locked after submission except for a recruiter-approved edit." |
| REQ-038 | F-3 | "The comparison view shows 2 to 4 candidates side by side, per criterion, with resume score, override, and interviewer scores and comments." |
| REQ-039 | F-4 | "The comparison view highlights disagreement between interviewers on the same criterion." |
| REQ-040 | G-1 | "Provider: OpenRouter. Model: `claude-haiku-4-5`." |
| REQ-041 | G-2 | "`max_tokens` is capped at 1500. Higher requests are clamped or rejected." |
| REQ-042 | G-3 | "Each call logs input tokens, output tokens, cost, purpose (criteria, scoring, kit, eval), role and timestamp." |
| REQ-043 | G-4 | "The gateway keeps a running total of spend. Once the total passes USD 8, further calls are refused with a clear error." |
| REQ-044 | G-5 | "A refused call returns a typed error that the UI shows plainly. The user never sees a silent failure." |
| REQ-045 | G-6 | "Replay mode: tests and CI use recorded responses keyed by a hash of the request. CI makes no live calls." |
| REQ-046 | G-7 | "A missing recording in replay mode fails the test. It never falls back to a live call." |
| REQ-047 | G-8 | "The gateway rejects input that has not been through the anonymizer." |
| REQ-048 | G-9 | "API keys live in environment configuration and are never logged." |
| REQ-049 | PRD §10 Privacy | "Raw resumes are visible to recruiters only. Logs never contain raw resume text or API keys." |
| REQ-050 | PRD §10 Reliability | "Upload of 100 resumes completes without blocking the UI, with per-file progress." |
| REQ-051 | PRD §10 Transparency | "Every score shows its source (model, verified quote, or override with note)." |
| REQ-052 | PRD §10 Accessibility | "WCAG 2.1 AA for text contrast and keyboard navigation." |
| REQ-053 | PRD §10 Performance | "Scoring one resume returns in a reasonable time for a batch run, with a visible queue." |
| REQ-054 | PRD §3 | "Interviewers cannot reject, edit criteria, upload resumes or override scores. (PRD section 3 table and section 8.1; only a recruiter can reject, view the cost log, or approve criteria)" |
| REQ-055 | PRD §4.1 | "Moving to `Rejected` requires a recruiter action and is logged with user, time and optional reason. The system never changes a stage on its own. Every stage change is stored in a stage history." |
| REQ-056 | PRD §8.1 | "Anonymizer: each of the six fields is removed, with the hard cases listed in 5.3. Quote verification: fabricated, altered and partial quotes are caught. Gateway: budget cutoff at USD 8, `max_tokens` cap, per-call logging, replay mode, refusal of non-anonymized input. Permissions and workflow tests as listed. (PRD section 8.1 table, joined)" |
| REQ-057 | PRD §8.2 | "Proposed pass threshold: at least 80% of criterion scores within 1 point of the label (to be confirmed once a baseline run exists)." |
| REQ-058 | PRD §8.3 | "Swap the candidate name (and any name-linked signals) **before** anonymization, run the full pipeline on both versions, and compare scores." |
| REQ-059 | PRD §8.4 | "Unit tests and both evals run from recorded responses, with zero live calls. Live re-recording is a manual, budget-checked step." |
| REQ-060 | PRD §14 | "2 roles with job descriptions and approved criteria. 40 synthetic resumes written by Claude Code, split across the 2 roles, in PDF and DOCX, with varied strength levels and formats. Claude Code labels for those resumes (the eval ground truth). 20 of the resumes prepared as name-swap pairs. Synthetic data must contain no real people." |
| REQ-061 | PRD §9 | "Per role, the recruiter can set how long candidate data is kept (for example 30, 90 or 180 days after the role closes)." |
| REQ-062 | PRD §3.1 | "The safe default is to hide the model scores until their feedback is submitted, to avoid anchoring." |

## Matrix

| REQ | Statement (short) | Judgement | Why | Covered by | AC ids |
| --- | --- | --- | --- | --- | --- |
| REQ-001 | Create a role | story | the recruiter can do something new: start a role | US-00-001 | AC-US-00-001-1 |
| REQ-002 | Model proposes criteria | story | merged with REQ-001: creating a role is only useful with the proposal that follows | US-00-001 | AC-US-00-001-2, AC-US-00-001-4 |
| REQ-003 | Criterion fields | criterion-of US-00-001 | it defines the shape of what the proposal returns, not a separate action | US-00-001 | AC-US-00-001-3 |
| REQ-004 | Edit criteria and rubric | story | editing is a separate action from proposing, and the recruiter's control point | US-00-002 | AC-US-00-002-1 |
| REQ-005 | Draft and Approved status | criterion-of US-00-002 | approval is the act of editing that unlocks the rest; the block is checked again in the upload and kit stories | US-00-002 | AC-US-00-002-2, AC-US-00-002-3 |
| REQ-006 | Edit after approval | criterion-of US-00-002 | a consequence of editing criteria, in the same story | US-00-002 | AC-US-00-002-4, AC-US-00-002-5, AC-US-00-002-6 |
| REQ-007 | Bulk upload PDF and DOCX | story | the recruiter can bring resumes in | US-00-003 | AC-US-00-003-1, AC-US-00-003-2 |
| REQ-008 | Extraction failures listed | criterion-of US-00-003 | the failure path of the same upload | US-00-003 | AC-US-00-003-3 |
| REQ-009 | Raw and anonymized text apart | story | a storage boundary that the recruiter relies on but no other story delivers | US-00-005 | AC-US-00-005-1, AC-US-00-005-2 |
| REQ-010 | Duplicate uploads flagged | criterion-of US-00-003 | a condition on the upload | US-00-003 | AC-US-00-003-4 |
| REQ-011 | Remove name | story | seeds the anonymization story; it is the first of seven signals that one story delivers | US-00-004 | AC-US-00-004-1 |
| REQ-012 | Remove gender signals | criterion-of US-00-004 | one more signal removed by the same story | US-00-004 | AC-US-00-004-2 |
| REQ-013 | Remove age signals | criterion-of US-00-004 | one more signal removed by the same story | US-00-004 | AC-US-00-004-3 |
| REQ-014 | Remove photos | criterion-of US-00-004 | one more signal removed by the same story | US-00-004 | AC-US-00-004-4 |
| REQ-015 | Remove religion signals | criterion-of US-00-004 | one more signal removed by the same story | US-00-004 | AC-US-00-004-5 |
| REQ-016 | Remove location | criterion-of US-00-004 | one more signal removed by the same story | US-00-004 | AC-US-00-004-6 |
| REQ-017 | Remove indirect identifiers | criterion-of US-00-004 | one more signal removed by the same story | US-00-004 | AC-US-00-004-7 |
| REQ-018 | Gateway accepts only anonymized text | story | the enforcement that makes anonymization the only path to the model | US-00-005 | AC-US-00-005-3 |
| REQ-019 | Score and quote per criterion | story | the recruiter gets a scored, evidenced result per criterion | US-00-006 | AC-US-00-006-1, AC-US-00-006-2 |
| REQ-020 | Quote verified in resume text | story | verification is a separate check from producing the score, and the evidence guarantee rests on it | US-00-007 | AC-US-00-007-1, AC-US-00-007-2 |
| REQ-021 | Failed quote downgraded | criterion-of US-00-007 | what happens when the check in REQ-020 fails | US-00-007 | AC-US-00-007-3, AC-US-00-007-4 |
| REQ-022 | No evidence caps the score | criterion-of US-00-007 | a limit on the score once the quote check fails | US-00-007 | AC-US-00-007-5, AC-US-00-007-6 |
| REQ-023 | Strict schema, one retry | criterion-of US-00-006 | the failure path of the scoring call | US-00-006 | AC-US-00-006-3, AC-US-00-006-4, AC-US-00-006-5 |
| REQ-024 | Weighted total, must-haves apart | story | the recruiter reads one total and the must-have gap beside it | US-00-008 | AC-US-00-008-1, AC-US-00-008-2, AC-US-00-008-3 |
| REQ-025 | Ranked list | story | the recruiter can review candidates in order | US-00-009 | AC-US-00-009-1, AC-US-00-009-2 |
| REQ-026 | Override with a note | story | the recruiter can change a score, a distinct action from reading the list | US-00-010 | AC-US-00-010-1, AC-US-00-010-2, AC-US-00-010-3 |
| REQ-027 | Ranking recalculated | criterion-of US-00-010 | what an override causes | US-00-010 | AC-US-00-010-4 |
| REQ-028 | Filter and sort | criterion-of US-00-009 | controls on the ranked list | US-00-009 | AC-US-00-009-3 |
| REQ-029 | No auto-reject, hide or de-rank | criterion-of US-00-009 | a limit on how the ranked list behaves | US-00-009 | AC-US-00-009-4 |
| REQ-030 | Audit history | criterion-of US-00-010 | the record kept for an override; the stage move half is checked in US-00-011 | US-00-010, US-00-011 | AC-US-00-010-5, AC-US-00-011-2 |
| REQ-031 | Generate kit once approved | story | the recruiter can produce a kit | US-00-013 | AC-US-00-013-1 |
| REQ-032 | Questions per criterion | criterion-of US-00-013 | the content of the kit | US-00-013 | AC-US-00-013-2 |
| REQ-033 | Strong and weak answers | criterion-of US-00-013 | the content of each question | US-00-013 | AC-US-00-013-3 |
| REQ-034 | Edit or remove questions | criterion-of US-00-013 | editing acts on the same kit and shares its screen | US-00-013 | AC-US-00-013-5, AC-US-00-013-6 |
| REQ-035 | Kit is per role | criterion-of US-00-013 | a limit on what goes into the kit prompt | US-00-013 | AC-US-00-013-4 |
| REQ-036 | Score and comment per criterion | story | the interviewer can record structured feedback | US-00-014 | AC-US-00-014-1, AC-US-00-014-2, AC-US-00-014-3 |
| REQ-037 | Feedback locked after submit | criterion-of US-00-014 | the state after the submit in REQ-036 | US-00-014 | AC-US-00-014-4, AC-US-00-014-5 |
| REQ-038 | Comparison view | story | the recruiter and interviewer can compare candidates | US-00-015 | AC-US-00-015-1, AC-US-00-015-2, AC-US-00-015-3 |
| REQ-039 | Highlight disagreement | criterion-of US-00-015 | a marking inside the same view | US-00-015 | AC-US-00-015-4 |
| REQ-040 | OpenRouter and claude-haiku-4-5 | story | merged with REQ-041, REQ-042 and REQ-048: one gateway function all model calls pass through | US-02-001 | AC-US-02-001-1, AC-US-02-001-2 |
| REQ-041 | max_tokens capped at 1500 | criterion-of US-02-001 | a limit enforced inside the gateway | US-02-001 | AC-US-02-001-3 |
| REQ-042 | Log each call | criterion-of US-02-001 | logging done inside the gateway | US-02-001 | AC-US-02-001-4 |
| REQ-043 | USD 8 running total | story | the budget cutoff is a distinct capability with its own state | US-02-002 | AC-US-02-002-1, AC-US-02-002-2 |
| REQ-044 | Typed error shown plainly | criterion-of US-02-002 | how the cutoff in REQ-043 surfaces | US-02-002 | AC-US-02-002-3, AC-US-02-002-4 |
| REQ-045 | Replay mode | story | recorded replay is a separate capability that tests and the demo rely on | US-02-003 | AC-US-02-003-1, AC-US-02-003-4 |
| REQ-046 | Missing recording fails | criterion-of US-02-003 | a limit on replay mode | US-02-003 | AC-US-02-003-2, AC-US-02-003-3 |
| REQ-047 | Gateway rejects non-anonymized input | duplicate-of REQ-018 | same outcome as REQ-018; both cited in US-00-005 | US-00-005 | AC-US-00-005-3, AC-US-00-005-4 |
| REQ-048 | Keys in environment, never logged | criterion-of US-02-001 | a rule for how the gateway handles its key | US-02-001 | AC-US-02-001-5 |
| REQ-049 | Raw resumes recruiters only, clean logs | non-functional | a quality that US-00-005, US-00-012 and US-02-001 carry as criteria | US-00-005, US-00-012, US-02-001 | AC-US-02-001-6, AC-US-00-005-5, AC-US-00-005-6, AC-US-00-012-6 |
| REQ-050 | 100 resumes without blocking | non-functional | a quality that the upload story carries as a criterion | US-00-003 | AC-US-00-003-5 |
| REQ-051 | Every score shows its source | non-functional | a quality that the total and source display carries as a criterion | US-00-008 | AC-US-00-008-4, AC-US-00-008-5 |
| REQ-052 | WCAG 2.1 AA | non-functional | a quality carried by the upload, ranked list and comparison stories | US-00-003, US-00-009, US-00-015 | AC-US-00-003-7, AC-US-00-009-5, AC-US-00-015-5 |
| REQ-053 | Visible queue for batch scoring | non-functional | a quality that the upload story carries as a criterion | US-00-003 | AC-US-00-003-6 |
| REQ-054 | Recruiter and interviewer permissions | story | who may do what is a capability of its own that every other story depends on | US-00-012, US-00-016 | AC-US-00-012-1, AC-US-00-012-2, AC-US-00-012-3, AC-US-00-012-4, AC-US-00-012-5, AC-US-00-016-1, AC-US-00-016-2, AC-US-00-016-3 |
| REQ-055 | Stages and rejection | story | the recruiter can move candidates through stages, a new capability | US-00-011 | AC-US-00-011-1, AC-US-00-011-2, AC-US-00-011-3, AC-US-00-011-4 |
| REQ-056 | Automated tests for the core rules | story | a maintainer-facing capability: proof that the rules hold | US-02-004 | AC-US-02-004-1, AC-US-02-004-2, AC-US-02-004-3, AC-US-02-004-4, AC-US-02-004-5 |
| REQ-057 | Scoring agreement eval | story | a distinct eval a maintainer runs | US-02-005 | AC-US-02-005-1, AC-US-02-005-2, AC-US-02-005-3, AC-US-02-005-4 |
| REQ-058 | Name-swap eval | story | a distinct eval a maintainer runs | US-02-006 | AC-US-02-006-1, AC-US-02-006-2, AC-US-02-006-3, AC-US-02-006-4, AC-US-02-006-5 |
| REQ-059 | CI from recordings only | criterion-of US-02-003 | how replay is used in CI | US-02-003 | AC-US-02-003-4, AC-US-02-003-5 |
| REQ-060 | Seed data | story | the data every eval and the demo run on | US-02-007 | AC-US-02-007-1, AC-US-02-007-2, AC-US-02-007-3, AC-US-02-007-4, AC-US-02-007-5 |
| REQ-061 | Data-retention setting (stretch) | out-of-scope | the PRD calls it a stretch goal (2.3); Q-012 decides it is out of the first build | none (Q-012) | none |
| REQ-062 | Hide model scores until feedback | criterion-of US-00-014 | a visibility rule on the feedback story; the PRD leaves the final call open, see Q-008 | US-00-014 | AC-US-00-014-6, AC-US-00-014-7 |

## Gaps

| REQ | Why uncovered | Proposed action |
| --- | --- | --- |
| none | REQ-061 is out of scope by decision (Q-012), not a gap | confirm Q-012, then plan the stretch through `prd` |

## Orphan stories

| Story | Reason it exists | Action |
| --- | --- | --- |
| demo (no story id yet) inferred: | the build plan (docs/designs/hirekit-build-plan.md) chose a full-pipeline demo from recordings; no PRD statement asks for it, so it is not written as a story | accept as a REQ via prd, then add a story / drop |

## Counts

stories-coverage: 62 REQ from docs/product/coverage.md (0 withdrawn), 61 covered, 1 out of scope, 0 gaps, 23 stories, 121 AC, 0 orphans, 0 problems
Verdict: covered
