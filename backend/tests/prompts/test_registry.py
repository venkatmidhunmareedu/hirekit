import json
from pathlib import Path

import pytest

from app.gateway.text import PromptText
from app.prompts import PromptRegistryError, load_prompt, render
from app.prompts.registry import PROMPTS_DIR

ROOT = Path(__file__).parent / "fixtures"
GOOD = {"topic": "cats", "tone": "plain", "count": 3}


def test_highest_active_wins_and_version_is_derived() -> None:
    prompt = load_prompt("echo", root=ROOT)
    assert prompt.prompt_version == "echo-v2"
    assert (prompt.model, prompt.effort, prompt.max_tokens) == ("claude-sonnet-5-5", "medium", 500)


def test_draft_needs_an_explicit_version_and_retired_is_not_default() -> None:
    assert load_prompt("echo", 3, root=ROOT).status == "draft"
    assert load_prompt("echo", root=ROOT).version == 2  # v3 draft and v1 retired are skipped


def test_unknown_version_and_no_active_version_raise() -> None:
    with pytest.raises(PromptRegistryError):
        load_prompt("echo", 9, root=ROOT)
    with pytest.raises(PromptRegistryError):
        load_prompt("absent", root=ROOT)


def test_golden_render_is_a_prompt_text() -> None:
    text = render(load_prompt("echo", root=ROOT), GOOD)
    assert isinstance(text, PromptText)
    assert text.value == 'Write 3 lines about cats in a plain tone. Schema: {"lines": []}\n'


def test_optional_variable_renders_empty_when_omitted() -> None:
    text = render(load_prompt("echo", root=ROOT), {"topic": "cats", "tone": "formal"})
    assert text.value.startswith("Write  lines about cats")


def test_substitution_is_single_pass() -> None:
    text = render(load_prompt("echo", root=ROOT), {**GOOD, "topic": "{{tone}}"})
    assert "about {{tone}} in a plain" in text.value


@pytest.mark.parametrize(
    "bad",
    [
        {"tone": "plain"},  # missing required
        {**GOOD, "extra": "x"},  # unknown
        {**GOOD, "topic": "x" * 41},  # oversized
        {**GOOD, "tone": "shouty"},  # not in enum
        {**GOOD, "count": "3"},  # wrong type
        {**GOOD, "count": True},  # bool is not int
    ],
)
def test_bad_variables_raise(bad: dict[str, object]) -> None:
    with pytest.raises(PromptRegistryError):
        render(load_prompt("echo", root=ROOT), bad)


@pytest.mark.parametrize("field", ["topic", "tone", "count", "extra"])
def test_error_messages_never_carry_the_value(field: str) -> None:
    secret = "SECRET-RESUME-TEXT" * 5
    with pytest.raises(PromptRegistryError) as err:
        render(load_prompt("echo", root=ROOT), {**GOOD, field: secret})
    assert "SECRET-RESUME-TEXT" not in str(err.value)


def test_every_real_prompt_renders_with_its_fixtures() -> None:
    """Zero prompts today; HK-42 onward add them. Each needs fixtures.json of named cases."""

    names = [p.name for p in PROMPTS_DIR.iterdir() if p.is_dir() and p.name != "__pycache__"]
    for name in names:
        cases = json.loads((PROMPTS_DIR / name / "fixtures.json").read_text(encoding="utf-8"))
        for version in sorted(int(p.stem[1:]) for p in (PROMPTS_DIR / name).glob("v*.md")):
            prompt = load_prompt(name, version)
            for case in cases.values():
                assert "{{" not in render(prompt, case).value
