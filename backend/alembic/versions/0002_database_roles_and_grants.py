"""database roles and grants

Migration: database_roles_and_grants        Task: HK-15
Store: postgres      Phase: expand (1 of 1)
Purpose: create hirekit_api and hirekit_worker and grant each only what its process needs, so
  the database itself refuses a forged score (tenet 3), a stage written by the Worker (tenet 4),
  a spend by the Api (tenet 8) and any edit of the audit history.
Locks: Up: a brief lock on each table while its grants change, none for reads or writes in
  flight; Down: the same. Empty database at first release.
Rows: none touched.
Index: none: no new query shape.
Retention / PII: none created. A role holds no data.
Down: revokes everything (DROP OWNED BY) and drops both roles; Down loses: nothing but the two
  roles and their passwords. It fails if either role still owns or has privileges in ANOTHER
  database of the same cluster (roles are cluster-wide), so run it only where these two roles
  are used by this database alone.

Passwords come from the environment when the migration runs (HIREKIT_API_PASSWORD and
HIREKIT_WORKER_PASSWORD), never from the repository. A role with no password given is created
NOLOGIN, so no default password can exist. Grants are per table and per column; a table added
by a later migration must add its own grants. The roles are named in docs/design/api-lld.md
section 5 and docs/design/worker-lld.md section 5.
"""

import os
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

API = "hirekit_api"
WORKER = "hirekit_worker"

# role -> list of (table, privileges, columns or None). `columns` limits UPDATE only.
GRANTS: dict[str, list[tuple[str, str, tuple[str, ...] | None]]] = {
    API: [
        ("users", "SELECT", None),
        ("sessions", "SELECT, INSERT, DELETE", None),
        ("roles", "SELECT, INSERT", None),
        (
            "roles",
            "UPDATE",
            ("title", "job_description", "status", "criteria_version", "updated_at"),
        ),
        ("criteria", "SELECT, INSERT", None),
        ("criteria", "UPDATE", ("name", "kind", "weight", "position", "retired_at", "updated_at")),
        ("rubric_levels", "SELECT, INSERT, DELETE", None),
        ("rubric_levels", "UPDATE", ("descriptor", "updated_at")),
        ("candidates", "SELECT, INSERT", None),
        (
            "candidates",
            "UPDATE",
            ("stage", "processing_status", "failure_reason", "updated_at"),
        ),
        ("resume_files", "SELECT, INSERT", None),
        ("resume_raw_texts", "SELECT", None),
        ("resume_texts", "SELECT", None),
        ("scores", "SELECT", None),
        ("scores", "UPDATE", ("override_score", "override_note", "overridden_by", "updated_at")),
        ("assignments", "SELECT, INSERT, DELETE", None),
        ("audit_events", "SELECT, INSERT", None),
        ("interview_kits", "SELECT", None),
        ("questions", "SELECT, DELETE", None),
        (
            "questions",
            "UPDATE",
            ("question_text", "strong_answer", "weak_answer", "position", "updated_at"),
        ),
        ("feedback", "SELECT, INSERT", None),
        ("feedback", "UPDATE", ("score", "comment", "locked", "updated_at")),
        ("jobs", "SELECT, INSERT", None),
        ("jobs", "UPDATE", ("status", "lease_token", "lease_expires_at", "updated_at")),
        ("budget", "SELECT", None),
        ("call_log", "SELECT", None),
    ],
    WORKER: [
        ("roles", "SELECT", None),
        ("roles", "UPDATE", ("criteria_version", "updated_at")),
        ("criteria", "SELECT, INSERT", None),
        ("rubric_levels", "SELECT, INSERT", None),
        ("candidates", "SELECT", None),
        (
            "candidates",
            "UPDATE",
            ("processing_status", "failure_reason", "identity_name", "updated_at"),
        ),
        ("resume_files", "SELECT, DELETE", None),
        ("resume_raw_texts", "SELECT, INSERT", None),
        ("resume_texts", "SELECT, INSERT", None),
        ("scores", "SELECT, INSERT", None),
        (
            "scores",
            "UPDATE",
            ("status", "model_score", "quote", "flag_reason", "updated_at"),
        ),
        ("interview_kits", "SELECT, INSERT", None),
        ("interview_kits", "UPDATE", ("criteria_version", "updated_at")),
        ("questions", "SELECT, INSERT, DELETE", None),
        (
            "questions",
            "UPDATE",
            ("question_text", "strong_answer", "weak_answer", "updated_at"),
        ),
        ("jobs", "SELECT", None),
        (
            "jobs",
            "UPDATE",
            (
                "status",
                "attempt",
                "run_after",
                "lease_token",
                "lease_expires_at",
                "last_error",
                "updated_at",
            ),
        ),
        ("budget", "SELECT, INSERT, UPDATE", None),
        ("call_log", "SELECT, INSERT, UPDATE", None),
    ],
}


def grant_statements(role: str) -> list[str]:
    """One GRANT per entry; `UPDATE` with columns becomes a column-level grant."""
    statements = []
    for table, privileges, columns in GRANTS[role]:
        if columns:
            statements.append(f"GRANT {privileges} ({', '.join(columns)}) ON {table} TO {role}")
        else:
            statements.append(f"GRANT {privileges} ON {table} TO {role}")
    return statements


def run(sql: str) -> None:
    """Send one statement straight to the driver, so a colon in a password is not a bind marker."""
    op.get_bind().exec_driver_sql(sql)


def create_role(role: str, env_name: str) -> None:
    """Create the role if missing; give it a login password only if the environment has one."""
    run(
        f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN "
        f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE; END IF; END $$"
    )
    password = os.environ.get(env_name)
    if password:
        run(f"ALTER ROLE {role} LOGIN PASSWORD {_literal(password)}")


def _literal(value: str) -> str:
    """A SQL string literal (single quotes doubled), used only for the migration-time password."""
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    """Create both roles and apply their grants."""
    create_role(API, "HIREKIT_API_PASSWORD")
    create_role(WORKER, "HIREKIT_WORKER_PASSWORD")
    for role in (API, WORKER):
        for statement in grant_statements(role):
            run(statement)


def downgrade() -> None:
    """Revoke everything and drop both roles."""
    for role in (WORKER, API):
        run(
            f"DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN "
            f"EXECUTE 'DROP OWNED BY {role}'; EXECUTE 'DROP ROLE {role}'; END IF; END $$"
        )
