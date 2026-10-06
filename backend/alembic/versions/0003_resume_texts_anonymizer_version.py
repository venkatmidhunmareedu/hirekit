"""resume texts anonymizer version

Migration: resume_texts_anonymizer_version        Task: HK-26
Store: postgres      Phase: expand (1 of 1)
Purpose: store which anonymizer version produced each stored text, so text from before an
  anonymizer fix can be told from new text (docs/design/anonymizer-lld.md work item 10).
Locks: Up: ACCESS EXCLUSIVE on resume_texts for the catalog change only; a constant default
  is metadata only on PG11+, so no rewrite and no scan whatever the row count. Down: the same
  brief lock (DROP COLUMN marks the column dropped, it does not rewrite).
Rows: every existing row reads 1, the version in force when it was written.
Index: none: nothing queries by this column yet.
Retention / PII: none created; the column holds a small integer.
Down: drops the column; Down loses: the recorded version of every row (all become
  indistinguishable again). Run it after the code that writes the column is rolled back.

Order: apply before the Worker release that writes the column. The previous release keeps
working on the new schema: its insert omits the column and gets the default 1. The Worker's
table-level INSERT and the Api's SELECT on resume_texts (migration 0002) already cover it.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the column with a constant default and describe it."""
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("ALTER TABLE resume_texts ADD COLUMN anonymizer_version smallint NOT NULL DEFAULT 1")
    op.execute(
        "COMMENT ON COLUMN resume_texts.anonymizer_version IS "
        "'Which anonymizer version produced the text, so text from before a fix can be told "
        "from new text.'"
    )


def downgrade() -> None:
    """Drop the column."""
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("ALTER TABLE resume_texts DROP COLUMN anonymizer_version")
