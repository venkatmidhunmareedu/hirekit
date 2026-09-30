# Data model: HireKit

**Store:** PostgreSQL · **Tables:** 18 · **Columns:** 133 · **Indexes:** 25 · **Personal-data columns:** 13

One PostgreSQL database holds everything HireKit stores: users and sessions, roles with their criteria and rubric, candidates with their files and texts, scores with overrides, the audit history, the interview kit and feedback, the job queue, the model call log and the single budget row. The Api and the Worker (one backend package) read and write it; the Web never touches it. One store is enough because every acceptance criterion is relational or transactional (an upload commits its file, candidate and job together; a score exists only if its quote was verified), and the largest table stays near 10^6 rows.

- Task: HK-1
- Serves: US-00-001 to US-00-016, US-02-001, US-02-002, US-02-003, US-02-007, REQ-001 to REQ-062 (docs/product/coverage.md)
- ADRs: ADR-0001 (store), ADR-0004 (queue in a table), ADR-0005 (users and sessions), ADR-0008 (files in a table until extracted)
- Stores: postgres (ADR: ADR-0001)
- Companion files: `docs/design/schema.sql`, `docs/design/data-dictionary.csv`, `docs/design/erd.md`
- Author: midhun.m, 2026-09-30, status Draft, version v1

## 1. Why these stores

### PostgreSQL

**Holds:** all 18 tables below, including the job queue (ADR-0004) and uploaded files until extracted (ADR-0008).

The stories need foreign keys, check constraints, one transaction across upload, file and job (AC-US-00-003-1), row locks for the queue and the reserve-under-the-cap update for the budget (tenet 8). Volumes are small: the largest table, `scores`, reaches 10^5 to 10^6 rows a year. Postgres was chosen in ADR-0001; no second store is proposed.

| Considered | Why not |
| --- | --- |
| MongoDB | Scores, overrides and feedback are cross-referenced by candidate, criterion and user; the audit and duplicate rules are constraints, not documents read whole (ADR-0001). |
| ClickHouse | Nothing here is append-only analytics at scale: the largest question is cost by day over about 10^5 rows, answered by an index on `call_log`; HLD section 11 rejects an analytics store. |
| Redis or a broker for the queue | Enqueue must commit with the upload row and stale-marking must run in the role transaction (ADR-0004); a broker needs an outbox for both. |
| Object storage for resume files | About 20 MB per batch, deleted after extraction; the bytes must be written in the upload transaction (ADR-0008). |
| Recordings and the spend ledger as tables | Committed JSON files keyed by request hash, so CI needs no database (decisions.md conflict 3, REQ-045). |

## 2. Entities: ownership and lifecycle

Owners: Api and Worker are one backend package sharing this database (HLD section 4); Gateway is the module that writes `call_log` and `budget`.

| Entity | Owner | Created by | Changed by | Ended by | Stories | PII | Retention |
| --- | --- | --- | --- | --- | --- | --- | --- |
| users | Api | seed command | none in v1 | none | US-00-012, US-00-016 | yes | UNDEFINED |
| sessions | Api | login | none | logout, cascade from user | US-00-012 | no | UNDEFINED |
| roles | Api | Api create, seed | Api (approve, criteria edits) | none | US-00-001, US-00-002, US-02-007 | no | kept (no purge job in v1) |
| criteria | Api, Worker | Worker (proposal), Api, seed | Api | Api delete, cascade from role | US-00-001, US-00-002 | no | kept |
| rubric_levels | Api, Worker | with criteria | Api | cascade from criterion | US-00-001, US-00-002 | no | kept |
| candidates | Api, Worker | Api upload, seed | Worker (processing), Api (stage only) | none in v1 | US-00-003, US-00-009, US-00-011 | yes | UNDEFINED |
| resume_files | Api, Worker | Api upload | none | Worker delete after extraction | US-00-003 | yes | deleted on success; failed files UNDEFINED |
| resume_raw_texts | Worker | Worker | none | cascade from candidate | US-00-005 | yes | UNDEFINED |
| resume_texts | Worker | Worker | none | cascade from candidate | US-00-004, US-00-005 | yes | UNDEFINED |
| scores | Worker, Api | Worker | Api (override) | cascade from candidate or criterion | US-00-006 to US-00-010 | yes | UNDEFINED |
| assignments | Api | Api | none | Api delete, cascade from candidate | US-00-016 | no | kept |
| audit_events | Api | Api (each audited action) | never (trigger) | explicit purge only | US-00-009 to US-00-011, US-00-014 | yes | UNDEFINED |
| interview_kits | Worker | Worker (generate) | Worker (regenerate) | cascade from role | US-00-002, US-00-013 | no | kept |
| questions | Worker, Api | Worker | Api (edit), Worker (regenerate) | Api delete, cascade | US-00-013 | no | kept |
| feedback | Api | Api (submit) | Api (approved edit) | cascade from candidate | US-00-014, US-00-015 | yes | UNDEFINED |
| jobs | Api, Worker | Api enqueue | Worker, Api (cancel, retry) | none in v1 | US-00-001, US-00-003, US-00-006, US-00-013 | no | kept (no purge job in v1) |
| call_log | Gateway | Gateway | Gateway (settle) | none | US-02-001 to US-02-003 | no | kept |
| budget | Gateway | start-up from the spend ledger | Gateway | none | US-02-002 | no | kept |

Not modelled: `stage_history`, because REQ-055's history is the `stage_change` events of `audit_events` (one append-only table, not two); `retention_settings`, because Q-012 puts the per-role setting out of the first build; eval labels, name-swap pair links, recordings and the spend ledger, because they are committed files (decisions.md conflict 3) and no story reads them from the database; `notifications`, because no story asks for one.

Every writer, every column: the seed command (US-02-007) is the third writer of roles, criteria, users and candidates. It is assumed to go through the same functions as the Api upload and the criteria edit, so every NOT NULL column (content hash, file name, criteria_version) has a source. Direct SQL inserts by the seed command would leave `content_hash` with no source; open concern 6 asks for confirmation.

## 3. Relationships

One row per foreign key. The diagram with one sentence per relationship is `docs/design/erd.md`.

| From | To | Cardinality | FK column | On delete | Why |
| --- | --- | --- | --- | --- | --- |
| users | sessions | one-to-many | sessions.user_id | CASCADE | A user can have several sessions; signing a user out or removing them ends every session, so no cookie outlives its user. |
| roles | criteria | one-to-many | criteria.role_id | CASCADE | A role has about eight criteria; criteria have no meaning without their role. |
| criteria | rubric_levels | one-to-many | rubric_levels.criterion_id | CASCADE | A criterion has one descriptor for each level 0 to 4; they are part of the criterion. |
| roles | candidates | one-to-many | candidates.role_id | RESTRICT | A role collects many candidates; a role with candidates cannot be deleted, because no story deletes candidate records. |
| candidates | candidates | one-to-many | candidates.duplicate_of_id | SET NULL | A duplicate upload points at the earlier one; removing the original clears the flag instead of removing the duplicate (REQ-029: nothing is hidden). |
| candidates | resume_files | one-to-one | resume_files.candidate_id | CASCADE | A candidate has at most one stored file, present only until extraction succeeds. |
| candidates | resume_raw_texts | one-to-one | resume_raw_texts.candidate_id | CASCADE | A candidate has one raw text, recruiter only, droppable without touching the anonymized text. |
| candidates | resume_texts | one-to-one | resume_texts.candidate_id | CASCADE | A candidate has one anonymized text, the only text the model sees. |
| candidates | scores | one-to-many | scores.candidate_id | CASCADE | A candidate has one score per criterion per criteria version; scores follow the candidate. |
| criteria | scores | one-to-many | scores.criterion_id | CASCADE | A deleted criterion takes its scores; the recruiter's override history survives in audit_events. |
| users | scores | one-to-many | scores.overridden_by | RESTRICT | The recruiter who overrode a score is recorded and cannot be deleted while the override stands. |
| candidates | assignments | one-to-many | assignments.candidate_id | CASCADE | A candidate can have several interviewers; assignments follow the candidate. |
| users | assignments | one-to-many | assignments.user_id | RESTRICT | An interviewer can be assigned many candidates; a user with assignments cannot be deleted. |
| candidates | audit_events | one-to-many | audit_events.candidate_id | RESTRICT | Every override, stage move and reveal belongs to a candidate; a candidate with history cannot be deleted without an explicit purge of that history first. |
| users | audit_events | one-to-many | audit_events.actor_id | RESTRICT | Every event names who acted; that user cannot be deleted while their history stands. |
| users | audit_events | one-to-many | audit_events.subject_user_id | RESTRICT | Feedback events name the interviewer concerned. |
| roles | interview_kits | one-to-one | interview_kits.role_id | CASCADE | A role has at most one kit, which goes with the role. |
| interview_kits | questions | one-to-many | questions.role_id | CASCADE | A kit holds many questions; regenerating a kit replaces them. |
| criteria | questions | one-to-many | (questions.role_id, questions.criterion_id) | CASCADE | A question probes one criterion of the same role; a composite key stops a question pointing at another role's criterion. |
| candidates | feedback | one-to-many | feedback.candidate_id | CASCADE | Feedback belongs to a candidate and follows it. |
| users | feedback | one-to-many | feedback.interviewer_id | RESTRICT | An interviewer scores many candidates; submitted feedback is not lost with a user. |
| criteria | feedback | one-to-many | feedback.criterion_id | RESTRICT | Locked feedback is never removed with a criterion; deleting a criterion sets retired_at instead. |
| roles | jobs | one-to-many | jobs.role_id | RESTRICT | Every job works for a role; the queue view is per role. |
| candidates | jobs | one-to-many | jobs.candidate_id | CASCADE | A scoring job with no candidate has nothing to do. |
| questions | jobs | one-to-many | jobs.question_id | CASCADE | A regenerate job for a deleted question has nothing to do. |
| roles | call_log | one-to-many | call_log.role_id | RESTRICT | Spend is attributed to a role and the record outlives no deletion of it. |

