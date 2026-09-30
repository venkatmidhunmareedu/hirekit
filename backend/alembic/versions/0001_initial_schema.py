"""initial schema

Migration: initial_schema        Task: HK-4
Store: postgres      Phase: expand (1 of 1)
Purpose: create every HireKit table, enum type, index, check and the audit trigger
  from docs/design/schema.sql.
Locks: Up: none beyond DDL on an empty database; Down: ACCESS EXCLUSIVE on each table
  while it is dropped, empty database only.
Rows: none, a new database (docs/design/data-model.md section 9).
Index: 25 indexes, each with the query it serves in docs/design/data-model.md
  section 4; none is built on existing rows.
Retention / PII: 13 personal-data columns, retention UNDEFINED (data-model.md
  section 6); no purge job is created here.
Down: drops the audit trigger and function, every table in reverse foreign-key
  order, then the seven enum types.
  Down loses: EVERY ROW IN EVERY TABLE, so it is run only on a local or throwaway
  database; tested in `make migrate-verify` and tests/integration/test_schema.py.

The SQL is 0001_initial_schema.sql, a byte-for-byte copy of docs/design/schema.sql
that tests/test_migration_sql.py keeps identical until the first release. After the
first release this file is history: every change is a new revision, never an edit here.
"""

import re
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SQL_FILE = Path(__file__).with_suffix(".sql")


def statements(sql: str) -> list[str]:
    """Split the file into statements, keeping `$$` function bodies whole and dropping BEGIN/COMMIT.

    Alembic already wraps the revision in a transaction, and asyncpg runs one statement at a time.
    """
    out: list[str] = []
    current: list[str] = []
    in_body = False
    for line in sql.splitlines():
        if not in_body and not current and (not line.strip() or line.lstrip().startswith("--")):
            continue
        current.append(line)
        if line.count("$$") % 2 == 1:
            in_body = not in_body
        if not in_body and line.rstrip().endswith(";"):
            statement = "\n".join(current).strip()
            current = []
            if statement.upper() not in ("BEGIN;", "COMMIT;"):
                out.append(statement)
    return out


def created(sql: str, kind: str) -> list[str]:
    """Names of the objects of `kind` (TABLE or TYPE) the file creates, in creation order."""
    return re.findall(rf"^CREATE {kind} (\w+)", sql, flags=re.MULTILINE)


def upgrade() -> None:
    """Create the whole schema."""
    bind = op.get_bind()
    for statement in statements(SQL_FILE.read_text(encoding="utf-8")):
        bind.exec_driver_sql(statement)


def downgrade() -> None:
    """Drop everything Up created, newest first."""
    sql = SQL_FILE.read_text(encoding="utf-8")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS audit_events_refuse_update()")
    for table in reversed(created(sql, "TABLE")):
        op.execute(f"DROP TABLE IF EXISTS {table}")
    for enum in reversed(created(sql, "TYPE")):
        op.execute(f"DROP TYPE IF EXISTS {enum}")
