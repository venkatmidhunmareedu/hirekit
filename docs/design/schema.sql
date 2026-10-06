-- HireKit: database schema (PostgreSQL 16 or later)
-- Written by data-model beside docs/design/data-model.md, which gives the
-- reason for every table, column, index and constraint below.
--
-- Applies in one transaction to an empty database: enum types first, then
-- tables in foreign-key order, each followed by its comments and indexes.
-- Use it as the first migration; every change after the first release is its
-- own migration (db-migration), never an edit to this file.

BEGIN;

CREATE TYPE user_role AS ENUM ('recruiter', 'interviewer');
CREATE TYPE role_status AS ENUM ('draft', 'approved');
CREATE TYPE criterion_kind AS ENUM ('must_have', 'nice_to_have');
CREATE TYPE candidate_stage AS ENUM ('new', 'screened', 'interview', 'offer', 'hired', 'rejected', 'withdrawn');
CREATE TYPE processing_state AS ENUM ('queued', 'parsing', 'anonymizing', 'scoring', 'done', 'failed');
CREATE TYPE score_status AS ENUM ('scored', 'no_evidence', 'failed');
CREATE TYPE call_status AS ENUM ('reserved', 'settled', 'replayed', 'released');

-- users: A seeded recruiter or interviewer who can sign in.
-- Serves US-00-012, US-00-016, US-00-014
CREATE TABLE users (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    name text NOT NULL,
    email text NOT NULL,
    role user_role NOT NULL,
    password_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_pkey PRIMARY KEY (id),
    CONSTRAINT chk_users_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT chk_users_email_shape CHECK (email ~ '^[^@[:space:]]+@[^@[:space:]]+$')
);
COMMENT ON TABLE users IS 'A seeded recruiter or interviewer who can sign in. Serves US-00-012, US-00-016, US-00-014.';
COMMENT ON COLUMN users.id IS 'Surrogate key.';
COMMENT ON COLUMN users.name IS 'Display name shown beside overrides, stage moves and feedback. [personal data: name]';
COMMENT ON COLUMN users.email IS 'Sign-in identifier, unique ignoring case. [personal data: contact]';
COMMENT ON COLUMN users.role IS 'recruiter or interviewer; the value every route dependency checks.';
COMMENT ON COLUMN users.password_hash IS 'Password hash; the password itself is never stored. [personal data: credential]';
COMMENT ON COLUMN users.created_at IS 'When the row was written.';
-- Sign-in lookup, and refuses two accounts that differ only by case (AC-US-00-012-5).
CREATE UNIQUE INDEX uq_users_email ON users (lower(email));

-- sessions: A server-side session behind the secure cookie.
-- Serves US-00-012
CREATE TABLE sessions (
    token_hash bytea NOT NULL,
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    csrf_token text NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sessions_pkey PRIMARY KEY (token_hash),
    CONSTRAINT chk_sessions_token_hash_length CHECK (octet_length(token_hash) = 32)
);
COMMENT ON TABLE sessions IS 'A server-side session behind the secure cookie. Serves US-00-012.';
COMMENT ON COLUMN sessions.token_hash IS 'SHA-256 of the session cookie value; the cookie itself is never stored.';
COMMENT ON COLUMN sessions.user_id IS 'The signed-in user.';
COMMENT ON COLUMN sessions.csrf_token IS 'Token the client echoes in a header on state-changing requests.';
COMMENT ON COLUMN sessions.expires_at IS 'When the session stops being valid; checked on every request.';
COMMENT ON COLUMN sessions.created_at IS 'When the row was written.';
-- Foreign-key index: sign a user out everywhere, and no table scan when a user is checked on delete.
CREATE INDEX idx_sessions_user_id ON sessions (user_id);

-- roles: A job being hired for: the title, the job description and the approval state that gates everything downstream.
-- Serves US-00-001, US-00-002, US-00-013, US-02-007
CREATE TABLE roles (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    title text NOT NULL,
    job_description text NOT NULL,
    status role_status NOT NULL DEFAULT 'draft',
    criteria_version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT roles_pkey PRIMARY KEY (id),
    CONSTRAINT chk_roles_title_not_blank CHECK (btrim(title) <> ''),
    CONSTRAINT chk_roles_criteria_version_positive CHECK (criteria_version >= 1)
);
COMMENT ON TABLE roles IS 'A job being hired for: the title, the job description and the approval state that gates everything downstream. Serves US-00-001, US-00-002, US-00-013, US-02-007.';
COMMENT ON COLUMN roles.id IS 'Surrogate key.';
COMMENT ON COLUMN roles.title IS 'The role title.';
COMMENT ON COLUMN roles.job_description IS 'The job description the criteria proposal and kit prompts are built from.';
COMMENT ON COLUMN roles.status IS 'Draft or Approved.';
COMMENT ON COLUMN roles.criteria_version IS 'Counter bumped by every criteria or rubric write, including a model proposal.';
COMMENT ON COLUMN roles.created_at IS 'When the row was written.';
COMMENT ON COLUMN roles.updated_at IS 'Last change to the row, set by the repository on every UPDATE.';