## 4. PostgreSQL tables

In the order schema.sql creates them. The DDL lives only in `docs/design/schema.sql`; this section gives the reason for each piece. Ids are `uuid` from `gen_random_uuid()` on tables that stay under about 10^5 rows (random keys are acceptable there), and `bigint identity` on the queue, the audit history and the call log. Timestamps are `timestamptz`.

### `users`: Users (hot: no)

A seeded recruiter or interviewer who can sign in.

Serves US-00-012, US-00-016, US-00-014. Expected volume: tens of rows (10^1), one per seeded account.

Writers: the seed command only (Q-002); no story creates or edits users, so there is no Api path.

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | `uuid` | No | PK | `gen_random_uuid()` | Surrogate key. | AC-US-00-010-5: audit rows record which user acted, by id. |
| `name` | `text` | No |  |  | Display name shown beside overrides, stage moves and feedback. **(personal data: name)** | AC-US-00-011-3: a rejection is logged under the recruiter's name. |
| `email` | `text` | No |  |  | Sign-in identifier, unique ignoring case. **(personal data: contact)** | ADR-0005 and Q-002: seeded logins need a login identifier. |
| `role` | `user_role` | No |  |  | recruiter or interviewer; the value every route dependency checks. | AC-US-00-012-2: the service refuses by role, not only the UI. |
| `password_hash` | `text` | No |  |  | Password hash; the password itself is never stored. **(personal data: credential)** | ADR-0005: hashed passwords; seed passwords are generated at seed time. |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |

**Indexes**

- `uq_users_email`: unique on (lower(email)). Sign-in lookup, and refuses two accounts that differ only by case (AC-US-00-012-5).

**Constraints**

- `chk_users_name_not_blank`: `btrim(name) <> ''`. Refuses a user with a blank name prints an unlabelled audit row.
- `chk_users_email_shape`: `email ~ '^[^@[:space:]]+@[^@[:space:]]+$'`. Refuses a login value that cannot be an email address.

### `sessions`: Sessions (hot: no)

A server-side session behind the secure cookie.

Serves US-00-012. Expected volume: hundreds of rows (10^2 to 10^3) a year: a few sign-ins a day, never purged in the first build.

Writers: the Api login and logout routes.

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `token_hash` | `bytea` | No | PK |  | SHA-256 of the session cookie value; the cookie itself is never stored. | ADR-0005: server-side sessions; a copied database must not yield working cookies. |
| `user_id` | `uuid` | No | FK users.id |  | The signed-in user. | AC-US-00-012-5: a request with no signed-in user is refused; removing a user ends the session. |
| `csrf_token` | `text` | No |  |  | Token the client echoes in a header on state-changing requests. | HLD section 9: every state-changing request carries a CSRF token the Api checks. |
| `expires_at` | `timestamptz` | No |  |  | When the session stops being valid; checked on every request. | ADR-0005: we own session expiry. The lifetime is UNDEFINED (section 6). |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |

**Indexes**

- `idx_sessions_user_id`: on (user_id). Foreign-key index: sign a user out everywhere, and no table scan when a user is checked on delete.

**Constraints**

- `chk_sessions_token_hash_length`: `octet_length(token_hash) = 32`. Refuses a stored value that is not a SHA-256 digest, meaning a raw cookie was stored.

### `roles`: Roles (hiring roles) (hot: no)

A job being hired for: the title, the job description and the approval state that gates everything downstream.

Serves US-00-001, US-00-002, US-00-013, US-02-007. Expected volume: tens of rows (10^1): two seeded, a few created by hand.

Writers: the Api (create, approve, criteria edits that set status back to draft and bump criteria_version in the same transaction) and the seed command. The Worker reads it under FOR SHARE and never writes it.

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | `uuid` | No | PK | `gen_random_uuid()` | Surrogate key. | AC-US-00-001-1: a saved role has an id every candidate and criterion points to. |
| `title` | `text` | No |  |  | The role title. | AC-US-00-001-1: a role is created with a title. |
| `job_description` | `text` | No |  |  | The job description the criteria proposal and kit prompts are built from. | AC-US-00-001-1 and AC-US-00-013-4: the kit prompt contains the job description and criteria. |
| `status` | `role_status` | No |  | `'draft'` | Draft or Approved. | AC-US-00-002-3: upload, scoring and kit are blocked while Draft; AC-US-00-001-1: a new role is Draft. |
| `criteria_version` | `integer` | No |  | `1` | Counter bumped by every criteria or rubric write, including a model proposal. | REQ-006 and HLD section 7: the Worker writes scores only while this equals the job's version, which closes the edit and re-approve case. |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |
| `updated_at` | `timestamptz` | No |  | `now()` | Last change to the row, set by the repository on every UPDATE. | Rule: audit columns (postgres.md). |

**Constraints**

- `chk_roles_title_not_blank`: `btrim(title) <> ''`. Refuses a role with no visible title in the role list.
- `chk_roles_criteria_version_positive`: `criteria_version >= 1`. Refuses a version of zero or below, which the job payload could never match.

### `criteria`: Criteria (hot: no)

One scoring criterion of a role: name, kind, weight and order.

Serves US-00-001, US-00-002, US-00-008. Expected volume: hundreds of rows (10^2): about 8 per role.

Writers: the Worker (a propose_criteria job writes the proposal into a Draft role), the Api (edits, reorder, delete = set retired_at) and the seed command. Edits are in-place updates by id and a delete never removes a row, so RESTRICT from feedback never blocks it (decided 2026-09-30). Every read of a role's criteria repeats retired_at IS NULL; a purge of retired rows is a batched hard delete once retention is decided. Every writer bumps roles.criteria_version in the same transaction.

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | `uuid` | No | PK | `gen_random_uuid()` | Surrogate key. | AC-US-00-006-1: scores and questions are keyed by criterion. |
| `role_id` | `uuid` | No | FK roles.id |  | The role this criterion belongs to. | AC-US-00-001-3: a criterion is part of a role's proposal. CASCADE because a criterion has no life apart from its role. |
| `name` | `text` | No |  |  | What is being judged, for example Python experience. | AC-US-00-001-3: each criterion has a name. |
| `kind` | `criterion_kind` | No |  |  | must_have or nice_to_have. | AC-US-00-008-2: must-have coverage is computed from the kind; AC-US-00-015-1 groups by it. |
| `weight` | `numeric(6,3)` | No |  |  | Weight in the total; default set by kind, editable. | AC-US-00-008-1: the total is the weighted sum; Q-001: editable per criterion. |
| `position` | `integer` | No |  |  | Display order inside the role. | AC-US-00-002-1: the recruiter can reorder criteria. |
| `retired_at` | `timestamptz` | Yes |  |  | When the recruiter deleted the criterion; null while it is live. Retired rows stay so scores and feedback keep their target. | AC-US-00-002-1 (delete a criterion) with REQ-037 (locked feedback is kept): deleting retires, never removes a row that feedback or scores point at. |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |
| `updated_at` | `timestamptz` | No |  | `now()` | Last change to the row, set by the repository on every UPDATE. | Rule: audit columns (postgres.md). |

**Indexes**

- `uq_criteria_role_id_id`: `UNIQUE (role_id, id)`. A unique constraint, not an index statement in schema.sql; it is the target of the composite foreign key from questions, so a question cannot point at another role's criterion.
- `idx_criteria_role_position`: on (role_id, position) where `retired_at IS NULL`. A role's live criteria in display order (AC-US-00-002-1); the query must repeat retired_at IS NULL. The leading role_id is also the foreign-key index.

**Constraints**

- `chk_criteria_name_not_blank`: `btrim(name) <> ''`. Refuses a criterion that renders as an empty row.
- `chk_criteria_weight_positive`: `weight > 0`. Refuses a zero or negative weight that lets a criterion cancel or vanish from the total.

### `rubric_levels`: Rubric levels (hot: no)

The descriptor for each score level 0 to 4 of one criterion.

Serves US-00-001, US-00-002, US-00-006. Expected volume: hundreds to a thousand rows (10^2 to 10^3): five per criterion.

