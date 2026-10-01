"""The gateway boundaries hold in the real app tree, and each detector catches a planted breach."""

from pathlib import Path

from tests.gateway import boundaries as b

TESTS = Path(__file__).resolve().parents[1]
APP = TESTS.parent / "app"


def tree(root: Path, files: dict[str, str]) -> Path:
    """Write a small `app` package under `root` and return its path."""
    app = root / "app"
    for relative, source in {"__init__.py": "", **files}.items():
        path = app / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return app


# The real tree ---------------------------------------------------------------------------


def test_gateway_is_the_only_provider_caller() -> None:
    """AC-US-02-001-1: no code outside app/gateway/ contacts the provider."""
    outside = [
        m for m in b.files_containing(APP, "openrouter.ai") if not m.startswith("app.gateway")
    ]
    assert outside == []
    assert b.files_containing(APP, "openrouter.ai") == ["app.gateway.transport"]


def test_only_transport_imports_httpx() -> None:
    """AC-US-02-001-1: one module owns the HTTP client."""
    assert b.files_importing(APP, "httpx") == ["app.gateway.transport"]


def test_api_package_does_not_import_gateway() -> None:
    """Tenet 1: the Api process never imports the gateway, directly or through another module."""
    reachable = b.import_closure(APP, "app.main")
    assert "app.api.health.router" in reachable  # the scan really walked the Api
    assert [m for m in reachable if m == "app.gateway" or m.startswith("app.gateway.")] == []


def test_the_api_can_use_the_budget_policy_without_the_gateway() -> None:
    """The Api needs `model_actions_allowed`, which therefore lives outside app.gateway."""
    closure = b.import_closure(APP, "app.budget.policy")
    assert not any(m.startswith("app.gateway") for m in closure)


def test_each_mint_function_has_one_importer() -> None:
    """Tenet 2: only the producer of each text class may build it."""
    allowed = {
        "mint_anonymized": "app.anonymizer",
        "mint_job_description": "app.jobs.job_description",
        "mint_prompt": "app.prompts",
    }
    for name, producer in allowed.items():
        importers = b.files_importing_name(APP, "app.gateway.text", name)
        assert [m for m in importers if not m.startswith(producer)] == [], name


def test_text_classes_are_built_only_inside_their_own_module() -> None:
    """Tenet 2: no direct AnonymizedText(...) elsewhere; `_MINT` never leaves text.py."""
    classes = {"AnonymizedText", "JobDescriptionText", "PromptText"}
    outside = [(m, c) for m, c in b.constructor_calls(APP, classes) if m != "app.gateway.text"]
    assert outside == []
    assert b.files_importing_name(APP, "app.gateway.text", "_MINT") == []


def test_gateway_test_files_cover_cutoff_cap_logging_replay_and_refusal() -> None:
    """AC-US-02-004-3: the gateway suite proves the cutoff, the cap, logging, replay and refusal."""
    required = {
        "cutoff": [
            "test_call_refused_before_transport_when_reserve_would_pass_the_limit",
            "test_concurrent_reservations_never_pass_the_limit",
        ],
        "cap": [
            "test_max_tokens_above_cap_is_clamped_to_1500",
            "test_request_sent_never_exceeds_1500_tokens",
        ],
        "logging": ["test_completed_call_logs_tokens_cost_purpose_role_through_ledger"],
        "replay": [
            "test_replay_returns_recording_with_no_network_call",
            "test_missing_recording_never_falls_back_to_a_live_call",
        ],
        "refusal": [
            "test_raw_text_passed_as_string_is_refused",
            "test_raw_text_wrapped_in_job_description_class_is_refused_for_scoring",
        ],
    }
    present = b.defined_test_names(TESTS)
    missing = {area: [n for n in names if n not in present] for area, names in required.items()}
    assert {area: names for area, names in missing.items() if names} == {}


# The detectors, on planted breaches -------------------------------------------------------


def test_provider_scan_finds_the_url_outside_the_gateway(tmp_path: Path) -> None:
    app = tree(tmp_path, {"api/leak.py": 'URL = "https://openrouter.ai/api/v1"\n'})
    assert b.files_containing(app, "openrouter.ai") == ["app.api.leak"]


def test_httpx_scan_finds_a_second_importer(tmp_path: Path) -> None:
    app = tree(
        tmp_path,
        {
            "gateway/transport.py": "import httpx\n",
            "api/client.py": "from httpx import AsyncClient\n",
        },
    )
    assert b.files_importing(app, "httpx") == ["app.api.client", "app.gateway.transport"]


def test_closure_finds_a_gateway_import_hidden_behind_another_module(tmp_path: Path) -> None:
    app = tree(
        tmp_path,
        {
            "main.py": "from app.api import router\n",
            "api/__init__.py": "",
            "api/router.py": "from app.domain import service\n",
            "domain/__init__.py": "",
            "domain/service.py": "from app.gateway.service import Gateway\n",
            "gateway/__init__.py": "",
            "gateway/service.py": "class Gateway: ...\n",
        },
    )
    closure = b.import_closure(app, "app.main")
    assert "app.gateway.service" in closure
    assert "app.gateway" in closure


def test_closure_of_a_clean_tree_has_no_gateway(tmp_path: Path) -> None:
    app = tree(
        tmp_path,
        {
            "main.py": "from app.api import router\n",
            "api/__init__.py": "",
            "api/router.py": "import json\n",
            "gateway/__init__.py": "",
        },
    )
    assert "app.gateway" not in b.import_closure(app, "app.main")


def test_mint_scan_finds_a_wrong_importer(tmp_path: Path) -> None:
    app = tree(
        tmp_path,
        {
            "anonymizer/x.py": "from app.gateway.text import mint_anonymized\n",
            "api/bad.py": "from app.gateway.text import mint_anonymized, _MINT\n",
        },
    )
    assert b.files_importing_name(app, "app.gateway.text", "mint_anonymized") == [
        "app.anonymizer.x",
        "app.api.bad",
    ]
    assert b.files_importing_name(app, "app.gateway.text", "_MINT") == ["app.api.bad"]


def test_constructor_scan_finds_a_direct_build(tmp_path: Path) -> None:
    app = tree(tmp_path, {"api/bad.py": "x = AnonymizedText('raw resume', None)\n"})
    assert b.constructor_calls(app, {"AnonymizedText"}) == [("app.api.bad", "AnonymizedText")]


def test_a_comment_or_string_mentioning_an_import_is_not_an_import(tmp_path: Path) -> None:
    app = tree(tmp_path, {"api/ok.py": '# import httpx\nNAME = "from app.gateway import x"\n'})
    assert b.files_importing(app, "httpx") == []
    assert b.files_importing(app, "app.gateway") == []
