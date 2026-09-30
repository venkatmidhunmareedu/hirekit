"""The three text classes cannot be built by accident and never print their content."""

import pytest

from app.gateway.text import (
    AnonymizedText,
    JobDescriptionText,
    PromptText,
    mint_anonymized,
    mint_job_description,
    mint_prompt,
)


@pytest.mark.parametrize("cls", [AnonymizedText, JobDescriptionText, PromptText])
def test_text_classes_cannot_be_built_without_the_mint_sentinel(cls: type) -> None:
    """AC-US-00-005-3, tenet 2: a caller cannot wrap raw text directly."""
    with pytest.raises(TypeError, match="mint_"):
        cls("raw resume text", object())


def test_mint_functions_build_the_right_class() -> None:
    assert isinstance(mint_anonymized("a"), AnonymizedText)
    assert isinstance(mint_job_description("b"), JobDescriptionText)
    assert isinstance(mint_prompt("c"), PromptText)
    assert mint_anonymized("a").value == "a"


def test_classes_are_distinct_so_isinstance_can_tell_them_apart() -> None:
    assert not isinstance(mint_job_description("x"), AnonymizedText)
    assert not isinstance(mint_anonymized("x"), JobDescriptionText)
    assert not isinstance(mint_prompt("x"), AnonymizedText)


def test_text_is_immutable() -> None:
    text = mint_anonymized("original")
    with pytest.raises(AttributeError, match="immutable"):
        text.value = "changed"
    assert text.value == "original"


def test_repr_and_str_do_not_show_the_text() -> None:
    """Tenet 7: an accidental log line must not carry resume text."""
    text = mint_anonymized("Jane Doe, 12 High Street")
    assert "Jane" not in repr(text)
    assert "Jane" not in str(text)
    assert "24 chars" in repr(text)