-- criteria: One scoring criterion of a role: name, kind, weight and order.
-- Serves US-00-001, US-00-002, US-00-008
CREATE TABLE criteria (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    role_id uuid NOT NULL REFERENCES roles (id) ON DELETE CASCADE,
    name text NOT NULL,
    kind criterion_kind NOT NULL,
    weight numeric(6,3) NOT NULL,
    position integer NOT NULL,
    retired_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT criteria_pkey PRIMARY KEY (id),
    CONSTRAINT uq_criteria_role_id_id UNIQUE (role_id, id),
    CONSTRAINT chk_criteria_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT chk_criteria_weight_positive CHECK (weight > 0)
);
COMMENT ON TABLE criteria IS 'One scoring criterion of a role: name, kind, weight and order. Serves US-00-001, US-00-002, US-00-008.';
COMMENT ON COLUMN criteria.id IS 'Surrogate key.';
COMMENT ON COLUMN criteria.role_id IS 'The role this criterion belongs to.';
COMMENT ON COLUMN criteria.name IS 'What is being judged, for example Python experience.';
COMMENT ON COLUMN criteria.kind IS 'must_have or nice_to_have.';
COMMENT ON COLUMN criteria.weight IS 'Weight in the total; default set by kind, editable.';
COMMENT ON COLUMN criteria.position IS 'Display order inside the role.';
COMMENT ON COLUMN criteria.retired_at IS 'When the recruiter deleted the criterion; null while it is live. Retired rows stay so scores and feedback keep their target.';
COMMENT ON COLUMN criteria.created_at IS 'When the row was written.';
COMMENT ON COLUMN criteria.updated_at IS 'Last change to the row, set by the repository on every UPDATE.';
-- A role's live criteria in display order (AC-US-00-002-1); the query must repeat retired_at IS NULL. The leading role_id is also the foreign-key index.
CREATE INDEX idx_criteria_role_position ON criteria (role_id, position) WHERE retired_at IS NULL;

-- rubric_levels: The descriptor for each score level 0 to 4 of one criterion.
-- Serves US-00-001, US-00-002, US-00-006
CREATE TABLE rubric_levels (
    criterion_id uuid NOT NULL REFERENCES criteria (id) ON DELETE CASCADE,
    level smallint NOT NULL,
    descriptor text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT rubric_levels_pkey PRIMARY KEY (criterion_id, level),
    CONSTRAINT chk_rubric_levels_level_range CHECK (level BETWEEN 0 AND 4),
    CONSTRAINT chk_rubric_levels_descriptor_not_blank CHECK (btrim(descriptor) <> '')
);
COMMENT ON TABLE rubric_levels IS 'The descriptor for each score level 0 to 4 of one criterion. Serves US-00-001, US-00-002, US-00-006.';
COMMENT ON COLUMN rubric_levels.criterion_id IS 'The criterion described.';
COMMENT ON COLUMN rubric_levels.level IS 'Score value from 0 to 4; 0 means no evidence.';
COMMENT ON COLUMN rubric_levels.descriptor IS 'What a resume at this level looks like.';
COMMENT ON COLUMN rubric_levels.created_at IS 'When the row was written.';
COMMENT ON COLUMN rubric_levels.updated_at IS 'Last change to the row, set by the repository on every UPDATE.';

