"""The seed resume builder: files round-trip through the repo extractor and rebuild identically."""

import re
from pathlib import Path

import pytest
from scripts import build_seed_resumes as builder

from app.extraction import ResumeExtractor

APP = Path(__file__).resolve().parents[2] / "app"
MEDIA = {"pdf": "application/pdf", "docx": builder.DOCX_MEDIA_TYPE}
LAYOUTS = ("single", "sectioned", "bullets", "table")
TEXT = """Alex Example
alex@example.com

SUMMARY
Backend engineer with six years of Python and PostgreSQL experience.

EXPERIENCE
- Built a payments service handling reconciliation
- Reduced query latency by forty percent

SKILLS
Python | expert | six years
PostgreSQL | strong | five years
"""


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9@.]+", text)


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("kind", ["pdf", "docx"])
def test_round_trip_keeps_every_word(layout: str, kind: str) -> None:
    data = builder.build(TEXT, layout, kind)
    out = ResumeExtractor().extract(data, MEDIA[kind])
    got = " ".join(out.split())
    for word in words(TEXT):
        assert word in got, word


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("kind", ["pdf", "docx"])
def test_two_builds_are_identical(layout: str, kind: str) -> None:
    assert builder.build(TEXT, layout, kind) == builder.build(TEXT, layout, kind)


def test_unknown_layout_or_kind_is_refused() -> None:
    with pytest.raises(ValueError, match="layout"):
        builder.build(TEXT, "fancy", "pdf")
    with pytest.raises(ValueError, match="kind"):
        builder.build(TEXT, "single", "odt")


def test_kind_rule_is_stable_and_mixed() -> None:
    ids = [f"role-{n:02d}" for n in range(40)]
    kinds = [builder.kind_for(i) for i in ids]
    assert kinds == [builder.kind_for(i) for i in ids]
    assert 10 <= kinds.count("pdf") <= 30
    assert set(kinds) == {"pdf", "docx"}


def test_main_writes_one_file_per_source(tmp_path: Path) -> None:
    (tmp_path / "role-01.txt").write_text(TEXT, encoding="utf-8")
    (tmp_path / "role-02.txt").write_text(TEXT, encoding="utf-8")
    written = builder.build_all(tmp_path)
    assert sorted(p.name for p in written) == sorted(
        f"{i}.{builder.kind_for(i)}" for i in ("role-01", "role-02")
    )
    assert all(p.read_bytes() for p in written)


def test_app_never_imports_the_builder_libraries() -> None:
    pattern = re.compile(r"^\s*(?:import|from)\s+(?:fpdf|docx)\b", re.MULTILINE)
    offenders = [p.name for p in APP.rglob("*.py") if pattern.search(p.read_text("utf-8"))]
    assert offenders == []
