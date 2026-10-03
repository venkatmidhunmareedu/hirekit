"""The outcome types and the failure texts."""

import re
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from app.worker import outcome
from app.worker.outcome import Failed, Retry, Stale, Succeeded

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-", re.IGNORECASE)


def failure_texts() -> list[str]:
    return [
        value for name, value in vars(outcome).items() if name.isupper() and isinstance(value, str)
    ]


def test_failure_texts_carry_no_ids_or_resume_text() -> None:
    texts = failure_texts()
    assert len(texts) == 8
    for text in texts:
        assert text.endswith(".")
        assert not UUID.search(text)
        assert not any(mark in text for mark in "{}_<>")
        assert "Traceback" not in text


def test_the_budget_text_names_the_limit() -> None:
    assert "$8.00" in outcome.BUDGET_REACHED


def test_outcomes_are_immutable_values() -> None:
    retry = Retry(datetime(2026, 1, 1, tzinfo=UTC), "rate_limited")
    assert retry == Retry(datetime(2026, 1, 1, tzinfo=UTC), "rate_limited")
    assert Succeeded() == Succeeded()
    assert Stale() == Stale()
    with pytest.raises(FrozenInstanceError):
        Failed("x", "y").code = "z"  # type: ignore[misc]  # proves the dataclass is frozen