-- candidates: One uploaded resume for one role: its stage, its processing state and the fields the list needs.
-- Serves US-00-003, US-00-005, US-00-009, US-00-011
CREATE TABLE candidates (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    candidate_no bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
    role_id uuid NOT NULL REFERENCES roles (id) ON DELETE RESTRICT,
    stage candidate_stage NOT NULL DEFAULT 'new',
    processing_status processing_state NOT NULL DEFAULT 'queued',
    failure_reason text,
    file_name text NOT NULL,
    content_hash text NOT NULL,
    duplicate_of_id uuid REFERENCES candidates (id) ON DELETE SET NULL,
    identity_name text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT candidates_pkey PRIMARY KEY (id),
    CONSTRAINT uq_candidates_candidate_no UNIQUE (candidate_no),
    CONSTRAINT chk_candidates_content_hash_shape CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_candidates_failure_reason CHECK ((processing_status = 'failed') = (failure_reason IS NOT NULL)),
    CONSTRAINT chk_candidates_duplicate_not_self CHECK (duplicate_of_id IS NULL OR duplicate_of_id <> id)
);
COMMENT ON TABLE candidates IS 'One uploaded resume for one role: its stage, its processing state and the fields the list needs. Serves US-00-003, US-00-005, US-00-009, US-00-011.';
COMMENT ON COLUMN candidates.id IS 'Surrogate key.';
COMMENT ON COLUMN candidates.candidate_no IS 'Number shown as C-014 in every list instead of a name.';
COMMENT ON COLUMN candidates.role_id IS 'The role the resume was uploaded to.';
COMMENT ON COLUMN candidates.stage IS 'Hiring stage; written only by the stage endpoint.';
COMMENT ON COLUMN candidates.processing_status IS 'Per-file pipeline status.';
COMMENT ON COLUMN candidates.failure_reason IS 'Plain reason a file failed; null otherwise.';
COMMENT ON COLUMN candidates.file_name IS 'Original upload name. [personal data: name inside a file name]';
COMMENT ON COLUMN candidates.content_hash IS 'SHA-256 hex of the uploaded bytes, kept after the bytes are deleted.';
COMMENT ON COLUMN candidates.duplicate_of_id IS 'The earlier candidate with the same hash; null when not a duplicate.';
COMMENT ON COLUMN candidates.identity_name IS 'Name the anonymizer found, for Reveal identity; recruiters only. [personal data: name]';
COMMENT ON COLUMN candidates.created_at IS 'When the row was written.';
COMMENT ON COLUMN candidates.updated_at IS 'Last change to the row, set by the repository on every UPDATE.';
-- The ranked list for one role filtered by stage (AC-US-00-009-3) and the per-role queue view (AC-US-00-003-6); role_id leads, so it is also the foreign-key index.
CREATE INDEX idx_candidates_role_stage ON candidates (role_id, stage);
-- The duplicate check at upload: earlier candidates of this role with the same hash (AC-US-00-003-4).
CREATE INDEX idx_candidates_role_content_hash ON candidates (role_id, content_hash);
-- Foreign-key index for the self reference; the predicate is implied by any equality on the column.
CREATE INDEX idx_candidates_duplicate_of_id ON candidates (duplicate_of_id) WHERE duplicate_of_id IS NOT NULL;

-- resume_files: The uploaded bytes, held only until extraction succeeds (ADR-0008).
-- Serves US-00-003
CREATE TABLE resume_files (
    candidate_id uuid NOT NULL REFERENCES candidates (id) ON DELETE CASCADE,
    media_type text NOT NULL,
    content bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT resume_files_pkey PRIMARY KEY (candidate_id),
    CONSTRAINT chk_resume_files_media_type CHECK (media_type IN ('application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')),
    CONSTRAINT chk_resume_files_content_not_empty CHECK (octet_length(content) > 0)
);
COMMENT ON TABLE resume_files IS 'The uploaded bytes, held only until extraction succeeds (ADR-0008). Serves US-00-003.';
COMMENT ON COLUMN resume_files.candidate_id IS 'The candidate this file was uploaded as.';
COMMENT ON COLUMN resume_files.media_type IS 'PDF or DOCX media type.';
COMMENT ON COLUMN resume_files.content IS 'The original file bytes. [personal data: original resume file]';
COMMENT ON COLUMN resume_files.created_at IS 'When the row was written.';

-- resume_raw_texts: The extracted text as it came out of the file, before anonymization; recruiters only.
-- Serves US-00-004, US-00-005, US-00-009
CREATE TABLE resume_raw_texts (
    candidate_id uuid NOT NULL REFERENCES candidates (id) ON DELETE CASCADE,
    raw_text text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT resume_raw_texts_pkey PRIMARY KEY (candidate_id),
    CONSTRAINT chk_resume_raw_texts_not_blank CHECK (btrim(raw_text) <> '')
);
COMMENT ON TABLE resume_raw_texts IS 'The extracted text as it came out of the file, before anonymization; recruiters only. Serves US-00-004, US-00-005, US-00-009.';
COMMENT ON COLUMN resume_raw_texts.candidate_id IS 'The candidate whose file this text came from.';
COMMENT ON COLUMN resume_raw_texts.raw_text IS 'Extracted text with names, contacts and location intact. [personal data: full resume text]';
COMMENT ON COLUMN resume_raw_texts.created_at IS 'When the row was written.';