Writers: as criteria. That all five levels exist for a criterion is an application rule (AC-US-00-001-3); no constraint can count rows in another table.

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `criterion_id` | `uuid` | No | PK, FK criteria.id |  | The criterion described. | AC-US-00-001-3: rubric descriptors belong to a criterion; they go with it. |
| `level` | `smallint` | No |  |  | Score value from 0 to 4; 0 means no evidence. | Q-009 and AC-US-00-006-2: the scale is 0 to 4, shown beside every score. |
| `descriptor` | `text` | No |  |  | What a resume at this level looks like. | AC-US-00-001-3: rubric descriptors for each score level. |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |
| `updated_at` | `timestamptz` | No |  | `now()` | Last change to the row, set by the repository on every UPDATE. | Rule: audit columns (postgres.md). |

**Constraints**

- `chk_rubric_levels_level_range`: `level BETWEEN 0 AND 4`. Refuses a level outside the 0 to 4 scale that no score can equal.
- `chk_rubric_levels_descriptor_not_blank`: `btrim(descriptor) <> ''`. Refuses a level shown to the recruiter with no descriptor.

### `candidates`: Candidates (hot: no)

One uploaded resume for one role: its stage, its processing state and the fields the list needs.

Serves US-00-003, US-00-005, US-00-009, US-00-011. Expected volume: tens of thousands of rows a year (10^4 to 10^5): at most 100 a day at peak (assumption in HLD section 4), 40 seeded.

Writers: the Api upload (id, role_id, file_name, content_hash, duplicate_of_id; stage and processing_status by default), the Api stage endpoint (stage only, with an audit_events row in the same transaction), the Worker (processing_status, failure_reason, identity_name) and the seed command through the same upload function. No worker or ranking code writes stage (tenet 4).

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | `uuid` | No | PK | `gen_random_uuid()` | Surrogate key. | AC-US-00-009-1: the list and every action address a candidate by id. |
| `candidate_no` | `bigint` | No |  | identity | Number shown as C-014 in every list instead of a name. | AC-US-00-009-2: candidates appear as IDs, not names. Global, not per role. |
| `role_id` | `uuid` | No | FK roles.id |  | The role the resume was uploaded to. | AC-US-00-003-1: each file becomes a row under an Approved role. RESTRICT: no story deletes a role that has candidates. |
| `stage` | `candidate_stage` | No |  | `'new'` | Hiring stage; written only by the stage endpoint. | AC-US-00-011-1 and AC-US-00-011-4: a recruiter moves it, the system never does; AC-US-00-009-3 filters by it. |
| `processing_status` | `processing_state` | No |  | `'queued'` | Per-file pipeline status. | AC-US-00-003-5: each file shows queued, parsing, anonymizing, scoring, done or failed. |
| `failure_reason` | `text` | Yes |  |  | Plain reason a file failed; null otherwise. | AC-US-00-003-3: a failed file stays in the list with a plain reason. |
| `file_name` | `text` | No |  |  | Original upload name. **(personal data: name inside a file name)** | AC-US-00-003-1: each file is shown as a row. File names often carry the name, so it is personal data. |
| `content_hash` | `text` | No |  |  | SHA-256 hex of the uploaded bytes, kept after the bytes are deleted. | AC-US-00-003-4: a matching hash for the role flags a duplicate. |
| `duplicate_of_id` | `uuid` | Yes | FK candidates.id |  | The earlier candidate with the same hash; null when not a duplicate. | AC-US-00-003-4: flagged, never rejected (REQ-029). SET NULL so removing the original does not remove the flagged row. |
| `identity_name` | `text` | Yes |  |  | Name the anonymizer found, for Reveal identity; recruiters only. **(personal data: name)** | AC-US-00-009-2 and Q-007: names are hidden until a logged reveal. Null until extraction, or when none was found. |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |
| `updated_at` | `timestamptz` | No |  | `now()` | Last change to the row, set by the repository on every UPDATE. | Rule: audit columns (postgres.md). |

**Indexes**

- `uq_candidates_candidate_no`: `UNIQUE (candidate_no)`. A unique constraint, not an index statement in schema.sql; it is the two candidates sharing the C-nnn shown in the list.
- `idx_candidates_role_stage`: on (role_id, stage). The ranked list for one role filtered by stage (AC-US-00-009-3) and the per-role queue view (AC-US-00-003-6); role_id leads, so it is also the foreign-key index.
- `idx_candidates_role_content_hash`: on (role_id, content_hash). The duplicate check at upload: earlier candidates of this role with the same hash (AC-US-00-003-4).
- `idx_candidates_duplicate_of_id`: on (duplicate_of_id) where `duplicate_of_id IS NOT NULL`. Foreign-key index for the self reference; the predicate is implied by any equality on the column.

**Constraints**

- `chk_candidates_content_hash_shape`: `content_hash ~ '^[0-9a-f]{64}$'`. Refuses a hash that is not SHA-256 hex, which would never match a later upload.
- `chk_candidates_failure_reason`: `(processing_status = 'failed') = (failure_reason IS NOT NULL)`. Refuses a failed file with no reason (a silent drop) or a reason on a file that is not failed.
- `chk_candidates_duplicate_not_self`: `duplicate_of_id IS NULL OR duplicate_of_id <> id`. Refuses a candidate flagged as a duplicate of itself.

### `resume_files`: Resume files (hot: no)

The uploaded bytes, held only until extraction succeeds (ADR-0008).

Serves US-00-003. Expected volume: about 100 rows at most at a time (10^2): a batch of up to 100 files of about 200 KB (assumption), deleted as each succeeds.

Writers: the Api upload inserts the row; the Worker deletes it in the transaction that stores the text (the lease-token write). Deleted on success, kept on failure.

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `candidate_id` | `uuid` | No | PK, FK candidates.id |  | The candidate this file was uploaded as. | ADR-0008: the file is written in the same transaction as its candidate and job; one file per candidate. |
| `media_type` | `text` | No |  |  | PDF or DOCX media type. | AC-US-00-003-2: only PDF and DOCX are accepted. |
| `content` | `bytea` | No |  |  | The original file bytes. **(personal data: original resume file)** | AC-US-00-003-3: a failed extraction needs the original for the retry action. |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |

**Constraints**

- `chk_resume_files_media_type`: `media_type IN ('application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')`. Refuses a file type the extractor cannot read.
- `chk_resume_files_content_not_empty`: `octet_length(content) > 0`. Refuses an empty upload that would fail extraction with no useful reason.

### `resume_raw_texts`: Resume raw texts (hot: no)

The extracted text as it came out of the file, before anonymization; recruiters only.

Serves US-00-004, US-00-005, US-00-009. Expected volume: tens of thousands of rows (10^4 to 10^5) a year, one per candidate.

Writers: the Worker only, in the same transaction that deletes the resume_files row. Read only by recruiter-guarded routes and by the anonymizer.

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `candidate_id` | `uuid` | No | PK, FK candidates.id |  | The candidate whose file this text came from. | AC-US-00-005-1: raw text is stored apart from anonymized text; one row per candidate. |
| `raw_text` | `text` | No |  |  | Extracted text with names, contacts and location intact. **(personal data: full resume text)** | AC-US-00-005-5: recruiters can read it, other accounts are denied. Its own table so no interviewer or list query can pull it by accident and so a purge can drop it alone (PRD section 9). |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |

**Constraints**

- `chk_resume_raw_texts_not_blank`: `btrim(raw_text) <> ''`. Refuses a scanned image that extracted to nothing and must be a failed file (AC-US-00-003-3), not an empty text.

### `resume_texts`: Resume anonymized texts (hot: no)

The anonymizer's output: the only resume text the model sees and the text quotes are checked against.

Serves US-00-004, US-00-005, US-00-006, US-00-007. Expected volume: tens of thousands of rows (10^4 to 10^5) a year, one per candidate.

Writers: the Worker only. The Api reads it for recruiters; interviewer routes never join this table (Q-003).

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `candidate_id` | `uuid` | No | PK, FK candidates.id |  | The candidate this text belongs to. | AC-US-00-005-1: stored in its own row, apart from the raw text. |
| `anonymized_text` | `text` | No |  |  | Text after identity signals were removed. **(personal data: derived from a resume; proxy signals can remain)** | AC-US-00-005-2 and AC-US-00-007-1: scoring reads only this, and every quote must appear in it. Marked personal data because proxy signals can remain (PRD section 13). |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |

**Constraints**

- `chk_resume_texts_not_blank`: `btrim(anonymized_text) <> ''`. Refuses an anonymizer result that is empty, which would make every quote unverifiable.

### `scores`: Scores (hot: no)

One criterion's score for one candidate at one criteria version, with its verified quote and any recruiter override.

Serves US-00-006, US-00-007, US-00-008, US-00-010. Expected volume: hundreds of thousands of rows a year (10^5 to 10^6): about 800 a day at the peak (8 criteria, HLD section 4), times re-runs.

