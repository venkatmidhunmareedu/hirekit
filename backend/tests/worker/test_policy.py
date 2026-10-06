"""`next_step`: the one decision from an error to a retry or a failure."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from app.gateway import errors as gateway_errors
from app.gateway.errors import (
    BudgetReachedError,
    GatewayError,
    RateLimitedError,
)
from app.worker import outcome
from app.worker.errors import ExtractionError, SchemaError
from app.worker.policy import BACKOFF_SECONDS, DEADLINE, next_step

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
DEADLINE_AT = NOW + DEADLINE


def all_gateway_errors() -> list[type[GatewayError]]:
    return [
        cls
        for cls in vars(gateway_errors).values()
        if isinstance(cls, type) and issubclass(cls, GatewayError) and cls is not GatewayError
    ]


def build(cls: type[GatewayError]) -> GatewayError:
    if cls is BudgetReachedError:
        return BudgetReachedError(Decimal(8), Decimal(8))
    return cls("boom")


def test_next_step_retries_a_retryable_error_with_the_first_backoff() -> None:
    step = next_step(RateLimitedError("slow"), 1, NOW, DEADLINE_AT)
    assert step == outcome.Retry(NOW + timedelta(seconds=BACKOFF_SECONDS[0]), "rate_limited")


def test_next_step_retries_again_with_the_second_backoff() -> None:
    step = next_step(RateLimitedError("slow"), 2, NOW, DEADLINE_AT)
    assert step == outcome.Retry(NOW + timedelta(seconds=BACKOFF_SECONDS[1]), "rate_limited")


def test_next_step_fails_a_retryable_error_at_the_third_attempt() -> None:
    step = next_step(RateLimitedError("slow"), 3, NOW, DEADLINE_AT)
    assert step == outcome.Failed("rate_limited", outcome.MODEL_UNAVAILABLE)


def test_next_step_fails_when_the_next_retry_would_pass_the_deadline() -> None:
    just_enough = NOW + timedelta(seconds=BACKOFF_SECONDS[0] + 1)
    assert isinstance(next_step(RateLimitedError("x"), 1, NOW, just_enough), outcome.Retry)
    at_the_deadline = NOW + timedelta(seconds=BACKOFF_SECONDS[0])
    step = next_step(RateLimitedError("x"), 1, NOW, at_the_deadline)
    assert step == outcome.Failed("rate_limited", outcome.MODEL_UNAVAILABLE)


@pytest.mark.parametrize("cls", all_gateway_errors(), ids=lambda cls: cls.__name__)
def test_next_step_maps_every_gateway_error_to_a_decision(cls: type[GatewayError]) -> None:
    step = next_step(build(cls), 1, NOW, DEADLINE_AT)
    if cls.retryable:
        assert isinstance(step, outcome.Retry)
        assert step.code == cls.code
    else:
        assert isinstance(step, outcome.Failed)
        assert step.reason in {
            outcome.BUDGET_REACHED,
            outcome.BUDGET_NOT_INITIALISED,
            outcome.RECORDING_MISSING,
            outcome.SCORING_FAILED,
            outcome.SOMETHING_WENT_WRONG,
        }


@pytest.mark.parametrize(
    ("cls", "code", "reason"),
    [
        (BudgetReachedError, "budget_reached", outcome.BUDGET_REACHED),
        (gateway_errors.ProviderCreditExhaustedError, "budget_reached", outcome.BUDGET_REACHED),
        (
            gateway_errors.BudgetNotInitialisedError,
            "budget_not_initialised",
            outcome.BUDGET_NOT_INITIALISED,
        ),
        (gateway_errors.RecordingMissingError, "recording_missing", outcome.RECORDING_MISSING),
        (gateway_errors.RecordingCorruptError, "recording_missing", outcome.RECORDING_MISSING),
        (gateway_errors.ProviderRejectedError, "provider_rejected", outcome.SCORING_FAILED),
        (
            gateway_errors.ProviderProtocolError,
            "provider_protocol_error",
            outcome.SCORING_FAILED,
        ),
        (gateway_errors.InputNotAllowedError, "input_not_allowed", outcome.SOMETHING_WENT_WRONG),
        (gateway_errors.InvalidRequestError, "invalid_request", outcome.SOMETHING_WENT_WRONG),
        (
            gateway_errors.LiveCallForbiddenError,
            "live_call_forbidden",
            outcome.SOMETHING_WENT_WRONG,
        ),
        (gateway_errors.BudgetLedgerError, "budget_ledger_error", outcome.SOMETHING_WENT_WRONG),
    ],
)
def test_a_non_retryable_gateway_error_fails_at_once_with_its_text(
    cls: type[GatewayError], code: str, reason: str
) -> None:
    assert next_step(build(cls), 1, NOW, DEADLINE_AT) == outcome.Failed(code, reason)


def test_next_step_reads_the_retryable_attribute_of_a_gateway_error() -> None:
    class NewRetryableError(GatewayError):
        code = "brand_new"
        retryable = True

    class NewFatalError(GatewayError):
        code = "brand_new_fatal"

    assert isinstance(next_step(NewRetryableError("x"), 1, NOW, DEADLINE_AT), outcome.Retry)
    assert next_step(NewFatalError("x"), 1, NOW, DEADLINE_AT) == outcome.Failed(
        "brand_new_fatal", outcome.SOMETHING_WENT_WRONG
    )


def test_an_extraction_error_fails_with_a_plain_reason_and_is_not_retried() -> None:
    step = next_step(ExtractionError("scanned"), 1, NOW, DEADLINE_AT)
    assert step == outcome.Failed("extraction_failed", outcome.EXTRACTION_FAILED)


def test_unexpected_exception_fails_the_job_and_records_only_its_class_name() -> None:
    step = next_step(ValueError("Jane Doe, 12 Elm Street"), 1, NOW, DEADLINE_AT)
    assert step == outcome.Failed("ValueError", outcome.SOMETHING_WENT_WRONG)
    assert "Jane" not in repr(step)


def test_a_schema_error_outside_a_handler_is_a_bug_and_fails() -> None:
    step = next_step(SchemaError("bad reply"), 1, NOW, DEADLINE_AT)
    assert step == outcome.Failed("SchemaError", outcome.SOMETHING_WENT_WRONG)


def test_an_integrity_error_after_a_paid_call_is_not_retried() -> None:
    error = IntegrityError("INSERT ...", {}, Exception("duplicate key"))
    step = next_step(error, 1, NOW, DEADLINE_AT)
    assert step == outcome.Failed("IntegrityError", outcome.SOMETHING_WENT_WRONG)


class _PgError(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


def test_a_database_outage_or_deadlock_is_retried() -> None:
    outage = OperationalError("SELECT 1", {}, Exception("connection refused"))
    deadlock = IntegrityError("UPDATE ...", {}, _PgError("40P01"))
    serialization = IntegrityError("UPDATE ...", {}, _PgError("40001"))
    for error in (outage, deadlock, serialization):
        step = next_step(error, 1, NOW, DEADLINE_AT)
        assert step == outcome.Retry(
            NOW + timedelta(seconds=BACKOFF_SECONDS[0]), "database_unavailable"
        )


def test_a_database_outage_fails_at_the_third_attempt() -> None:
    outage = OperationalError("SELECT 1", {}, Exception("connection refused"))
    step = next_step(outage, 3, NOW, DEADLINE_AT)
    assert step == outcome.Failed("database_unavailable", outcome.DATABASE_UNAVAILABLE)
