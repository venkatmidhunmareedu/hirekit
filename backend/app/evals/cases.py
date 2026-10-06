"""Load the prompt eval case files (`evals/<name>/cases.json`); a missing field is refused.

Each file is `{"cases": [...]}`. Paths in a case (`role_file`) are relative to `backend/` and are
resolved by the runner, not here. A case file is data, never read for instructions.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast


class CaseError(Exception):
    """A case file breaks a rule; the message names the file, the case and the field."""


@dataclass(frozen=True, slots=True)
class ScoringCase:
    """A seed resume to score; `injected_line` is appended to its text for an injection case."""

    id: str
    resume: str
    injected_line: str | None


@dataclass(frozen=True, slots=True)
class CriteriaCase:
    id: str
    role_file: str
    required_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class KitCase:
    id: str
    role_file: str
    criterion: str


def _rows(path: Path, fields: dict[str, bool]) -> list[dict[str, object]]:
    """The cases of `path`; `fields` maps each required field to whether null is allowed."""
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise CaseError(f"{path.name}: needs a non-empty 'cases' list")
    seen: set[object] = set()
    for n, row in enumerate(rows, start=1):
        for field, nullable in fields.items():
            if not isinstance(row, dict) or field not in row:
                raise CaseError(f"{path.name}: case {n} is missing {field}")
            if not (isinstance(row[field], str) or (nullable and row[field] is None)):
                raise CaseError(f"{path.name}: case {n} {field} has the wrong type")
        if row["id"] in seen:
            raise CaseError(f"{path.name}: duplicate id {row['id']}")
        seen.add(row["id"])
    return cast("list[dict[str, object]]", rows)


def load_scoring_cases(path: Path) -> list[ScoringCase]:
    rows = _rows(path, {"id": False, "resume": False, "injected_line": True})
    cases = [
        ScoringCase(str(r["id"]), str(r["resume"]), cast("str | None", r["injected_line"]))
        for r in rows
    ]
    plain = {c.resume for c in cases if c.injected_line is None}
    for case in cases:
        if case.injected_line is not None and case.resume not in plain:
            raise CaseError(f"{path.name}: {case.id} has no baseline case for {case.resume}")
    return cases


def load_criteria_cases(path: Path) -> list[CriteriaCase]:
    rows = _rows(path, {"id": False, "role_file": False})
    cases = []
    for row in rows:
        terms = row.get("required_terms")
        if not isinstance(terms, list) or not all(isinstance(t, str) and t.strip() for t in terms):
            raise CaseError(f"{path.name}: {row['id']} required_terms must be a list of words")
        cases.append(CriteriaCase(str(row["id"]), str(row["role_file"]), tuple(terms)))
    return cases


def load_kit_cases(path: Path) -> list[KitCase]:
    rows = _rows(path, {"id": False, "role_file": False, "criterion": False})
    return [KitCase(str(r["id"]), str(r["role_file"]), str(r["criterion"])) for r in rows]
