"""Each error says whether the Worker may reschedule; the budget error carries the numbers."""

from decimal import Decimal

import pytest

from app.gateway import errors

RETRYABLE = [
    errors.LedgerUnavailableError,
    errors.RateLimitedError,
    errors.ProviderUnavailableError,
    errors.ProviderTimeoutError,
]
FATAL = [
    errors.InvalidRequestError,
    errors.InputNotAllowedError,
    errors.LiveCallForbiddenError,
    errors.ProviderCreditExhaustedError,
    errors.BudgetNotInitialisedError,
    errors.BudgetLedgerError,
    errors.RecordingCorruptError,
    errors.ProviderRejectedError,
    errors.ProviderProtocolError,
]


@pytest.mark.parametrize("cls", RETRYABLE)
def test_transient_errors_are_retryable(cls: type[errors.GatewayError]) -> None:
    assert cls("x").retryable is True


@pytest.mark.parametrize("cls", FATAL)
def test_permanent_errors_are_not_retryable(cls: type[errors.GatewayError]) -> None:
    assert cls("x").retryable is False


def test_every_error_has_a_unique_code() -> None:
    classes: list[type[errors.GatewayError]] = [
        *RETRYABLE,
        *FATAL,
        errors.BudgetReachedError,
        errors.RecordingMissingError,
    ]
    codes = [c.code for c in classes]
    assert len(codes) == len(set(codes))


def test_budget_reached_carries_total_and_limit() -> None:
    """AC-US-02-002-3, AC-US-02-002-4: the message is the text the UI shows."""
    err = errors.BudgetReachedError(Decimal("7.995"), Decimal(8))
    assert err.spent == Decimal("7.995")
    assert err.limit == Decimal(8)
    assert err.message == (
        "The model budget of $8.00 has been reached. No new model calls can be made."
    )
    assert err.retryable is False


def test_missing_recording_names_the_key() -> None:
    """AC-US-02-003-2."""
    err = errors.RecordingMissingError("abc123")
    assert "abc123" in err.message
    assert err.stale is False


def test_missing_recording_with_same_input_is_reported_as_stale() -> None:
    """AC-US-02-003-3: the failure says a recording exists under a different prompt."""
    err = errors.RecordingMissingError("new", found_key="old")
    assert err.stale is True
    assert "old" in err.message
    assert "different prompt" in err.message
