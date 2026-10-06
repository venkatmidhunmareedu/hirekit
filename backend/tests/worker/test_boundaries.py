"""The Worker's boundaries hold in the real app tree, and each detector catches a planted breach."""

import re
from pathlib import Path

from tests.gateway import boundaries as b
from tests.gateway.test_boundaries import tree

TESTS = Path(__file__).resolve().parents[1]
APP = TESTS.parent / "app"
LLD = TESTS.parents[1] / "docs" / "design" / "worker-lld.md"
MINTS = {"mint_anonymized", "mint_job_description", "mint_prompt"}
TEXT_CLASSES = {"AnonymizedText", "JobDescriptionText", "PromptText"}
STAGE = re.compile(r"\bstage\b", re.IGNORECASE)

# The real tree ---------------------------------------------------------------------------


def test_worker_never_writes_candidate_stage() -> None:
    """Tenet 4: no SQL or string in the Worker or its repositories names `stage`."""
    worker = b.string_literals(APP, "app.worker")
    writes = b.string_literals(APP, "app.db.repositories.worker_writes")
    jobs = b.string_literals(APP, "app.db.repositories.jobs")
    assert [(m, s) for m, s in worker + writes + jobs if STAGE.search(s)] == []
    assert any("processing_status" in s for _, s in writes)  # the scan really read the SQL


def test_worker_mints_no_text_classes() -> None:
    """Tenet 2: the Worker imports no `mint_*` and never builds a text class itself."""
    in_worker = [
        m
        for n in MINTS
        for m in b.files_importing_name(APP, "app.gateway.text", n)
        if m.startswith("app.worker")
    ]
    assert in_worker == []
    assert [
        c for c in b.constructor_calls(APP, TEXT_CLASSES) if c[0].startswith("app.worker")
    ] == []


def test_api_does_not_import_the_worker() -> None:
    """Tenet 1: the Api process never reaches the Worker, directly or through another module."""
    reachable = b.import_closure(APP, "app.main")
    assert "app.api.health.router" in reachable
    assert [m for m in reachable if m == "app.worker" or m.startswith("app.worker.")] == []


def test_no_worker_module_imports_the_api() -> None:
    """The Worker is its own process: it shares the database layer, never the Api."""
    assert b.files_importing(APP / "worker", "app.api") == []
    assert b.files_importing(APP / "worker", "app.main") == []


def test_the_worker_is_the_only_caller_of_the_gateway_for_scoring_criteria_and_kit() -> None:
    """Tenet 1: only the Worker builds a request, and nothing else calls `complete`."""
    requests = {m for m, _ in b.constructor_calls(APP, {"GatewayRequest"})}
    assert {m for m in requests if not m.startswith("app.gateway")} == {
        "app.worker.handlers.kit",
        "app.worker.handlers.propose_criteria",
        "app.worker.handlers.scoring",
    }
    callers = [m for m in b.files_containing(APP, ".complete(") if not m.startswith("app.gateway")]
    assert sorted(callers) == [
        "app.worker.handlers.kit",
        "app.worker.handlers.propose_criteria",
        "app.worker.handlers.scoring",
    ]


def test_every_worker_write_goes_through_a_fenced_transaction() -> None:
    """HLD section 7: a handler writes only on the session `ctx.fenced()` gave it."""
    assert b.unfenced_calls(APP, "app.worker.handlers") == []


def test_handlers_never_read_reply_fields() -> None:
    """Section 3: a reply is validated once, in the parser; handlers read only text and finish."""
    assert b.attribute_reads(APP, "app.worker.handlers", "reply") == {"text", "finish_reason"}
    assert b.files_importing(APP / "worker", "json") == []


def test_no_module_builds_an_engine_at_import_time() -> None:
    """Python rules: engines are made in a function (the lifespan, `main`), never at import."""
    assert b.module_level_calls(APP, {"create_async_engine", "make_engine"}) == []


def test_every_test_the_worker_design_names_exists() -> None:
    """Section 8: each test named in the design's table is defined somewhere under tests/."""
    named = set(re.findall(r"`(test_\w+)`", LLD.read_text(encoding="utf-8").split("## 9.")[0]))
    assert len(named) > 60
    assert sorted(named - b.defined_test_names(TESTS)) == []


# The detectors, on planted breaches -------------------------------------------------------

FENCED = (
    "async def h(ctx, deps):\n    async with ctx.fenced() as session:\n"
    "        await deps.writes.set_status(session, 1, 'done')\n"
)


def test_fence_scan_accepts_a_fenced_write_and_a_helper_taking_the_session(tmp_path: Path) -> None:
    helper = "async def end(deps, session):\n    await deps.jobs.mark_stale(session, 1)\n"
    app = tree(tmp_path, {"worker/h.py": FENCED + helper})
    assert b.unfenced_calls(app, "app.worker") == []


def test_fence_scan_finds_a_write_outside_the_fence(tmp_path: Path) -> None:
    bad = "async def h(ctx, deps, session):\n    pass\n\nasync def g(deps, s):\n"
    bad += "    await deps.writes.set_status(s, 1, 'done')\n"
    app = tree(tmp_path, {"worker/h.py": bad})
    assert b.unfenced_calls(app, "app.worker") == [("app.worker.h", 5)]


def test_fence_scan_finds_a_handler_opening_its_own_transaction(tmp_path: Path) -> None:
    source = "async def h(ctx):\n    async with ctx.sessions() as session:\n        pass\n"
    app = tree(tmp_path, {"worker/h.py": source})
    assert b.unfenced_calls(app, "app.worker") == [("app.worker.h", 2)]


def test_string_scan_skips_docstrings_and_finds_sql(tmp_path: Path) -> None:
    source = '"""Never touches stage."""\nSQL = "UPDATE candidates SET stage = 1"\n'
    app = tree(tmp_path, {"worker/w.py": source})
    assert b.string_literals(app, "app.worker") == [
        ("app.worker.w", "UPDATE candidates SET stage = 1")
    ]


def test_attribute_scan_finds_a_reply_field_read(tmp_path: Path) -> None:
    app = tree(tmp_path, {"worker/h.py": "x = reply.text\ny = reply.score\n"})
    assert b.attribute_reads(app, "app.worker", "reply") == {"text", "score"}


def test_module_level_scan_finds_an_import_time_engine_only(tmp_path: Path) -> None:
    source = "engine = make_engine(s)\n\ndef main():\n    return make_engine(s)\n"
    app = tree(tmp_path, {"db.py": source})
    assert b.module_level_calls(app, {"make_engine"}) == [("app.db", "make_engine")]
