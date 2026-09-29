# AGENTS.md

The standard every AI coding agent follows in this repository (Claude Code,
Cursor, Codex, Gemini CLI, Copilot). It loads into every session, so it holds
only what applies on every turn; the skills carry each step's detail.

Each step of the workflow names one skill, from Bearing or from another
installed pack. Unsure which one: `workflow` names the next step and its
skill.

## This repository

HireKit: structured, evidence-backed, anonymized resume screening. Product in
`PRD.md`, UI rules in `Design.md`, build plan in
`docs/designs/hirekit-build-plan.md`, technology choices in `docs/adr/` (index:
`docs/decisions.md`).

- Backend: Python 3.14, FastAPI, PostgreSQL, at the repository root (`app/`,
  `tests/`, `alembic/`). Frontend: React with Vite in `web/`, added later with
  its own gate. Neither exists yet; the layout above is the plan.
- Build order: engine first (gateway, anonymizer, scoring with quote check,
  both evals green), UI second.
- `make check` fails today with "0 python files, nothing checked". That is the
  gate working, not a fault; it passes once `app/` and `tests/` exist.

Domain rules (PRD.md), each with a test:

- The model only ever sees anonymized text. One gateway function is the only
  path to the model; it refuses non-anonymized input, caps `max_tokens` at
  1500, logs every call and stops at USD 8 total.
- Tests and CI use recorded responses only. A missing recording fails the test;
  it never falls back to a live call.
- A score has a quote that code found in the anonymized text, or "no evidence
  found". Quote matching normalizes whitespace only; no fuzzy matching.
- Nothing rejects, hides or re-stages a candidate except a recruiter action.
- Anonymization is a floor, not proof of fairness: proxy signals (schools,
  clubs, gendered wording, career gaps) can remain. Never claim otherwise in
  copy, docs or eval reports.
- The 40-resume agreement eval is a consistency check (same model family wrote
  the resumes, labels and scores). Label it that way.

## Ground rules

Breaking one gets the change rejected, whatever else it does.

1. Never commit to `main` (or the trunk the snapshot names). Work on a task branch.
2. Never push, open a merge or pull request, merge, tag or deploy. Prepare the
   command and hand it to the engineer.
3. Never commit a secret, key, certificate or `.env` file, and never read one
   into context.
4. Never touch a production system, database or bucket, not even to read.
5. Never rewrite history: no amend, rebase, force-push, `reset --hard`.
6. Never weaken a guardrail to go green: no lint suppression, no `any` or
   `@ts-ignore`, no skipped test, no lowered threshold, no relaxed CI rule.
7. Never add a dependency nobody asked for; propose it with the reason.
8. Never invent an API, field, table, variable or command; find it in the code first.
9. Stay in scope. What you notice in passing goes under "Noticed", unfixed.
10. Report honestly: a check you did not run is "not run", never "passing".
11. No AI attribution in commits, requests or documents.
12. No em dashes in prose; rewrite the sentence.

## Working here

- Every change has a task id and a branch: `start-task` creates
  `feature|bugfix|chore|docs/<ID>-<PascalName>`. One task per session.
- Every command is a Makefile target; `make help` lists them and `make check`
  is the gate CI runs.
- Search before reading, open only what you located, and copy the shape,
  naming and tests of the closest existing example.
- More than three files, or a change to a schema, API contract, auth or
  billing: agree a plan before the first edit.
- A technology choice is never silent: `tech-decision` gives options and a
  recommendation, the engineer decides, `adr` records it.
- Commits are Conventional with the task id at the end of the subject:
  `feat(auth): add OTP lockout [TASK-142]`.
- State that must outlive the session: `.bearing/state/` via `session-handoff` (local, ignored); shared progress: `docs/progress/<ID>.md` (committed).
  Scratch: `.scratch/`. Nothing at the root such as `NOTES.md`.
- Done means `definition-of-done` passed with evidence. Code, database, testing and
  security rules live in `.claude/rules/` and load with the files they cover.

## Reporting

End every task in this shape: `## Changed` (path: what and why), `## Verified`
(the command and the tail of its output), `## Not done` (asked, not delivered,
why), `## Noticed` (seen in passing, not fixed). No full diffs, no restating
the task.