Writers: the Worker (a whole row per criterion, upserted by candidate, criterion and version, only while its lease token matches and the role's criteria_version equals the job's) and the Api override endpoint (override_score, override_note, overridden_by, updated_at). The weighted total and the ranking are computed in the query, never stored, so an override recalculates it (AC-US-00-010-4). The upsert never sets override_* columns, and a rescore at the same version rewrites only rows whose status is failed, so an override is never overwritten. An override does not carry to a new criteria_version (open concern 3). The guarantee that a quote exists in the anonymized text is enforced by code (tenet 3), not by the database: the CHECK only requires a quote on a scored row (open concern 9). The primary key has no separate id because nothing references a score.

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `candidate_id` | `uuid` | No | PK, FK candidates.id |  | The candidate scored. | AC-US-00-006-1: a score belongs to a candidate; removing the candidate removes its scores. |
| `criterion_id` | `uuid` | No | PK, FK criteria.id |  | The criterion scored. | AC-US-00-006-1: one score per approved criterion. |
| `criteria_version` | `integer` | No |  |  | The roles.criteria_version the score was computed against; the scoring run. | AC-US-00-002-5: a score is stale when this is below the role's version, so no writer has a stale flag to forget. |
| `status` | `score_status` | No |  |  | scored, no_evidence or failed. | AC-US-00-006-4 and AC-US-00-007-3: failed and no-evidence criteria are listed, never guessed. |
| `model_score` | `smallint` | Yes |  |  | The model's score after capping; null when failed. | AC-US-00-007-4 and AC-US-00-007-5: capped when the quote fails or there is no evidence. |
| `quote` | `text` | Yes |  |  | The evidence quote, stored only after code found it in the anonymized text. **(personal data: excerpt of a resume)** | Tenet 3 and AC-US-00-007-1: a score row exists only after verify_quote passed. Null means no evidence found. |
| `flag_reason` | `text` | Yes |  |  | One line saying why the item is flagged, for example the quote was not found. | AC-US-00-007-4: the item is flagged with a line that says why. |
| `override_score` | `smallint` | Yes |  |  | Recruiter's replacement value; null when not overridden. | AC-US-00-010-3: both the model value and the override are kept and shown. |
| `override_note` | `text` | Yes |  |  | Why the recruiter overrode. **(personal data: free text about a candidate)** | AC-US-00-010-1: a note of at least 10 characters is required. |
| `overridden_by` | `uuid` | Yes | FK users.id |  | The recruiter who overrode. | AC-US-00-008-4: an override shows as Recruiter override; AC-US-00-010-5: recorded under a user. |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |
| `updated_at` | `timestamptz` | No |  | `now()` | Last change to the row, set by the repository on every UPDATE. | Rule: audit columns (postgres.md). |

**Indexes**

- `idx_scores_criterion_id`: on (criterion_id, criteria_version). Sort the ranked list by one criterion for the current version (AC-US-00-009-3); the leading criterion_id is also the foreign-key index.
- `idx_scores_overridden_by`: on (overridden_by) where `overridden_by IS NOT NULL`. Foreign-key index for the users reference; the predicate is implied by any equality on the column.

**Constraints**

- `chk_scores_criteria_version_positive`: `criteria_version >= 1`. Refuses a version no role can have.
- `chk_scores_model_score_range`: `model_score BETWEEN 0 AND 4`. Refuses a value off the 0 to 4 scale (Q-009).
- `chk_scores_status_shape`: `(status = 'scored' AND model_score IS NOT NULL AND quote IS NOT NULL) OR (status = 'no_evidence' AND model_score = 0 AND quote IS NULL) OR (status = 'failed' AND model_score IS NULL AND quote IS NULL)`. Refuses a scored row with no quote, a no-evidence row above 0 (REQ-022, Q-011) or with a quote, or a failed row with a guessed value.
- `chk_scores_override_range`: `override_score BETWEEN 0 AND 4`. Refuses an override off the scale.
- `chk_scores_override_all_or_none`: `(override_score IS NULL) = (override_note IS NULL) AND (override_score IS NULL) = (overridden_by IS NULL)`. Refuses an override with no note or no author, or a note with no override.
- `chk_scores_override_note_length`: `override_note IS NULL OR length(btrim(override_note)) >= 10`. Refuses a note under 10 characters (AC-US-00-010-2).

### `assignments`: Assignments (hot: no)

Which interviewer may see which candidate.

Serves US-00-016, US-00-012, US-00-014. Expected volume: tens of thousands of rows (10^4): a few interviewers per interviewed candidate.

Writers: the Api assignment routes, recruiter only (AC-US-00-016-3). That user_id names an interviewer is checked by the route, not by the database.

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `candidate_id` | `uuid` | No | PK, FK candidates.id |  | The candidate assigned. | AC-US-00-016-1: the assignment makes the candidate visible; removing the candidate removes it. |
| `user_id` | `uuid` | No | PK, FK users.id |  | The interviewer assigned. | AC-US-00-016-1: the interviewer sees that candidate. RESTRICT: an assigned user cannot vanish under an open assignment. |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |

**Indexes**

- `idx_assignments_user_id`: on (user_id). An interviewer's candidate list, the predicate every interviewer query carries (AC-US-00-012-3, tenet 6); also the foreign-key index.

### `audit_events`: Audit events (hot: no)

Append-only history of who did what to a candidate: overrides, stage moves, identity reveals and approved feedback edits.

Serves US-00-009, US-00-010, US-00-011, US-00-014. Expected volume: tens of thousands to a hundred thousand rows a year (10^4 to 10^5): under 300 a day (HLD section 4).

Writers: the Api only: the override endpoint, the stage endpoint, the reveal endpoint and the feedback approval and edit endpoints, each writing its event in the same transaction as the change. The stage history the PRD asks for (REQ-055) is the stage_change events of this table; there is no second table.

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | `bigint` | No | PK | identity | Sequence number; the order of events. | REQ-030: an audit history is ordered. |
| `candidate_id` | `uuid` | No | FK candidates.id |  | The candidate acted on. | AC-US-00-011-2: the history is per candidate. RESTRICT: a candidate with history cannot be deleted by accident. |
| `actor_id` | `uuid` | No | FK users.id |  | The user who acted. | AC-US-00-010-5 and AC-US-00-011-2: user and time are recorded. |
| `kind` | `text` | No |  |  | score_override, stage_change, identity_reveal, feedback_edit_approved or feedback_edited. | REQ-030 and AC-US-00-009-2: each audited action is one kind. |
| `criterion_name` | `text` | Yes |  |  | Name of the criterion at the time; null for stage and reveal events. | AC-US-00-010-5: the override record must stay readable after the criterion is renamed or deleted, so the name is copied, not referenced. |
| `old_score` | `smallint` | Yes |  |  | Value before the change. | AC-US-00-010-5: old value and new value are recorded. |
| `new_score` | `smallint` | Yes |  |  | Value after the change. | AC-US-00-010-5: old value and new value are recorded. |
| `from_stage` | `candidate_stage` | Yes |  |  | Stage before a stage_change. | AC-US-00-011-2: the stage history records from. |
| `to_stage` | `candidate_stage` | Yes |  |  | Stage after a stage_change. | AC-US-00-011-2 and AC-US-00-011-3: records to; Rejected is logged under the recruiter. |
| `subject_user_id` | `uuid` | Yes | FK users.id |  | The interviewer whose feedback an event concerns. | AC-US-00-014-5: an approved edit and the edit itself are recorded against that interviewer. |
| `old_comment` | `text` | Yes |  |  | The comment before a feedback_edited change; null for other kinds. **(personal data: free text about a candidate)** | AC-US-00-014-5: an approved edit is saved and recorded, so the previous comment must survive the overwrite. |
| `note` | `text` | Yes |  |  | Override note or optional stage reason. **(personal data: free text about a candidate)** | AC-US-00-010-5 (note) and AC-US-00-011-3 (optional reason). |
| `created_at` | `timestamptz` | No |  | `now()` | When it happened. | AC-US-00-010-5 and AC-US-00-011-2: time is recorded. |

**Indexes**

- `idx_audit_events_candidate_created`: on (candidate_id, created_at DESC, id DESC). A candidate's history, newest first (AC-US-00-011-2); also the foreign-key index.
- `idx_audit_events_actor_id`: on (actor_id). Foreign-key index for the users reference.
- `idx_audit_events_subject_user_id`: on (subject_user_id) where `subject_user_id IS NOT NULL`. Foreign-key index for the users reference; the predicate is implied by any equality on the column.

**Constraints**

- `chk_audit_events_kind`: `kind IN ('score_override', 'stage_change', 'identity_reveal', 'feedback_edit_approved', 'feedback_edited')`. Refuses an audited action nothing knows how to render.
- `chk_audit_events_override_shape`: `kind <> 'score_override' OR (criterion_name IS NOT NULL AND new_score IS NOT NULL AND note IS NOT NULL AND length(btrim(note)) >= 10)`. Refuses an override record with no criterion, value or note (AC-US-00-010-5).
- `chk_audit_events_stage_shape`: `kind <> 'stage_change' OR (from_stage IS NOT NULL AND to_stage IS NOT NULL AND from_stage <> to_stage)`. Refuses a stage record with a missing side or a move to the same stage.
- `chk_audit_events_feedback_shape`: `kind NOT IN ('feedback_edit_approved', 'feedback_edited') OR subject_user_id IS NOT NULL`. Refuses a feedback event that does not say whose feedback it concerns.
- `trg_audit_events_append_only`: a BEFORE UPDATE trigger that raises. Refuses any edit of an audit row (REQ-030; ADR-0001: constraints enforce the audit trail).

### `interview_kits`: Interview kits (hot: no)

The per-role kit header: whether one exists and whether it is stale.

