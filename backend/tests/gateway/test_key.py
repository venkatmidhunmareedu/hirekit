"""The replay key is stable across machines and changes with everything that changes the reply."""

import unicodedata

from app.gateway.key import input_sha256, request_key

BASE = {
    "model": "anthropic/claude-haiku-4.5",
    "prompt_version": "score-v1",
    "schema_retry": 0,
    "max_tokens": 1000,
    "system": "Score each criterion.",
    "input_text": "Built a payments service in Python.",
}


def key(**overrides: object) -> str:
    return request_key(**{**BASE, **overrides})  # type: ignore[arg-type]  # test kwargs


def test_same_inputs_give_the_same_key() -> None:
    """AC-US-02-003-1: the key is a pure function of the request."""
    assert key() == key()
    assert len(key()) == 64
    assert set(key()) <= set("0123456789abcdef")


def test_key_changes_with_prompt_version_model_and_schema_retry() -> None:
    """decisions.md conflict 2: each of these makes a different recording."""
    keys = {
        key(),
        key(prompt_version="score-v2"),
        key(model="other/model"),
        key(schema_retry=1),
        key(max_tokens=1500),
        key(system="Score again."),
        key(input_text="A different resume."),
    }
    assert len(keys) == 7


def test_crlf_and_lf_fixtures_give_the_same_key() -> None:
    """Replay on any machine: a CRLF checkout must not change the key."""
    lf = key(input_text="line one\nline two\n")
    assert key(input_text="line one\r\nline two\r\n") == lf
    assert key(input_text="line one\rline two\r") == lf


def test_unicode_forms_give_the_same_key() -> None:
    composed = unicodedata.normalize("NFC", "café")
    decomposed = unicodedata.normalize("NFD", "café")
    assert composed != decomposed
    assert key(input_text=composed) == key(input_text=decomposed)


def test_input_hash_ignores_prompt_and_model_but_not_input_or_retry() -> None:
    """The stale check matches recordings for the same input under another prompt."""
    base = input_sha256(purpose="scoring", schema_retry=0, input_text="resume")
    assert base == input_sha256(purpose="scoring", schema_retry=0, input_text="resume")
    assert base != input_sha256(purpose="scoring", schema_retry=1, input_text="resume")
    assert base != input_sha256(purpose="eval", schema_retry=0, input_text="resume")
    assert base != input_sha256(purpose="scoring", schema_retry=0, input_text="other")


def test_input_hash_normalizes_newlines_like_the_key() -> None:
    lf = input_sha256(purpose="scoring", schema_retry=0, input_text="a\nb")
    assert lf == input_sha256(purpose="scoring", schema_retry=0, input_text="a\r\nb")
