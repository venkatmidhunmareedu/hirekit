"""SQLAlchemy models. Every module with models must be imported by alembic/env.py.

The schema is written in SQL (alembic/versions/0001_initial_schema.sql, from
docs/design/schema.sql). A model is added here only for a table the code reads or
writes, with its work item (the gateway adds `Budget` and `CallLog`). Migrations for
this schema are written by hand; autogenerate would propose dropping every unmapped table.
"""