Serves US-00-002, US-00-013. Expected volume: tens of rows (10^1): at most one per role.

Writer: the Worker (generate_kit), only while the job's criteria_version equals the role's, so a kit generated for old criteria is discarded, never stored as fresh. Staleness is derived: kit.criteria_version < roles.criteria_version.

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `role_id` | `uuid` | No | PK, FK roles.id |  | The role the kit is for. | REQ-035 and AC-US-00-013-1: the kit is per role. CASCADE because a kit has no life apart from its role. |
| `criteria_version` | `integer` | No |  |  | The roles.criteria_version the kit was generated against. | AC-US-00-002-6 and Q-005: the kit is stale when this is below the role's version, so no writer has a flag to forget (same pattern as scores). |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |
| `updated_at` | `timestamptz` | No |  | `now()` | Last change to the row, set by the repository on every UPDATE. | Rule: audit columns (postgres.md). |

**Constraints**

- `chk_interview_kits_version_positive`: `criteria_version >= 1`. Refuses a version no role can have.

### `questions`: Kit questions (hot: no)

One interview question for one criterion, with what a strong and a weak answer look like.

Serves US-00-013, US-00-014. Expected volume: hundreds of rows (10^2): about 3 per criterion, about 8 criteria, per role.

Writers: the Worker (generate_kit and regenerate_question jobs, one call per criterion) and the Api (edit, reorder, delete). Edits are made in place, so interviewers see the edited version (AC-US-00-013-6).

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | `uuid` | No | PK | `gen_random_uuid()` | Surrogate key. | AC-US-00-013-5: a single question is edited, reordered, deleted or regenerated by id. |
| `role_id` | `uuid` | No | FK interview_kits.role_id |  | The role whose kit holds the question. | AC-US-00-013-2: the kit is grouped by criterion within a role's kit. |
| `criterion_id` | `uuid` | No | FK criteria.id |  | The criterion the question probes. | AC-US-00-013-2: questions grouped by criterion. Part of a composite foreign key with role_id, so it must belong to the same role. |
| `question_text` | `text` | No |  |  | The question. | AC-US-00-013-2: the kit holds questions. |
| `strong_answer` | `text` | No |  |  | What a strong answer looks like. | AC-US-00-013-3: each question has a strong answer description. |
| `weak_answer` | `text` | No |  |  | What a weak answer looks like. | AC-US-00-013-3: each question has a weak answer description. |
| `position` | `integer` | No |  |  | Order inside the criterion. | AC-US-00-013-5: the recruiter can reorder questions. |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |
| `updated_at` | `timestamptz` | No |  | `now()` | Last change to the row, set by the repository on every UPDATE. | Rule: audit columns (postgres.md). |

**Indexes**

- `idx_questions_role_criterion_position`: on (role_id, criterion_id, position). The kit for a role grouped by criterion in order (AC-US-00-013-2); the leading pair is also the composite foreign-key index.

**Constraints**

- `fk_questions_role_criterion`: `FOREIGN KEY (role_id, criterion_id) REFERENCES criteria (role_id, id) ON DELETE CASCADE`. Keeps a question inside its own role's criteria.
- `chk_questions_fields_not_blank`: `btrim(question_text) <> '' AND btrim(strong_answer) <> '' AND btrim(weak_answer) <> ''`. Refuses a question the interviewer sees with an empty answer guide.

### `feedback`: Interviewer feedback (hot: no)

One interviewer's score and comment for one criterion of one candidate.

Serves US-00-014, US-00-015. Expected volume: tens of thousands of rows (10^4 to 10^5): interviewed candidates times criteria times interviewers.

Writers: the Api only. One submission inserts a whole set of rows for (candidate, interviewer) in one transaction, so submitted means any row exists for that pair; the Api enforces that every criterion is present (AC-US-00-014-3). The approve-edit route addresses (candidate, interviewer), not one id, and copies the old score and comment into the audit row (open concern 10).

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `candidate_id` | `uuid` | No | PK, FK candidates.id |  | The candidate interviewed. | AC-US-00-014-2: feedback is per candidate. |
| `interviewer_id` | `uuid` | No | PK, FK users.id |  | The interviewer who scored. | AC-US-00-014-2 and AC-US-00-015-4: disagreement is found across interviewers. RESTRICT: feedback must not vanish with a user. |
| `criterion_id` | `uuid` | No | PK, FK criteria.id |  | The criterion scored. | AC-US-00-014-1: one section per criterion. RESTRICT: locked feedback must not vanish; a criterion delete only retires it. |
| `score` | `smallint` | No |  |  | The interviewer's score on the rubric scale. | AC-US-00-014-1: a score selector matching the rubric scale (Q-009). |
| `comment` | `text` | No |  |  | The interviewer's short comment. **(personal data: free text about a candidate)** | AC-US-00-014-2: every criterion is scored and commented before submit. Free text about a candidate. |
| `locked` | `boolean` | No |  | `true` | True after submit; a recruiter-approved edit sets it false until the interviewer saves again. | AC-US-00-014-4 and AC-US-00-014-5: read-only after submit except for an approved edit. |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |
| `updated_at` | `timestamptz` | No |  | `now()` | Last change to the row, set by the repository on every UPDATE. | Rule: audit columns (postgres.md). |

**Indexes**

- `idx_feedback_interviewer_id`: on (interviewer_id, candidate_id). An interviewer's own feedback and the has-submitted check that unhides model scores (AC-US-00-014-6, AC-US-00-014-7); also the foreign-key index.
- `idx_feedback_criterion_id`: on (criterion_id). Foreign-key index, so deleting a criterion checks feedback without a table scan.

**Constraints**

- `chk_feedback_score_range`: `score BETWEEN 0 AND 4`. Refuses a score off the 0 to 4 scale.
- `chk_feedback_comment_not_blank`: `btrim(comment) <> ''`. Refuses a submitted criterion with no comment (AC-US-00-014-2).

### `jobs`: Jobs (the queue) (hot: yes: claims and lease writes every second while a batch runs, but under 10^5 rows, so lock risk is low)

The Postgres-backed queue (ADR-0004): one row per unit of background work, claimed by a Worker.

Serves US-00-001, US-00-003, US-00-006, US-00-013, US-02-001. Expected volume: tens of thousands of rows a year (10^4 to 10^5): about 4,500 a month (HLD section 4), never purged in the first build.

Writers: the Api (enqueue in the upload transaction, cancel, manual retry) and the Worker (claim, lease, attempt, run_after, status, last_error). Every job carries the role's criteria_version at enqueue, so no job type escapes the stale check. A manual retry inserts a NEW row with the current criteria_version and a fresh deadline; the old row stays failed as history, and uq_jobs_open_candidate still blocks a double click. Cancel sets status to cancelled and clears lease_token and lease_expires_at, so a running Worker's fenced write fails. Claim and reclaim: a claim increments attempt; a reclaim of an expired lease at attempt 3 sets status failed and the candidate's failure_reason instead of incrementing, so chk_jobs_attempt_range never aborts a batch reclaim. The result transaction locks the job row (SELECT ... WHERE lease_token = :mine FOR UPDATE) before writing. process_resume is idempotent: if resume_texts already exists it skips extraction, because the file is deleted in the same transaction that stores the text.

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | `bigint` | No | PK | identity | Job id returned to the Web for polling. | AC-US-00-001-2 and AC-US-00-003-6: the Web polls a job; ids are sequence numbers, never application-generated. |
| `type` | `text` | No |  |  | process_resume, propose_criteria, generate_kit, regenerate_question or rescore. | HLD section 3: the five Worker job types. |
| `status` | `text` | No |  | `'queued'` | queued, running, succeeded, failed (dead letter), stale or cancelled. | AC-US-00-001-4 (cancel), HLD section 7 (stale, dead letter). |
| `role_id` | `uuid` | No | FK roles.id |  | The role the job works for. | AC-US-00-003-6: the queue view lists a role's jobs. RESTRICT: a role with jobs is not deleted. |
| `candidate_id` | `uuid` | Yes | FK candidates.id |  | The candidate, for process_resume and rescore. | AC-US-00-003-5: per-file status. CASCADE: a job for a removed candidate has nothing left to do. |
| `question_id` | `uuid` | Yes | FK questions.id |  | The question, for regenerate_question. | AC-US-00-013-5: a single question is regenerated. CASCADE: nothing to regenerate once deleted. |
| `criteria_version` | `integer` | No |  |  | roles.criteria_version at enqueue time; ids and this integer are the whole payload. | REQ-006 and HLD section 7: the Worker discards the result when it differs, marking the job stale. Tenet 7: ids only, no resume text. |
| `attempt` | `smallint` | No |  | `0` | Attempts started, at most 3. | HLD section 6: at most 3 attempts, then failed (dead letter); read as 3 attempts in total (open concern 8). |
| `run_after` | `timestamptz` | No |  | `now()` | Earliest time the job may be claimed; pushed out by backoff. | HLD section 6: transport retries reschedule the job with a delay instead of sleeping in the Worker. |
| `deadline_at` | `timestamptz` | No |  | `now() + interval '30 minutes'` | Time after which retries stop and the job fails. | HLD section 6: a 30 minute deadline. |
| `lease_token` | `uuid` | Yes |  |  | Random token of the Worker holding the job; every result write is conditional on it. | HLD section 7: fencing, so a slow original cannot overwrite the Worker that re-claimed the job. |
| `lease_expires_at` | `timestamptz` | Yes |  |  | When the lease lapses and another Worker may take the job. | HLD section 7: a lease of 180 seconds. |
| `last_error` | `text` | Yes |  |  | Short error code or message from the last failed attempt; never resume text. | AC-US-00-003-3 and tenet 7: the failure is explained with ids and codes only. |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |
| `updated_at` | `timestamptz` | No |  | `now()` | Last change to the row, set by the repository on every UPDATE. | Rule: audit columns (postgres.md). |