-- resume_texts: The anonymizer's output: the only resume text the model sees and the text quotes are checked against.
-- Serves US-00-004, US-00-005, US-00-006, US-00-007
CREATE TABLE resume_texts (
    candidate_id uuid NOT NULL REFERENCES candidates (id) ON DELETE CASCADE,
    anonymized_text text NOT NULL,
    anonymizer_version smallint NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT resume_texts_pkey PRIMARY KEY (candidate_id),
    CONSTRAINT chk_resume_texts_not_blank CHECK (btrim(anonymized_text) <> '')
);
COMMENT ON TABLE resume_texts IS 'The anonymizer''s output: the only resume text the model sees and the text quotes are checked against. Serves US-00-004, US-00-005, US-00-006, US-00-007.';
COMMENT ON COLUMN resume_texts.candidate_id IS 'The candidate this text belongs to.';
COMMENT ON COLUMN resume_texts.anonymized_text IS 'Text after identity signals were removed. [personal data: derived from a resume; proxy signals can remain]';
COMMENT ON COLUMN resume_texts.anonymizer_version IS 'Which anonymizer version produced the text, so text from before a fix can be told from new text.';
COMMENT ON COLUMN resume_texts.created_at IS 'When the row was written.';

-- scores: One criterion's score for one candidate at one criteria version, with its verified quote and any recruiter override.
-- Serves US-00-006, US-00-007, US-00-008, US-00-010
CREATE TABLE scores (
    candidate_id uuid NOT NULL REFERENCES candidates (id) ON DELETE CASCADE,
    criterion_id uuid NOT NULL REFERENCES criteria (id) ON DELETE CASCADE,
    criteria_version integer NOT NULL,
    status score_status NOT NULL,
    model_score smallint,
    quote text,
    flag_reason text,
    override_score smallint,
    override_note text,
    overridden_by uuid REFERENCES users (id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT scores_pkey PRIMARY KEY (candidate_id, criterion_id, criteria_version),
    CONSTRAINT chk_scores_criteria_version_positive CHECK (criteria_version >= 1),
    CONSTRAINT chk_scores_model_score_range CHECK (model_score BETWEEN 0 AND 4),
    CONSTRAINT chk_scores_status_shape CHECK ((status = 'scored' AND model_score IS NOT NULL AND quote IS NOT NULL) OR (status = 'no_evidence' AND model_score = 0 AND quote IS NULL) OR (status = 'failed' AND model_score IS NULL AND quote IS NULL)),
    CONSTRAINT chk_scores_override_range CHECK (override_score BETWEEN 0 AND 4),
    CONSTRAINT chk_scores_override_all_or_none CHECK ((override_score IS NULL) = (override_note IS NULL) AND (override_score IS NULL) = (overridden_by IS NULL)),
    CONSTRAINT chk_scores_override_note_length CHECK (override_note IS NULL OR length(btrim(override_note)) >= 10)
);
COMMENT ON TABLE scores IS 'One criterion''s score for one candidate at one criteria version, with its verified quote and any recruiter override. Serves US-00-006, US-00-007, US-00-008, US-00-010.';
COMMENT ON COLUMN scores.candidate_id IS 'The candidate scored.';
COMMENT ON COLUMN scores.criterion_id IS 'The criterion scored.';
COMMENT ON COLUMN scores.criteria_version IS 'The roles.criteria_version the score was computed against; the scoring run.';
COMMENT ON COLUMN scores.status IS 'scored, no_evidence or failed.';
COMMENT ON COLUMN scores.model_score IS 'The model''s score after capping; null when failed.';
COMMENT ON COLUMN scores.quote IS 'The evidence quote, stored only after code found it in the anonymized text. [personal data: excerpt of a resume]';
COMMENT ON COLUMN scores.flag_reason IS 'One line saying why the item is flagged, for example the quote was not found.';
COMMENT ON COLUMN scores.override_score IS 'Recruiter''s replacement value; null when not overridden.';
COMMENT ON COLUMN scores.override_note IS 'Why the recruiter overrode. [personal data: free text about a candidate]';
COMMENT ON COLUMN scores.overridden_by IS 'The recruiter who overrode.';
COMMENT ON COLUMN scores.created_at IS 'When the row was written.';
COMMENT ON COLUMN scores.updated_at IS 'Last change to the row, set by the repository on every UPDATE.';
-- Sort the ranked list by one criterion for the current version (AC-US-00-009-3); the leading criterion_id is also the foreign-key index.
CREATE INDEX idx_scores_criterion_id ON scores (criterion_id, criteria_version);
-- Foreign-key index for the users reference; the predicate is implied by any equality on the column.
CREATE INDEX idx_scores_overridden_by ON scores (overridden_by) WHERE overridden_by IS NOT NULL;

-- assignments: Which interviewer may see which candidate.
-- Serves US-00-016, US-00-012, US-00-014
CREATE TABLE assignments (
    candidate_id uuid NOT NULL REFERENCES candidates (id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT assignments_pkey PRIMARY KEY (candidate_id, user_id)
);
COMMENT ON TABLE assignments IS 'Which interviewer may see which candidate. Serves US-00-016, US-00-012, US-00-014.';
COMMENT ON COLUMN assignments.candidate_id IS 'The candidate assigned.';
COMMENT ON COLUMN assignments.user_id IS 'The interviewer assigned.';
COMMENT ON COLUMN assignments.created_at IS 'When the row was written.';
-- An interviewer's candidate list, the predicate every interviewer query carries (AC-US-00-012-3, tenet 6); also the foreign-key index.
CREATE INDEX idx_assignments_user_id ON assignments (user_id);

-- audit_events: Append-only history of who did what to a candidate: overrides, stage moves, identity reveals and approved feedback edits.
-- Serves US-00-009, US-00-010, US-00-011, US-00-014
CREATE TABLE audit_events (
    id bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
    candidate_id uuid NOT NULL REFERENCES candidates (id) ON DELETE RESTRICT,
    actor_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    kind text NOT NULL,
    criterion_name text,
    old_score smallint,
    new_score smallint,
    from_stage candidate_stage,
    to_stage candidate_stage,
    subject_user_id uuid REFERENCES users (id) ON DELETE RESTRICT,
    old_comment text,
    note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT audit_events_pkey PRIMARY KEY (id),
    CONSTRAINT chk_audit_events_kind CHECK (kind IN ('score_override', 'stage_change', 'identity_reveal', 'feedback_edit_approved', 'feedback_edited')),
    CONSTRAINT chk_audit_events_override_shape CHECK (kind <> 'score_override' OR (criterion_name IS NOT NULL AND new_score IS NOT NULL AND note IS NOT NULL AND length(btrim(note)) >= 10)),
    CONSTRAINT chk_audit_events_stage_shape CHECK (kind <> 'stage_change' OR (from_stage IS NOT NULL AND to_stage IS NOT NULL AND from_stage <> to_stage)),
    CONSTRAINT chk_audit_events_feedback_shape CHECK (kind NOT IN ('feedback_edit_approved', 'feedback_edited') OR subject_user_id IS NOT NULL)
);
COMMENT ON TABLE audit_events IS 'Append-only history of who did what to a candidate: overrides, stage moves, identity reveals and approved feedback edits. Serves US-00-009, US-00-010, US-00-011, US-00-014.';
COMMENT ON COLUMN audit_events.id IS 'Sequence number; the order of events.';
COMMENT ON COLUMN audit_events.candidate_id IS 'The candidate acted on.';
COMMENT ON COLUMN audit_events.actor_id IS 'The user who acted.';
COMMENT ON COLUMN audit_events.kind IS 'score_override, stage_change, identity_reveal, feedback_edit_approved or feedback_edited.';
COMMENT ON COLUMN audit_events.criterion_name IS 'Name of the criterion at the time; null for stage and reveal events.';
COMMENT ON COLUMN audit_events.old_score IS 'Value before the change.';
COMMENT ON COLUMN audit_events.new_score IS 'Value after the change.';
COMMENT ON COLUMN audit_events.from_stage IS 'Stage before a stage_change.';
COMMENT ON COLUMN audit_events.to_stage IS 'Stage after a stage_change.';
COMMENT ON COLUMN audit_events.subject_user_id IS 'The interviewer whose feedback an event concerns.';
COMMENT ON COLUMN audit_events.old_comment IS 'The comment before a feedback_edited change; null for other kinds. [personal data: free text about a candidate]';
COMMENT ON COLUMN audit_events.note IS 'Override note or optional stage reason. [personal data: free text about a candidate]';
COMMENT ON COLUMN audit_events.created_at IS 'When it happened.';
-- A candidate's history, newest first (AC-US-00-011-2); also the foreign-key index.
CREATE INDEX idx_audit_events_candidate_created ON audit_events (candidate_id, created_at DESC, id DESC);
-- Foreign-key index for the users reference.
CREATE INDEX idx_audit_events_actor_id ON audit_events (actor_id);
-- Foreign-key index for the users reference; the predicate is implied by any equality on the column.
CREATE INDEX idx_audit_events_subject_user_id ON audit_events (subject_user_id) WHERE subject_user_id IS NOT NULL;
-- Append-only: an audit row is never edited (REQ-030). Deleting is possible only
-- by an explicit purge job, because the candidate reference is RESTRICT.
CREATE FUNCTION audit_events_refuse_update() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_events rows cannot be updated';
END;
$$;
CREATE TRIGGER trg_audit_events_append_only BEFORE UPDATE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_refuse_update();

-- interview_kits: The per-role kit header: whether one exists and whether it is stale.
-- Serves US-00-002, US-00-013
CREATE TABLE interview_kits (
    role_id uuid NOT NULL REFERENCES roles (id) ON DELETE CASCADE,
    criteria_version integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT interview_kits_pkey PRIMARY KEY (role_id),
    CONSTRAINT chk_interview_kits_version_positive CHECK (criteria_version >= 1)
);
COMMENT ON TABLE interview_kits IS 'The per-role kit header: whether one exists and whether it is stale. Serves US-00-002, US-00-013.';
COMMENT ON COLUMN interview_kits.role_id IS 'The role the kit is for.';
COMMENT ON COLUMN interview_kits.criteria_version IS 'The roles.criteria_version the kit was generated against.';
COMMENT ON COLUMN interview_kits.created_at IS 'When the row was written.';
COMMENT ON COLUMN interview_kits.updated_at IS 'Last change to the row, set by the repository on every UPDATE.';

-- questions: One interview question for one criterion, with what a strong and a weak answer look like.
-- Serves US-00-013, US-00-014
CREATE TABLE questions (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    role_id uuid NOT NULL REFERENCES interview_kits (role_id) ON DELETE CASCADE,
    criterion_id uuid NOT NULL,
    question_text text NOT NULL,
    strong_answer text NOT NULL,
    weak_answer text NOT NULL,
    position integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT questions_pkey PRIMARY KEY (id),
    CONSTRAINT fk_questions_role_criterion FOREIGN KEY (role_id, criterion_id) REFERENCES criteria (role_id, id) ON DELETE CASCADE,
    CONSTRAINT chk_questions_fields_not_blank CHECK (btrim(question_text) <> '' AND btrim(strong_answer) <> '' AND btrim(weak_answer) <> '')
);
COMMENT ON TABLE questions IS 'One interview question for one criterion, with what a strong and a weak answer look like. Serves US-00-013, US-00-014.';
COMMENT ON COLUMN questions.id IS 'Surrogate key.';
COMMENT ON COLUMN questions.role_id IS 'The role whose kit holds the question.';
COMMENT ON COLUMN questions.criterion_id IS 'The criterion the question probes.';
COMMENT ON COLUMN questions.question_text IS 'The question.';
COMMENT ON COLUMN questions.strong_answer IS 'What a strong answer looks like.';
COMMENT ON COLUMN questions.weak_answer IS 'What a weak answer looks like.';
COMMENT ON COLUMN questions.position IS 'Order inside the criterion.';
COMMENT ON COLUMN questions.created_at IS 'When the row was written.';
COMMENT ON COLUMN questions.updated_at IS 'Last change to the row, set by the repository on every UPDATE.';
-- The kit for a role grouped by criterion in order (AC-US-00-013-2); the leading pair is also the composite foreign-key index.
CREATE INDEX idx_questions_role_criterion_position ON questions (role_id, criterion_id, position);

-- feedback: One interviewer's score and comment for one criterion of one candidate.
-- Serves US-00-014, US-00-015
CREATE TABLE feedback (
    candidate_id uuid NOT NULL REFERENCES candidates (id) ON DELETE CASCADE,
    interviewer_id uuid NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    criterion_id uuid NOT NULL REFERENCES criteria (id) ON DELETE RESTRICT,
    score smallint NOT NULL,
    comment text NOT NULL,
    locked boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT feedback_pkey PRIMARY KEY (candidate_id, interviewer_id, criterion_id),
    CONSTRAINT chk_feedback_score_range CHECK (score BETWEEN 0 AND 4),
    CONSTRAINT chk_feedback_comment_not_blank CHECK (btrim(comment) <> '')
);
COMMENT ON TABLE feedback IS 'One interviewer''s score and comment for one criterion of one candidate. Serves US-00-014, US-00-015.';
COMMENT ON COLUMN feedback.candidate_id IS 'The candidate interviewed.';
COMMENT ON COLUMN feedback.interviewer_id IS 'The interviewer who scored.';
COMMENT ON COLUMN feedback.criterion_id IS 'The criterion scored.';
COMMENT ON COLUMN feedback.score IS 'The interviewer''s score on the rubric scale.';
COMMENT ON COLUMN feedback.comment IS 'The interviewer''s short comment. [personal data: free text about a candidate]';
COMMENT ON COLUMN feedback.locked IS 'True after submit; a recruiter-approved edit sets it false until the interviewer saves again.';
COMMENT ON COLUMN feedback.created_at IS 'When the row was written.';
COMMENT ON COLUMN feedback.updated_at IS 'Last change to the row, set by the repository on every UPDATE.';
-- An interviewer's own feedback and the has-submitted check that unhides model scores (AC-US-00-014-6, AC-US-00-014-7); also the foreign-key index.
CREATE INDEX idx_feedback_interviewer_id ON feedback (interviewer_id, candidate_id);
-- Foreign-key index, so deleting a criterion checks feedback without a table scan.
CREATE INDEX idx_feedback_criterion_id ON feedback (criterion_id);

-- jobs: The Postgres-backed queue (ADR-0004): one row per unit of background work, claimed by a Worker.
-- Serves US-00-001, US-00-003, US-00-006, US-00-013, US-02-001
CREATE TABLE jobs (
    id bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
    type text NOT NULL,
    status text NOT NULL DEFAULT 'queued',
    role_id uuid NOT NULL REFERENCES roles (id) ON DELETE RESTRICT,
    candidate_id uuid REFERENCES candidates (id) ON DELETE CASCADE,
    question_id uuid REFERENCES questions (id) ON DELETE CASCADE,
    criteria_version integer NOT NULL,
    attempt smallint NOT NULL DEFAULT 0,
    run_after timestamptz NOT NULL DEFAULT now(),
    deadline_at timestamptz NOT NULL DEFAULT now() + interval '30 minutes',
    lease_token uuid,
    lease_expires_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT jobs_pkey PRIMARY KEY (id),
    CONSTRAINT chk_jobs_type CHECK (type IN ('process_resume', 'propose_criteria', 'generate_kit', 'regenerate_question', 'rescore')),
    CONSTRAINT chk_jobs_status CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'stale', 'cancelled')),
    CONSTRAINT chk_jobs_attempt_range CHECK (attempt BETWEEN 0 AND 3),
    CONSTRAINT chk_jobs_lease_together CHECK ((lease_token IS NULL) = (lease_expires_at IS NULL)),
    CONSTRAINT chk_jobs_target_shape CHECK ((type IN ('process_resume', 'rescore') AND candidate_id IS NOT NULL AND question_id IS NULL) OR (type = 'regenerate_question' AND question_id IS NOT NULL AND candidate_id IS NULL) OR (type IN ('propose_criteria', 'generate_kit') AND candidate_id IS NULL AND question_id IS NULL))
);
COMMENT ON TABLE jobs IS 'The Postgres-backed queue (ADR-0004): one row per unit of background work, claimed by a Worker. Serves US-00-001, US-00-003, US-00-006, US-00-013, US-02-001.';
COMMENT ON COLUMN jobs.id IS 'Job id returned to the Web for polling.';
COMMENT ON COLUMN jobs.type IS 'process_resume, propose_criteria, generate_kit, regenerate_question or rescore.';
COMMENT ON COLUMN jobs.status IS 'queued, running, succeeded, failed (dead letter), stale or cancelled.';
COMMENT ON COLUMN jobs.role_id IS 'The role the job works for.';
COMMENT ON COLUMN jobs.candidate_id IS 'The candidate, for process_resume and rescore.';
COMMENT ON COLUMN jobs.question_id IS 'The question, for regenerate_question.';
COMMENT ON COLUMN jobs.criteria_version IS 'roles.criteria_version at enqueue time; ids and this integer are the whole payload.';
COMMENT ON COLUMN jobs.attempt IS 'Attempts started, at most 3.';
COMMENT ON COLUMN jobs.run_after IS 'Earliest time the job may be claimed; pushed out by backoff.';
COMMENT ON COLUMN jobs.deadline_at IS 'Time after which retries stop and the job fails.';
COMMENT ON COLUMN jobs.lease_token IS 'Random token of the Worker holding the job; every result write is conditional on it.';
COMMENT ON COLUMN jobs.lease_expires_at IS 'When the lease lapses and another Worker may take the job.';
COMMENT ON COLUMN jobs.last_error IS 'Short error code or message from the last failed attempt; never resume text.';
COMMENT ON COLUMN jobs.created_at IS 'When the row was written.';
COMMENT ON COLUMN jobs.updated_at IS 'Last change to the row, set by the repository on every UPDATE.';
-- The claim query: oldest due queued job, FOR UPDATE SKIP LOCKED. The claim must repeat status = 'queued'.
CREATE INDEX idx_jobs_queued_run_after ON jobs (run_after) WHERE status = 'queued';
-- Re-claim of jobs whose lease lapsed after a Worker crash. The query must repeat status = 'running'.
CREATE INDEX idx_jobs_running_lease ON jobs (lease_expires_at) WHERE status = 'running';
-- The per-role queue view (AC-US-00-003-6); also the foreign-key index.
CREATE INDEX idx_jobs_role_status ON jobs (role_id, status);
-- Foreign-key index, and the retry lookup for one candidate's jobs.
CREATE INDEX idx_jobs_candidate_id ON jobs (candidate_id);
-- Foreign-key index for the questions reference.
CREATE INDEX idx_jobs_question_id ON jobs (question_id);
-- One open job per candidate and type, so a double-clicked retry cannot enqueue two paid scoring calls.
CREATE UNIQUE INDEX uq_jobs_open_candidate ON jobs (candidate_id, type) WHERE candidate_id IS NOT NULL AND status IN ('queued', 'running');
-- One open criteria proposal or kit generation per role, for the same reason.
CREATE UNIQUE INDEX uq_jobs_open_role_task ON jobs (role_id, type) WHERE candidate_id IS NULL AND question_id IS NULL AND status IN ('queued', 'running');
-- One open regeneration per question, so a double click cannot enqueue two paid calls.
CREATE UNIQUE INDEX uq_jobs_open_question ON jobs (question_id) WHERE question_id IS NOT NULL AND status IN ('queued', 'running');

