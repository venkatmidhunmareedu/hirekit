# Noticed ledger

Things seen in passing or left undone while building, kept so they are not lost when a session ends.

Rule: every task appends its "Noticed" and "Not done" items here, in the same commit as the task. Open items are reviewed when a task starts. Status is `open`, `done` (name the fixing task) or `dropped` (say why). Where this ledger was backfilled from chat reports and the outcome was not confirmed, the row is `open` with "verify".

Backfilled on 2026-10-03 from the reports of HK-17 to HK-40. Owner task numbers after HK-40 (HK-41 and up) are tentative, from the first-live-run plan; they are not assigned yet.

| ID | Source | Item | Why it matters | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| N-001 | HK-17 to HK-38 | `verify.py` scan does not check religion terms, titles or pronouns, which anonymizer LLD section 4 says it should | The scan is the independent backstop; a gap in a pass is not repaired | unassigned | open |
| N-002 | HK-24 | `verify.py` name lookaround still skips a name in square brackets (`[Jane]`); the names pass now handles it | A name in brackets that the pass misses would not be repaired by the scan | unassigned | open |
| N-003 | HK-23 | Cities list is a 339-entry seed; the LLD assumes about 3,000 | A small town can survive anonymization | unassigned | open |
| N-004 | HK-23 | `ID 12345` after a comma is masked as an Idaho ZIP | Harmless over-masking of an id number | unassigned | open |
| N-005 | HK-18 to HK-26 | `ANONYMIZER_VERSION` is still 1 although patterns changed across the passes | Bump when the Worker starts persisting it; replay keys depend on it | HK-40+ (Worker run) | open |
| N-006 | HK-26 | `0001_initial_schema.py` docstring says `schema.sql` and its SQL are byte-for-byte identical; they now differ by `anonymizer_version` | Misleading docstring | unassigned | open |
| N-007 | HK-26 | `tests/test_migration_sql.py` now strips `anonymizer_version` lines before comparing `schema.sql` with 0001; meant to be deleted at first release | A relaxed (not weakened) guard that must not linger | unassigned | open |
| N-008 | HK-26 | Worker does not yet write `ANONYMIZER_VERSION` with the text; every row gets the default 1 | Version stays 1 until written | Worker wiring task | open |
| N-009 | HK-30 | `app.jobs.job_description` does not exist; nothing implements `JobDescriptionLoader` | Propose-criteria and kit handlers cannot run live | HK-43 (plan task 5) | open |
| N-010 | HK-27 | LLD `LeaseLost` is `LeaseLostError` in code (lint rule N818); `Retry` gained a `code` field | LLD wording differs from code | unassigned | open |
| N-011 | HK-27 | Failure sentences for several errors were written without LLD wording ("Something went wrong. Try again.", budget not initialised, database outage) | Recruiters may see them; a reviewer should read them | unassigned | open |
| N-012 | HK-27 | Provider credit exhaustion records `budget_reached`; a corrupt recording records `recording_missing` (per the LLD, not the error codes) | Recorded codes differ from the error classes' own codes | unassigned | open |
| N-013 | HK-27 | One `# type: ignore[misc]` in `tests/worker/test_outcome.py` with a stated reason | Allowed suppression, listed for visibility | unassigned | open |
| N-014 | HK-29 | LLD is ambiguous on `Stale`: loop writes nothing for `Succeeded` or `Stale`, so a handler returning `Stale` without writing leaves the job `running` until the lease expires | Handlers must write their own end state | unassigned | open (handlers in HK-32, 36, 37 write it; update the LLD) |
| N-015 | HK-29 | Worker section 10 `make doctor` output for running jobs "added with item 3" | Was not in the item's file list | HK-30 | done (HK-30) |
| N-016 | HK-29 | `__main__.py` has no unit test and does not build the gateway | `HANDLERS` is empty, so real jobs fail as `no_handler` | HK-44 (plan task 6) | open |
| N-017 | HK-28 | Reclaim-at-attempt-3 candidate `failed` UPDATE sat inside `jobs.py` | Belongs behind `worker_writes` | HK-30 | done (HK-30) |
| N-018 | HK-28 | `claim` fails attempt-exhausted jobs internally; the loop never sees a "marked failed" result | LLD diagram 4.1 shows one; the loop needs nothing from it today | HK-29 | dropped (decided no change; claim already fails the candidate) |
| N-019 | HK-30 | `JobContext.fenced()` locked the job before the role, against LLD section 5; deadlock risk with a criteria edit | Real deadlock | HK-31 | done (HK-31, with an integration test) |
| N-020 | HK-31 | `generate_kit` rule "lock all of the role's open jobs in ascending id, own row included" was not implemented | Deadlock risk between kit writes and cancel paths | HK-37 | done (HK-37, `fence(lock_open_jobs=True)`) |
| N-021 | HK-31 | `fence()` also takes a shared role lock for progress and store-text writes, which the LLD does not list | Slightly more contention; one global lock order | unassigned | open |
| N-022 | HK-30 | `app.anonymizer.anonymize` returned `Anonymized` but the `Anonymizer` port expected a tuple | Needed an adapter or a port change | HK-35 | done (HK-35, port now returns `Anonymized`) |
| N-023 | HK-30 | The "every Worker write is fenced" guard accepts any helper that takes a `session` parameter (`unfenced_calls` ceiling) | A helper called outside a fence is not caught | unassigned | open |
| N-024 | HK-35 | "Name not found" has no column or note in the schema; the handler stores `identity_name = NULL` | Reveal identity must derive the warning from the null | API LLD / UI design | open |
| N-025 | HK-35 | `process_resume` handler returns an explicit `Failed` for extraction errors while `policy.next_step` also maps `ExtractionError` | Mapping is now a backup only | unassigned | open |
| N-026 | HK-35 | Integration halves of two process-resume tests were deferred | Needed real Postgres | HK-38 | done (HK-38) |
| N-027 | HK-36 | An empty proposal list from the criteria parser would insert zero criteria and still bump the version | The parser must reject an empty list | HK-42 (plan task 4) | open |
| N-028 | HK-36 | No pure proposal-validation function exists (weights, level counts, name uniqueness, kinds); the LLD puts it in the parser | Must be enforced when the criteria parser is built | HK-42 (plan task 4) | open |
| N-029 | HK-37 | LLD does not say how many questions per criterion to keep; `generate_kit` keeps all, `regenerate_question` keeps the first | Undecided product rule | unassigned | open |
| N-030 | HK-37 | `KIT_MAX_TOKENS` is 1500; the LLD estimates about 400 | A lower per-route value could be set with the kit prompt | HK-42 (plan task 4) | open |
| N-031 | HK-37 | LLD section 5 does not mention the `lock_open_jobs` fence variant | LLD out of date | unassigned | open |
| N-032 | HK-37 | `replace_kit` still locks the open jobs a second time after the fence | Redundant but harmless | unassigned | open |
| N-033 | HK-38 | `run_worker` claims any queued job, so a committed leftover from a crashed concurrency test would be picked up by the end-to-end tests | Test isolation | unassigned | open |
| N-034 | HK-38 | Worker LLD section 3 still shows the old `Anonymizer` port tuple; code and the anonymizer LLD use `Anonymized` | Stale LLD text | unassigned | open |
| N-035 | HK-38 | First live Worker run still lacks: extractor, scoring/criteria/kit prompts and parsers, job-description loader, gateway built in `__main__` with `build_handlers`, recorded responses, the API that enqueues jobs | Engine gate is blocked | HK-41 to HK-50 (plan) | open |
| N-036 | HK-32 | Quote verification had only a fake until the concrete verifier was built | Core domain rule | HK-33 | done (HK-33) |
| N-037 | HK-32 | `jobs.succeed` and `jobs.mark_stale` have only the HK-28 integration tests | Low coverage in fakes | unassigned | open |
| N-038 | HK-33 | Subprocess-based adversarial tests carried `# noqa: S603`; 9 suppressions broke AGENTS rule 6 | Rule 6 | HK-34 | done (HK-34, shared `timeout_helper`) |
| N-039 | HK-34 | `backend/alembic/env.py:12` still has `# noqa: F401` | Suppression under rule 6 | unassigned | open |
| N-040 | HK-39 | ADR-0010 says pydantic is already used for the parser (verified: pinned in `pyproject.toml`) | Claim was inferred | HK-39 | done |
| N-041 | HK-39 | ADR-0009 states the defusedxml licence (PSF) from memory | Unverified licence claim | HK-41 (extractor) | open (verify) |
| N-042 | HK-40 | `prompts.lock` hash check (an active version whose content changed) is not built; ADR-0011 notes it as a gap | Active versions can change silently | unassigned | open |
| N-043 | HK-40 | Frontmatter is parsed by a hand-written strict subset parser because PyYAML is only transitive; richer frontmatter would need PyYAML added deliberately | Dependency decision | unassigned | open |
| N-044 | HK-40 | Closing-delimiter escaping of variable values is deferred | Needed with the first real prompt | HK-42 (plan task 3) | open |
| N-045 | HK-40 | The check that each real prompt has `fixtures.json` and `CHANGELOG.md` only reads `fixtures.json` | CHANGELOG not checked | unassigned | open |
| N-046 | HK-40 | A non-prompt subfolder in `app/prompts/` would trip the fixtures test | Surprise later | unassigned | open |
| N-047 | HK-18 to HK-40 | Local `main` is behind `origin/main` (never fetched and fast-forwarded) | Branches cut from a stale base ref | engineer | open |
| N-048 | HK-27 to HK-40 | Branch stack HK-27 to HK-40 is unpushed (HK-18 to HK-26 are pushed) | Pushing and merging is the engineer's step (AGENTS rule 2) | engineer | open |
| N-049 | HK-28 to HK-40 | A local Docker Postgres container (`backend-postgres-1`) was started for integration tests | Local state, not in the repo | engineer | open |
| N-050 | HK-40 | Worker LLD is silent on the scoring, criteria, kit and extraction designs ("later designs") | The scoring prompt text, criteria schema, counts and weight defaults are undecided | HK-42 (plan tasks 3 and 4) | open |