**Indexes**

- `idx_jobs_queued_run_after`: on (run_after) where `status = 'queued'`. The claim query: oldest due queued job, FOR UPDATE SKIP LOCKED. The claim must repeat status = 'queued'.
- `idx_jobs_running_lease`: on (lease_expires_at) where `status = 'running'`. Re-claim of jobs whose lease lapsed after a Worker crash. The query must repeat status = 'running'.
- `idx_jobs_role_status`: on (role_id, status). The per-role queue view (AC-US-00-003-6); also the foreign-key index.
- `idx_jobs_candidate_id`: on (candidate_id). Foreign-key index, and the retry lookup for one candidate's jobs.
- `idx_jobs_question_id`: on (question_id). Foreign-key index for the questions reference.
- `uq_jobs_open_candidate`: unique on (candidate_id, type) where `candidate_id IS NOT NULL AND status IN ('queued', 'running')`. One open job per candidate and type, so a double-clicked retry cannot enqueue two paid scoring calls.
- `uq_jobs_open_role_task`: unique on (role_id, type) where `candidate_id IS NULL AND question_id IS NULL AND status IN ('queued', 'running')`. One open criteria proposal or kit generation per role, for the same reason.
- `uq_jobs_open_question`: unique on (question_id) where `question_id IS NOT NULL AND status IN ('queued', 'running')`. One open regeneration per question, so a double click cannot enqueue two paid calls.

**Constraints**

- `chk_jobs_type`: `type IN ('process_resume', 'propose_criteria', 'generate_kit', 'regenerate_question', 'rescore')`. Refuses a job no Worker handler exists for.
- `chk_jobs_status`: `status IN ('queued', 'running', 'succeeded', 'failed', 'stale', 'cancelled')`. Refuses a state the claim query and the queue view do not know.
- `chk_jobs_attempt_range`: `attempt BETWEEN 0 AND 3`. Refuses a fourth attempt, which the dead-letter rule forbids.
- `chk_jobs_lease_together`: `(lease_token IS NULL) = (lease_expires_at IS NULL)`. Refuses a token with no expiry (never re-claimed) or an expiry with no token (unfenced).
- `chk_jobs_target_shape`: `(type IN ('process_resume', 'rescore') AND candidate_id IS NOT NULL AND question_id IS NULL) OR (type = 'regenerate_question' AND question_id IS NOT NULL AND candidate_id IS NULL) OR (type IN ('propose_criteria', 'generate_kit') AND candidate_id IS NULL AND question_id IS NULL)`. Refuses a scoring job with no candidate, or a job with the wrong target for its type.

### `call_log`: Call log (hot: no)

One row per Gateway call, live or replayed: purpose, tokens and the cost counted against the budget.

Serves US-02-001, US-02-002, US-02-003. Expected volume: tens of thousands of rows a year (10^4 to 10^5): about 150 a day (HLD section 4).

Writers: the Gateway only, in its own transaction (reserve, then settle or release) and never in the transaction that stores scores (tenet 8). Replay writes a row with status replayed and cost 0.

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | `bigint` | No | PK | identity | Sequence number of the call. | AC-US-02-001-4: one log row per call. |
| `role_id` | `uuid` | Yes | FK roles.id |  | The role the call was for; null for eval calls made outside a role. | AC-US-02-001-4: the log holds the role. RESTRICT: the spend record outlives no role deletion. |
| `purpose` | `text` | No |  |  | criteria, scoring, kit or eval. | AC-US-02-001-4: purpose is logged. |
| `status` | `call_status` | No |  |  | reserved, settled, replayed or released. | Tenet 8: reserved before the call, settled after; replayed rows never touch the budget. |
| `model` | `text` | No |  |  | Model id sent, for example claude-haiku-4-5. | AC-US-02-001-2: the model is one configuration value; the log records it. Part of the replay key. |
| `request_key` | `text` | No |  |  | SHA-256 hex of request, model id, prompt version and schema-retry index; no text. | AC-US-02-003-1 and AC-US-02-003-2: replay is keyed by a hash, and a missing recording names it. |
| `schema_retry` | `smallint` | No |  | `0` | 0 for the first try, 1 for the retry after malformed output. | REQ-023 and decisions.md conflict 2: the retry has its own key. |
| `input_tokens` | `integer` | Yes |  |  | Input tokens; null until settled. | AC-US-02-001-4: input tokens are logged. |
| `output_tokens` | `integer` | Yes |  |  | Output tokens; null until settled. | AC-US-02-001-4: output tokens are logged. |
| `cost_usd` | `numeric(12,6)` | No |  | `0` | USD counted against the budget for this call: the reserved maximum, then the actual cost, 0 when replayed or released. | AC-US-02-002-1: the running total rises by each call's cost. An unsettled timeout keeps its reservation, so spend is over-counted, never under-counted (HLD section 7). |
| `created_at` | `timestamptz` | No |  | `now()` | When the row was written. | Rule: audit columns (postgres.md). |
| `updated_at` | `timestamptz` | No |  | `now()` | Last change to the row, set by the repository on every UPDATE. | Rule: audit columns (postgres.md). |

**Indexes**

- `idx_call_log_created_at`: on (created_at DESC, id DESC). The cost log screen, newest first, and cost by day (AC-US-00-012-4, HLD section 11).
- `idx_call_log_role_id`: on (role_id). Foreign-key index, and cost per role.

**Constraints**

- `chk_call_log_purpose`: `purpose IN ('criteria', 'scoring', 'kit', 'eval')`. Refuses a purpose the cost report cannot group.
- `chk_call_log_schema_retry_range`: `schema_retry IN (0, 1)`. Refuses a second schema retry, which REQ-023 forbids.
- `chk_call_log_request_key_shape`: `request_key ~ '^[0-9a-f]{64}$'`. Refuses a key that is not a SHA-256 hex digest, which replay would never find.
- `chk_call_log_cost_non_negative`: `cost_usd >= 0`. Refuses a negative cost that would lower the running total.
- `chk_call_log_replay_free`: `status NOT IN ('replayed', 'released') OR cost_usd = 0`. Refuses a replayed or released call that still draws on the budget (HLD section 3).
- `chk_call_log_settled_tokens`: `status <> 'settled' OR (input_tokens IS NOT NULL AND output_tokens IS NOT NULL)`. Refuses a settled call with no token counts (AC-US-02-001-4).

### `budget`: Budget (hot: yes: updated on every live call, but a single row)

The single running total of model spend, held under the USD 8 cap.

Serves US-02-002. Expected volume: one row (10^0).

Writers: the Gateway only, with one atomic UPDATE ... WHERE spent_usd + :reserve <= 8 (tenet 8). The row itself is inserted at start-up from spend-ledger.json, not by schema.sql, because its value comes from a committed file. Settle with LEAST(8, ...) because an actual cost above the reservation would otherwise violate the cap after the provider has billed; call_log.cost_usd keeps the true cost, so an overshoot shows as sum(cost_usd) above spent_usd; start-up sets spent_usd to GREATEST(database value, ledger value), never DO NOTHING. The 8 in the CHECK repeats the constant in code: raising the limit needs an ADR and a migration.

| Column | Type | Null | Key | Default | Description | Why |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | `smallint` | No | PK |  | Always 1; a single-row table. | AC-US-02-002-1: one running total, not per role or per user (US-02-002 non-goals). |
| `spent_usd` | `numeric(12,6)` | No |  | `0` | USD spent or reserved so far, seeded from the committed spend ledger. | AC-US-02-002-2: refuses further calls at the cap; REQ-043 and HLD section 3: seeded from the ledger, never from zero. |
| `updated_at` | `timestamptz` | No |  | `now()` | Last change to the row, set by the repository on every UPDATE. | Rule: audit columns (postgres.md). |

**Constraints**

- `chk_budget_single_row`: `id = 1`. Refuses a second total that two Gateway paths could update separately.
- `chk_budget_spent_cap`: `spent_usd >= 0 AND spent_usd <= 8`. Refuses an UPDATE that skipped the reserve-under-the-cap predicate (tenet 8) and would pass USD 8.

## 5. Enumerations

Postgres enum types, for sets fixed by the PRD:

