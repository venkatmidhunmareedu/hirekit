# Roadmap: what is left after HK-45

Written 2026-10-03 from the Worker, API and anonymizer LLDs, `docs/designs/hirekit-build-plan.md` and the open rows in `docs/progress/noticed.md`. Task numbers after HK-45 are tentative. Update this file when a task finishes or the plan changes.

## Done

- Anonymizer: HK-17 to HK-26.
- Worker: HK-27 to HK-38, plus the lock-order fix (HK-31) and the suppression cleanup (HK-34).
- Missing Worker pieces: HK-39 to HK-45 (ADRs, prompt registry, extractor, scoring prompt, criteria and kit prompts, job-description loader, wiring).
- Pushed to origin: HK-18 to HK-26 only.

## A. Housekeeping (engineer)

1. Push and merge the stack bottom-up: HK-27 to HK-45 (19 local-only branches).
2. Fetch and fast-forward local `main`, which is behind `origin/main`.

## B. Finish the engine (before the UI)

3. Seed data (2 or 3 tasks, mostly data): 2 roles and 40 synthetic resumes (no real people), 20 name-swap pairs, the label CSV, a seed command, a PDF and DOCX builder script with a pinned library. Story US-02-007.
4. The two evals, run from recordings: agreement (US-02-005, label it a consistency check) and name-swap (US-02-006).
5. Eval sets for the scoring, criteria and kit prompts (N-060, N-067). All three versions are active with "NOT RUN" today.
6. Live-recording entry point for `make record`: one criteria job, one `process_resume` job, one kit job.
7. Live smoke test, about 3 calls and USD 0.02, to check token use, latency and `finish_reason=length`. Needs a key with a provider credit limit of at most USD 8 and `KEY_CREDIT_LIMIT_CONFIRMED=yes`.
8. Full recording pass, about 80 to 100 calls and about USD 0.5 per pass, 2 or 3 passes. Freeze prompts first: any prompt edit re-keys the recordings. This spends the USD 8 budget.
9. Run both evals on those recordings. Engine gate: both evals green.

## C. The API (api-lld section 9, 12 items)

10. Auth core. 11. Roles and criteria. 12. Jobs: propose, get, cancel, queue view. 13. Upload. 14. Ranked list, detail and text. 15. Override, stage and reveal. 16. Assignments and interviewer visibility. 17. Kit routes. 18. Feedback. 19. Compare. 20. Retry, rescore, cost log and budget. 21. Guards.

## D. Frontend (React with Vite in `web/`, not created yet)

22. Build the screens in PRD order (steps 1, 4, 6, 7, 8) with the `Design.md` tokens, once the API exists.
23. Record the demo tape, then add the budget-guarded live button last.

## E. Decisions waiting for the engineer

- Should the gateway wrap the user input (resume text, job description) in delimiters? (N-058, N-069; a gateway change.)
- Confirm the proposed criteria and kit numbers (N-064 to N-066): 1 to 8 criteria, weights 1 to 5, 2 to 3 questions per criterion, name and text length caps.
- A PDF over 20 pages is refused, not truncated (N-052). Keep it?
- Add `types-defusedxml` to remove one `# type: ignore` (N-051)?
- Fix the `# noqa: F401` in `backend/alembic/env.py` (a rule 6 breach that predates this work)?
- Newline check on recruiter edits to criterion names (N-070), when the API is built.

## Small open items

Pin the missing-recording status test (N-079). Dispose the engine if `build_worker` fails (N-077). `verify.py` scan gaps for religion, titles and pronouns (N-001, N-002). The 339-city seed list versus about 3,000 (N-003). Everything else is in `docs/progress/noticed.md`.
