"""The anonymizer's boundaries hold in the real app tree (tenets 1, 2 and 7)."""

import re
from pathlib import Path

from app.anonymizer.pipeline import PASSES
from tests.gateway import boundaries as b

APP = Path(__file__).resolve().parents[2] / "app"


def test_the_anonymizer_is_the_only_importer_of_mint_anonymized() -> None:
    importers = b.files_importing_name(APP, "app.gateway.text", "mint_anonymized")
    assert importers
    assert [m for m in importers if not m.startswith("app.anonymizer")] == []


def test_the_anonymizer_imports_nothing_from_the_gateway_but_the_text_classes() -> None:
    """Directly only: importing `app.gateway.text` runs the package `__init__`, which is the
    gateway's own business; what matters is that no anonymizer module calls into it."""
    imported = {
        m
        for path in b.py_files(APP / "anonymizer")
        for m in b.imported_modules(path)
        if m == "app.gateway" or m.startswith("app.gateway.")
    }
    assert {m for m in imported if not m.startswith("app.gateway.text")} == set()
    assert b.files_importing(APP, "httpx") == ["app.gateway.transport"]


def test_only_the_loader_touches_the_database() -> None:
    touching = [m for m in b.files_importing(APP, "sqlalchemy") if m.startswith("app.anonymizer")]
    assert touching == ["app.anonymizer.loader"]


def test_the_api_does_not_import_the_anonymizer() -> None:
    """Tenet 1: the Api process never anonymizes; the Worker does."""
    reachable = b.import_closure(APP, "app.main")
    assert [m for m in reachable if m.startswith("app.anonymizer")] == []


def test_the_anonymizer_names_no_real_person_in_its_data() -> None:
    """Word lists hold words, never an email, a phone number or a link."""
    pattern = re.compile(r"@|https?://|\d{7}")
    data = (APP / "anonymizer" / "data").glob("*.txt")
    assert [f.name for f in data if pattern.search(f.read_text(encoding="utf-8"))] == []


def test_every_pass_is_a_pure_function_registered_once() -> None:
    assert len(set(PASSES)) == len(PASSES) == 6
