"""The initial migration's SQL matches the design file and splits into whole statements."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]
VERSIONS = REPO / "backend" / "alembic" / "versions"
DESIGN = REPO / "docs" / "design" / "schema.sql"


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("m0001", VERSIONS / "0001_initial_schema.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_sql_is_a_copy_of_the_design_schema() -> None:
    """The two must not drift before the first release; delete this test then."""
    assert (VERSIONS / "0001_initial_schema.sql").read_text() == DESIGN.read_text()


def test_statements_drop_begin_and_commit_and_keep_the_trigger_function_whole() -> None:
    module = load_migration()
    statements = module.statements(DESIGN.read_text())

    assert all(s.upper() not in ("BEGIN;", "COMMIT;") for s in statements)
    assert sum(s.startswith("CREATE TABLE") for s in statements) == 18
    assert sum(s.startswith("CREATE TYPE") for s in statements) == 7
    function = next(s for s in statements if s.startswith("CREATE FUNCTION"))
    assert function.count("$$") == 2
    assert "RAISE EXCEPTION" in function
    assert all(s.rstrip().endswith(";") for s in statements)


def test_every_statement_starts_with_a_ddl_keyword() -> None:
    """A statement cut in half would leave a fragment that starts with something else."""
    module = load_migration()
    starts = {s.split()[0] + " " + s.split()[1] for s in module.statements(DESIGN.read_text())}
    assert starts <= {
        "CREATE TYPE",
        "CREATE TABLE",
        "COMMENT ON",
        "CREATE INDEX",
        "CREATE UNIQUE",
        "CREATE FUNCTION",
        "CREATE TRIGGER",
    }


def test_created_names_come_back_in_creation_order() -> None:
    module = load_migration()
    tables = module.created(DESIGN.read_text(), "TABLE")

    assert tables[0] == "users"
    assert tables[-1] == "budget"
    assert tables.index("candidates") < tables.index("scores")
    assert tables.index("questions") < tables.index("jobs")


@pytest.mark.parametrize("bad", ["", "-- only a comment\n"])
def test_empty_or_comment_only_input_gives_no_statements(bad: str) -> None:
    assert load_migration().statements(bad) == []
