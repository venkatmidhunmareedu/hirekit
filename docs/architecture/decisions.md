# Architecture decisions: HireKit

One row per decision, and every contradiction settled once so it is not
settled again, differently, in each file that runs into it.

## Decisions

| Id | Title | Area | Status | Reversibility |
| --- | --- | --- | --- | --- |
| ADR-0001 | Use PostgreSQL for the system of record | database | Accepted | awkward: schema, migrations and role setup are written for Postgres |
| ADR-0002 | Use Python (FastAPI) for the backend | backend language | Accepted | awkward: the anonymizer, quote checker and evals are written against Python libraries |
| ADR-0003 | Use React with Vite for the frontend | frontend | Accepted | cheap: the API is a separate service, so the client can be rewritten alone |
| ADR-0004 | Use a Postgres-backed queue for background jobs | messaging | Accepted | awkward: a broker needs an outbox to keep transactional enqueue |
| ADR-0005 | Use own session authentication with two roles | auth | Accepted | awkward: moving to an identity provider migrates users, sessions and login |
| ADR-0006 | Use REST with OpenAPI for the API | api style | Accepted | cheap: one client consumes the API |
| ADR-0007 | Use one repository with separate backend and web folders | repository layout | Accepted | awkward: splitting later moves a folder with its history and re-points CI |
| ADR-0008 | Keep uploaded resume files in a Postgres table until extracted | object storage | Accepted | cheap: two functions hide the table, so a volume or bucket can replace it |

## Conflicts that were settled

### Should the API and the React client live in one repository or two?

**Between:** the 2026-09-30 onboarding (python-api at the repository root, React planned in `web/`), ADR-0002 and ADR-0003 (two stacks), and the kit's repo plan (one stack per repository entry).

**Decision.** One repository, `HireKitApp`, with the Python service in `backend/` and the React app in `web/`, each with its own gate. The repo plan records it as `stack: none` with two apps.

**Why.** One clone and one demo command matter more to this project than the kit's one-stack-per-repository scaffolding. The recommendation shown was two repositories; the user chose this.

**Settled by:** midhun (project owner)

**What now has to change to match:**
- Move the root `Makefile`, `app/`, `tests/` and `alembic/` plans into `backend/`; the root Makefile delegates `check` to `backend/` and `web/`.
- AGENTS.md "This repository" layout lines and the CLAUDE.md snapshot.
- ADR-0007 records the decision.

### How can a retry be recorded and replayed when replay keys on a hash of the request?

**Between:** REQ-045 (recordings keyed by a hash of the request), REQ-023 (retry a malformed answer once), US-02-003, US-00-006.

**Decision.** The replay hash covers the request, the model id, the prompt version and the schema-retry index (0 for the first try, 1 for the retry after a malformed answer), so the two tries have different keys and can hold different recorded responses. Only successful (2xx) responses are recorded; transport retries (5xx, timeout, 429) are new job attempts and are not part of the key. (The user chose "attempt number in the hash"; the HLD review refined it to the schema-retry index so a live 5xx followed by a success cannot leave a recording that replay never looks up.)

**Why.** With a request-only hash, the retry is identical to the first call and replays the same malformed answer, so the retry path cannot be recorded or tested. With one counter for both kinds of retry, a recording made after a transport failure sits under a key the replay never asks for.

**Settled by:** midhun (project owner)

**What now has to change to match:**
- US-02-003 acceptance criteria: define the hash as request, model id, prompt version and schema-retry index.
- The gateway's low-level design: the request key includes `schema_retry` and the prompt version.

### Which entities does the data model need beyond the PRD's rough model?

**Between:** PRD section 7 (rough data model), ADR-0004 (jobs), ADR-0005 (users and credentials), REQ-023 (failed criterion), REQ-030 (override and stage audit history), Q-004 (interviewer assignments).

**Decision.** Add jobs, users with credentials, interviewer assignments, audit events (overrides and stage moves) and a per-criterion status (scored, no evidence, failed) to `docs/design/data-model.md`. Recordings stay as committed JSON files keyed by request hash, not a table.

**Why.** Each story or ADR names data the PRD's model has nowhere to keep, and every LLD would otherwise invent its own tables. The option shown to the user listed recordings among the tables; keeping them as files is the one difference, called out here for confirmation.

**Settled by:** midhun (project owner)

**What now has to change to match:**
- Write `docs/design/data-model.md` with `data-model` before any low-level design.
- PRD section 7 is not edited; it is a rough sketch and the data model supersedes it.

### What does an interviewer see in the comparison view before submitting feedback?

**Between:** PRD section 3 (interviewers use the comparison view, which shows resume scores, REQ-038) and REQ-062 with Q-008 (model scores hidden until the interviewer submits).

**Decision.** For each candidate on which the interviewer has not submitted feedback, the comparison view hides the resume score and override cells for that interviewer. The recruiter view is unchanged.

**Why.** It keeps the anti-anchoring rule in REQ-062 while leaving the view usable for interviewers.

**Settled by:** midhun (project owner)

**What now has to change to match:**
- US-00-015: add an acceptance criterion for the interviewer view and cover REQ-062.
- The comparison endpoint's low-level design: the hiding is done by the query, not by the client.