| Name | Values | Why |
| --- | --- | --- |
| `user_role` | `recruiter`, `interviewer` | PRD section 3 defines exactly two roles (AC-US-00-012-1, AC-US-00-012-2); a third role is a permission-matrix rewrite, not a value. |
| `role_status` | `draft`, `approved` | REQ-005 defines Draft and Approved only; every gate on upload, scoring and kit reads these two. |
| `criterion_kind` | `must_have`, `nice_to_have` | REQ-003 and REQ-024: the two kinds are the basis of must-have coverage; no third kind exists in the PRD. |
| `candidate_stage` | `new`, `screened`, `interview`, `offer`, `hired`, `rejected`, `withdrawn` | PRD 4.1 fixes the seven stages (AC-US-00-011-1, AC-US-00-011-3); a new stage is a migration and a UI change. |
| `processing_state` | `queued`, `parsing`, `anonymizing`, `scoring`, `done`, `failed` | AC-US-00-003-5 lists exactly these six per-file statuses; a new one is a migration and a queue-view change. |
| `score_status` | `scored`, `no_evidence`, `failed` | REQ-019, REQ-021 and REQ-023: a criterion is scored with a quote, marked no evidence, or failed after the retry; nothing else is stored. |
| `call_status` | `reserved`, `settled`, `replayed`, `released` | HLD section 3 Gateway steps 4 and 5: reserved before a live call, settled after, replayed in replay mode, released when the provider reports no usage. |

Sets kept as `text` plus a named CHECK because they grow with features (a new value is a constraint swap, not an enum rewrite):