-- call_log: One row per Gateway call, live or replayed: purpose, tokens and the cost counted against the budget.
-- Serves US-02-001, US-02-002, US-02-003
CREATE TABLE call_log (
    id bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
    role_id uuid REFERENCES roles (id) ON DELETE RESTRICT,
    purpose text NOT NULL,
    status call_status NOT NULL,
    model text NOT NULL,
    request_key text NOT NULL,
    schema_retry smallint NOT NULL DEFAULT 0,
    input_tokens integer,
    output_tokens integer,
    cost_usd numeric(12,6) NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT call_log_pkey PRIMARY KEY (id),
    CONSTRAINT chk_call_log_purpose CHECK (purpose IN ('criteria', 'scoring', 'kit', 'eval')),
    CONSTRAINT chk_call_log_schema_retry_range CHECK (schema_retry IN (0, 1)),
    CONSTRAINT chk_call_log_request_key_shape CHECK (request_key ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_call_log_cost_non_negative CHECK (cost_usd >= 0),
    CONSTRAINT chk_call_log_replay_free CHECK (status NOT IN ('replayed', 'released') OR cost_usd = 0),
    CONSTRAINT chk_call_log_settled_tokens CHECK (status <> 'settled' OR (input_tokens IS NOT NULL AND output_tokens IS NOT NULL))
);
COMMENT ON TABLE call_log IS 'One row per Gateway call, live or replayed: purpose, tokens and the cost counted against the budget. Serves US-02-001, US-02-002, US-02-003.';
COMMENT ON COLUMN call_log.id IS 'Sequence number of the call.';
COMMENT ON COLUMN call_log.role_id IS 'The role the call was for; null for eval calls made outside a role.';
COMMENT ON COLUMN call_log.purpose IS 'criteria, scoring, kit or eval.';
COMMENT ON COLUMN call_log.status IS 'reserved, settled, replayed or released.';
COMMENT ON COLUMN call_log.model IS 'Model id sent, for example claude-haiku-4-5.';
COMMENT ON COLUMN call_log.request_key IS 'SHA-256 hex of request, model id, prompt version and schema-retry index; no text.';
COMMENT ON COLUMN call_log.schema_retry IS '0 for the first try, 1 for the retry after malformed output.';
COMMENT ON COLUMN call_log.input_tokens IS 'Input tokens; null until settled.';
COMMENT ON COLUMN call_log.output_tokens IS 'Output tokens; null until settled.';
COMMENT ON COLUMN call_log.cost_usd IS 'USD counted against the budget for this call: the reserved maximum, then the actual cost, 0 when replayed or released.';
COMMENT ON COLUMN call_log.created_at IS 'When the row was written.';
COMMENT ON COLUMN call_log.updated_at IS 'Last change to the row, set by the repository on every UPDATE.';
-- The cost log screen, newest first, and cost by day (AC-US-00-012-4, HLD section 11).
CREATE INDEX idx_call_log_created_at ON call_log (created_at DESC, id DESC);
-- Foreign-key index, and cost per role.
CREATE INDEX idx_call_log_role_id ON call_log (role_id);

-- budget: The single running total of model spend, held under the USD 8 cap.
-- Serves US-02-002
CREATE TABLE budget (
    id smallint NOT NULL,
    spent_usd numeric(12,6) NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT budget_pkey PRIMARY KEY (id),
    CONSTRAINT chk_budget_single_row CHECK (id = 1),
    CONSTRAINT chk_budget_spent_cap CHECK (spent_usd >= 0 AND spent_usd <= 8)
);
COMMENT ON TABLE budget IS 'The single running total of model spend, held under the USD 8 cap. Serves US-02-002.';
COMMENT ON COLUMN budget.id IS 'Always 1; a single-row table.';
COMMENT ON COLUMN budget.spent_usd IS 'USD spent or reserved so far, seeded from the committed spend ledger.';
COMMENT ON COLUMN budget.updated_at IS 'Last change to the row, set by the repository on every UPDATE.';

COMMIT;
