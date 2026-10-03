"""The job-description loader reads `roles` and nothing else (tenet 1)."""

import re
from pathlib import Path

from tests.gateway import boundaries as b

APP = Path(__file__).resolve().parents[2] / "app"


def test_the_loader_sql_names_no_candidate_or_resume_table() -> None:
    sql = [s for m, s in b.string_literals(APP, "app.jobs") if re.search(r"\bSELECT\b", s)]
    assert sql
    assert [s for s in sql if re.search(r"resume_|candidates|scores", s)] == []


def test_the_jobs_package_imports_no_candidate_code() -> None:
    imported = {m for p in b.py_files(APP / "jobs") for m in b.imported_modules(p)}
    assert {m for m in imported if m.startswith("app.anonymizer")} == set()
