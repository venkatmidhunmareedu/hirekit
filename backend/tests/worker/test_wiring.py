"""The composition root builds all five handlers offline, and `__main__` uses it."""

import ast
from contextlib import AbstractAsyncContextManager
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.prompts.criteria_prompt import CriteriaPromptBuilder
from app.prompts.kit_prompt import KitPromptBuilder
from app.prompts.scoring_prompt import ScoringPromptBuilder
from app.worker import __main__ as entry
from app.worker.wiring import build_worker
from tests.gateway.fakes import make_settings

JOB_TYPES = {
    "process_resume",
    "rescore",
    "propose_criteria",
    "generate_kit",
    "regenerate_question",
}


def no_database() -> AbstractAsyncContextManager[AsyncSession]:
    raise AssertionError("building the Worker must not open a transaction")


async def test_build_worker_returns_the_five_handlers_in_replay_mode(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    assert settings.model_mode == "replay"
    assert settings.openrouter_api_key is None

    handlers, close = build_worker(settings, no_database)

    assert set(handlers) == JOB_TYPES
    assert all(callable(h) for h in handlers.values())
    await close()


def test_a_live_build_without_a_key_fails_in_settings_not_at_the_first_call(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError, match="OPENROUTER_API_KEY is required"):
        make_settings(tmp_path, model_mode="live")


def test_the_real_prompt_versions_are_the_ones_wired() -> None:
    assert ScoringPromptBuilder().prompt_version == "scoring-v1"
    assert CriteriaPromptBuilder().prompt_version == "criteria-v1"
    assert KitPromptBuilder().prompt_version == "kit-v1"


def test_main_builds_its_registry_through_the_wiring_and_keeps_no_empty_one() -> None:
    tree = ast.parse(Path(entry.__file__).read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "build_worker" in names
    assert not hasattr(entry, "HANDLERS")
    empty = [n for n in ast.walk(tree) if isinstance(n, ast.Dict) and not n.keys]
    assert empty == []