| Column | Values | Why |
| --- | --- | --- |
| `jobs.type` | `process_resume`, `propose_criteria`, `generate_kit`, `regenerate_question`, `rescore` | HLD section 3 Worker job types; kept as text plus CHECK because job types grow with features. |
| `jobs.status` | `queued`, `running`, `succeeded`, `failed`, `stale`, `cancelled` | HLD sections 2 and 7 (stale, failed as dead letter) and AC-US-00-001-4 (cancel); text plus CHECK so a new state is a cheap constraint swap. |
| `call_log.purpose` | `criteria`, `scoring`, `kit`, `eval` | REQ-042 names exactly these four purposes. |
| `audit_events.kind` | `score_override`, `stage_change`, `identity_reveal`, `feedback_edit_approved`, `feedback_edited` | REQ-030 (overrides, stage moves), AC-US-00-009-2 (reveal), AC-US-00-014-5 (approved feedback edit); text plus CHECK so a new audited action is a constraint swap. |
| `resume_files.media_type` | `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | REQ-007 accepts PDF and DOCX only. |

## 6. Retention and personal data

Rules marked **UNDEFINED** are decisions owed by a person before any real candidate data is stored; this document does not make them. The first build is local and synthetic (HLD section 4, Q-006), and Q-012 keeps the per-role retention setting out of scope, so no purge or TTL job is designed here.

| Table | Rule | Mechanism | Source |
| --- | --- | --- | --- |
| `resume_files` | Deleted when extraction succeeds. A failed file's maximum stay is UNDEFINED (asked: how long may a failed file stay before a person must retry or delete it? owner midhun) | Worker deletes the row in the transaction that stores the text; nothing for failed files until decided | ADR-0008, HLD section 4 |
| `resume_raw_texts` | UNDEFINED (asked: how long after a role closes is raw text kept? PRD section 9 gives 30, 90 or 180 days only as examples for a stretch setting; owner midhun) | none until decided; a later purge drops this table's rows alone, keeping `resume_texts` | Q-012, not stated |
| `resume_texts`, `candidates`, `scores`, `feedback` | UNDEFINED (asked: how long after a role closes are candidate records kept, and do anonymized aggregates outlive them? owner midhun) | none until decided | Q-012, PRD section 9 |
| `audit_events` | UNDEFINED (asked: does audit history outlive a deleted candidate, or is it purged with it? owner midhun) | none; the candidate reference is RESTRICT, so a future purge must delete the events first, deliberately | REQ-030, not stated |
| `users` | UNDEFINED (asked: when is a seeded account removed? owner midhun) | none | not stated |
| `sessions` | UNDEFINED (asked: session lifetime and when expired rows are removed? owner midhun) | `expires_at` is checked on every request; no sweeper is designed | ADR-0005 (we own session expiry), not stated |
| `roles`, `criteria`, `rubric_levels`, `assignments`, `interview_kits`, `questions`, `jobs`, `call_log`, `budget` | Kept; no deletion job in the first build | none | HLD section 4 |

Lifetimes compose: a future candidate purge cascades to `resume_*`, `scores`, `assignments`, `feedback` and `jobs`, and is stopped by `audit_events` (RESTRICT) until those events are deleted first. `feedback` is deleted with the candidate, so a purge takes locked feedback too; the owner decides that with the audit question.

Size from the rule: no rule ties a table to a date yet, so rows accumulate. At the HLD peak every table stays below 10^7 rows for years (largest: `scores`, 10^5 to 10^6 a year), so a purge, when decided, is a batched hard delete, not partitions. `pg_dump` copies personal data; a backup is a copy of every table marked below.

Personal-data columns (13): `users.name` (name), `users.email` (contact), `users.password_hash` (credential), `candidates.file_name` (name inside a file name), `candidates.identity_name` (name), `resume_files.content` (original resume file), `resume_raw_texts.raw_text` (full resume text), `resume_texts.anonymized_text` (derived from a resume; proxy signals can remain), `scores.quote` (excerpt of a resume), `scores.override_note` (free text about a candidate), `audit_events.old_comment` (free text about a candidate), `audit_events.note` (free text about a candidate), `feedback.comment` (free text about a candidate).

## 7. Migration plan

| # | db-migration name | Phase (expand \| migrate \| contract) | Hot table | Lock risk and batch note |
| --- | --- | --- | --- | --- |
| 1 | initial_schema (schema.sql) | expand | no | Empty database, no lock risk, no backfill. The repository has no migration yet, so no numbering convention is claimed: the Alembic setup (backend/alembic) numbers it. The Down step drops the trigger and function, then tables in reverse order, then the seven enum types. |
| 2 | database_roles_and_grants | expand | no | Built (alembic/versions/0002_database_roles_and_grants.py). Creates `hirekit_api` and `hirekit_worker` (NOLOGIN unless `HIREKIT_API_PASSWORD` and `HIREKIT_WORKER_PASSWORD` are set at migrate time) with per-table and per-column grants: the Worker cannot update `candidates.stage` (tenet 4), the Api cannot write a score's model columns (tenet 3) or the budget and call log (tenet 8), and neither can update or delete `audit_events`. Brief per-table lock while grants change. Down revokes and drops both roles; it fails if a role has privileges in another database of the cluster. |

Migrations: 2 (hot-table batches: 0). Not migrations: the `budget` row is inserted at start-up from `backend/recordings/spend-ledger.json` (its value comes from a committed file), and the seed command loads users, roles and criteria.

Later changes are new migrations, planned when they arrive. Two are already known: any change to `scores` after it passes 10^6 rows needs `CREATE INDEX CONCURRENTLY` outside a transaction and `NOT VALID` then `VALIDATE` for a CHECK or FK; and raising the USD 8 cap needs an ADR and a migration of `chk_budget_spent_cap`.

## 8. Rules and deviations

Rules checked: 34 (23 against `database/references/postgres.md`, 11 design checks). Deviations: 5.

Followed: snake_case plural names; ids as uuid or bigint identity, never `serial`; `timestamptz` throughout; NOT NULL by default; enum versus text CHECK by how often the set changes; soft delete only for `criteria` (`retired_at`, with its partial index repeating `retired_at IS NULL`; the batched hard delete of retired rows waits for the retention decision, section 6); every foreign key with an explicit ON DELETE and an index on the referencing column; b-tree for equality and range, an expression index for `lower(email)`; composite order equality first, then the sort column; partial indexes repeat their predicate in the query; no covering index (no top read query is measured yet); no `CREATE INDEX CONCURRENTLY` (no table is over 1M rows); identifiers under 50 characters; the `lock_timeout` and `statement_timeout` header for db-migration; no unused-index review yet (no traffic). Design checks: every writer named per table; tenant-safe references (below); no new requirement on an existing table (new database); predicates immutable (no index or constraint calls `now()`; `deadline_at` and `lease_expires_at` are compared in queries); derived rows follow their parent; lifetimes compose (section 6); size from the rule (section 6); ambiguous numbers read aloud (open concern 8); hot-table changes (none); uniqueness has a lifecycle (`uq_users_email` is global; `uq_jobs_open_*` release when a job leaves queued or running).

- deviation: tenant_id first in composite keys and tenant-safe references, HireKit is a single-organisation local app with no tenant column (HLD section 1 non-goals, Q-006), revisit if it is hosted for more than one organisation.
- deviation: `text` with `CHECK (length(x) <= n)`, no story states a maximum for a title, description, note or comment, so any number would be invented; the Api validates request size, revisit when a story sets limits.
- deviation: money as `numeric(19,4)` or minor units with a `currency` column, `cost_usd` and `spent_usd` are `numeric(12,6)` USD with no currency column, because a call costs about 0.005 USD (four decimals lose it) and the budget is USD 8 only (REQ-043), revisit if a second currency appears.
- deviation: `created_at` and `updated_at` on every table, write-once tables (`sessions`, `users`, `resume_*`, `assignments`, `audit_events`) carry `created_at` only, since nothing updates them, revisit if a story edits one.
- deviation: composite `(role_id, id)` foreign keys for every cross-role reference, only `questions` has one; `scores`, `feedback` and `jobs` would need a denormalised `role_id` to carry it, so the Worker and Api queries keep a candidate and a criterion of the same role, revisit if a second writer of scores appears.

## 9. What the review found

Reviewed by: critic, 2026-09-30, against the acceptance criteria and the design checks.

Findings: BLOCKER 0, MAJOR 6, MINOR 3, NIT 0 (open 0).

### MAJOR: a manual retry reused the old job row with an expired deadline and an old version (`jobs`)

A recruiter edits criteria (v2) after C-014 failed at v1 and presses retry; the job still carries v1, so every result is discarded as stale, and a retry more than 30 minutes after upload starts past its deadline.

**Fix:** a retry inserts a new job row with the current `criteria_version` and a fresh `deadline_at`; the old row stays failed. Status: fixed in this version (jobs Writers note).

### MAJOR: a rescore could overwrite or detach recruiter overrides (`scores`)

One call returns every criterion, so re-running a failed criterion rewrites the others, including one the recruiter overrode.

**Fix:** the upsert never sets `override_*`; a same-version rescore rewrites only `failed` rows; an override does not carry to a new version (open concern 3). Status: fixed in this version (scores Writers note).

### MAJOR: kit and proposal jobs had no version fence, and `interview_kits.stale` was a flag writers had to remember (`jobs`, `interview_kits`)

A `generate_kit` enqueued at v3 and run after an edit to v4 stored a kit marked fresh, because no kit row existed to mark. A cancelled proposal could still write.

**Fix:** `jobs.criteria_version` is NOT NULL for every job type; `interview_kits.stale` is replaced by `interview_kits.criteria_version`, so staleness is derived like scores; cancel clears the lease. Status: fixed in this version.

### MAJOR: a crashed job at attempt 3 could stay `running` forever (`jobs`)

A reclaim that increments `attempt` past 3 violates `chk_jobs_attempt_range` and aborts the reclaim batch; fencing also needs the result transaction to lock the job row.

**Fix:** a reclaim at attempt 3 sets `failed` and the candidate's `failure_reason` instead of incrementing; the result transaction runs `SELECT ... WHERE lease_token = :mine FOR UPDATE`. Both are written into the jobs Writers note. Status: fixed in this version.

### MAJOR: `feedback.criterion_id` RESTRICT blocks deleting a criterion after feedback exists (`feedback`, `criteria`)

Deleting a criterion (AC-US-00-002-1) fails once feedback exists, and a delete-and-reinsert edit would cascade away scores and questions.

**Fix:** criteria edits are in-place updates by id; whether a criterion with feedback can be deleted or is retired (`retired_at`) was decided on 2026-09-30: deleting retires (`criteria.retired_at`), so RESTRICT never blocks it. Status: fixed in this version.

### MAJOR: "only a recruiter action changes a stage" is a convention, not a mechanism (`candidates`)

A whole-row write by the Worker's repository could put back an old stage with no audit row.

**Fix:** separate `hirekit_api` and `hirekit_worker` database roles with a column-level GRANT (migration 2, decided on 2026-09-30). Status: fixed in the plan; the roles are created by migration 2.

### MINOR: settling a call could break the cap after the provider billed; budget row seeding was unstated (`budget`)

**Fix:** settle with `LEAST(8, ...)` and record the overshoot; start-up sets `GREATEST(database, ledger)`. Status: fixed in this version (budget Writers note).

### MINOR: `uq_jobs_open_role_task` did not cover `regenerate_question` (`jobs`)

**Fix:** added `uq_jobs_open_question`. Status: fixed in this version.

### MINOR: the approve-edit route has no key, and an edit loses its history (`feedback`, `audit_events`)

Feedback's key is (candidate, interviewer, criterion), and `feedback_edited` keeps the old score but not the old comment.

**Fix:** route by candidate and interviewer; `audit_events.old_comment` keeps the previous comment (decided 2026-09-30). Status: fixed in this version; the route shape goes to the OpenAPI spec.

Weakest claims the critic named: (1) "a score row exists only after its quote was verified" is enforced by code, not by the schema (open concern 9); (2) `resume_files` is deleted in the transaction that stores the text, so a re-run after that commit has no file (fixed: `process_resume` skips extraction when `resume_texts` exists); (3) derived rows follow their parent (fixed for kits and scores by the version columns).

## 10. Open concerns

Each entry: what, the table, the consequence, owner and date. Owner for all: midhun.

1. **[settled 2026-09-30]** REQ-004 (delete criteria) against REQ-037 (locked feedback). `feedback.criterion_id` is RESTRICT, so a criterion with submitted feedback cannot be deleted; soft retirement (`retired_at`) would allow it. Decision: deleting a criterion sets `criteria.retired_at`; feedback stays RESTRICT. (`criteria`, `feedback`) Blocks development: no.
2. **[gap]** Retention is UNDEFINED for personal-data tables (section 6). Q-012 is a stretch, but no real candidate data may be stored before it is decided. By 2026-10-14. Blocks development: no.
3. **[ambiguity]** An override belongs to one `criteria_version`; after a re-run at a new version the new row carries none. Modelled so, with history in `audit_events`. Should overrides carry over? (`scores`) By 2026-10-14. Blocks development: no.
4. **[gap]** PRD 4.2 lists "needs attention" as a file status; AC-US-00-003-5 does not. Modelled as `failed` with a reason. (`candidates`) By 2026-10-14. Blocks development: no.
5. **[risk]** Session lifetime and the removal of expired sessions are unstated; `sessions.expires_at` is written by the Api from a value nobody has chosen. (`sessions`) By 2026-10-14. Blocks development: no.
6. **[ambiguity]** The seed command is assumed to write through the Api upload and criteria functions; a direct SQL seed would leave `content_hash` unsourced. (`candidates`, `criteria`) By 2026-10-07. Blocks development: no.
7. **[gap]** `assignments.user_id` may name a recruiter; the route checks the role, the database does not. (`assignments`) By 2026-10-14. Blocks development: no.
8. **[ambiguity]** "At most 3 attempts" is read as 3 attempts in total (`attempt` 0 to 3, then failed), not 3 retries after the first. (`jobs`) By 2026-10-07. Blocks development: no.
9. **[risk]** The quote guarantee (tenet 3) is enforced by code; the database only requires a quote on a scored row. A trigger comparing whitespace-normalized text against `resume_texts` would move it into the database. (`scores`) By 2026-10-14. Blocks development: no.
10. **[settled 2026-09-30]** The approve-edit route should address (candidate, interviewer), and the audit row should keep the old comment; `audit_events` has no old-comment column. (`feedback`, `audit_events`) Decision: `audit_events.old_comment` added; the route is `POST /v1/candidates/{id}/feedback/{interviewer}:approve-edit`, to be written in the OpenAPI spec. Blocks development: no.
11. **[settled 2026-09-30]** Stage protection needs database roles with a column-level GRANT (migration 2). Decision: migration 2 creates `hirekit_api` and `hirekit_worker` with column-level grants; until it is applied tenet 4 rests on code review. (`candidates`) By 2026-10-14. Blocks development: no.
12. **[gap]** After a scoring job is discarded as stale, the candidate's `processing_status` has no state for it; modelled as `done` with stale scores and a re-run offered. (`candidates`, `jobs`) By 2026-10-14. Blocks development: no.
13. **[gap]** `resume_texts` has no anonymizer version, so after an anonymizer fix, text verified under the old one cannot be told from new text. (`resume_texts`) By 2026-10-14. Blocks development: no.
14. **[gap]** Nothing reconciles `reserved` `call_log` rows left by timeouts (HLD section 16 already lists who reconciles the budget). No index on status; add one if a report needs it. (`call_log`) By 2026-10-14. Blocks development: no.
15. **[scope]** Eval labels, name-swap pair links, recordings and the spend ledger are assumed to be committed files, not tables. (not modelled) By 2026-10-07. Blocks development: no.
16. **[risk]** `audit_events` is protected against UPDATE only; DELETE is left possible for a future purge, and TRUNCATE is not addressed. Column grants in migration 2 should remove both from the application roles. (`audit_events`) By 2026-10-14. Blocks development: no.
17. **[risk]** The 8 in `chk_budget_spent_cap` repeats the constant in code; raising the cap needs an ADR and a migration. (`budget`) By 2026-10-14. Blocks development: no.

## 11. Applying this

`schema.sql` runs top to bottom in one transaction against an empty database: enum types first, then tables in foreign-key order. Use it as the first migration; every change after the first release is its own migration, never an edit to this file.

- Gate: `data-model: 18 tables, 133 columns, 25 indexes, 43 checks, 7 enums, 13 personal-data columns, 0 problems`
- Applied to an empty Postgres: `schema-apply: docs/design/schema.sql applied to postgres:16, 18 tables`
- Behaviour checked in a throwaway postgres:16 after the decisions (16 statements): a quoteless scored row, a no-evidence score above 0, a short override note, an audit UPDATE, spend above 8, a cross-role question, a duplicate open job, a hard delete of a criterion with feedback, a delete of a candidate with audit history, a failed file with no reason, a same-stage move and a job with no criteria_version were all refused. Retiring a criterion that has feedback, and a feedback_edited event with old_comment, were accepted.
