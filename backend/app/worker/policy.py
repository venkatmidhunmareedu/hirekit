"""The retry decision. Pure: no database, no clock, no network.

`next_step` is the one place a failed attempt becomes a `Retry` or a `Failed`. A
`GatewayError` is judged by its own `retryable` attribute, so a new gateway error cannot
fall through unmapped.
"""

from datetime import datetime, timedelta
from typing import Final

from sqlalchemy.exc import InterfaceError, OperationalError

from app.gateway.errors import (
    BudgetNotInitialisedError,
    BudgetReachedError,
    GatewayError,
    ProviderCreditExhaustedError,
    ProviderProtocolError,
    ProviderRejectedError,
    RecordingCorruptError,
    RecordingMissingError,
)
from app.worker.errors import ExtractionError
from app.worker.outcome import (
    BUDGET_NOT_INITIALISED,
    BUDGET_REACHED,
    DATABASE_UNAVAILABLE,
    EXTRACTION_FAILED,
    MODEL_UNAVAILABLE,
    RECORDING_MISSING,
    SCORING_FAILED,
    SOMETHING_WENT_WRONG,
    Failed,
    Retry,
)

MAX_ATTEMPTS: Final = 3
# Three attempts mean only the first two are ever used (LLD section 10).
BACKOFF_SECONDS: Final = (30, 120, 480)
LEASE_SECONDS: Final = 180
DEADLINE: Final = timedelta(minutes=30)

DATABASE_UNAVAILABLE_CODE: Final = "database_unavailable"
_RETRYABLE_SQLSTATES: Final = frozenset({"40P01", "40001"})  # deadlock, serialization failure

# Non-retryable gateway errors with their own code and text. Any other one fails with its
# own code and the generic text.
_GATEWAY_FAILURES: Final[dict[type[GatewayError], tuple[str, str]]] = {
    BudgetReachedError: ("budget_reached", BUDGET_REACHED),
    ProviderCreditExhaustedError: ("budget_reached", BUDGET_REACHED),
    BudgetNotInitialisedError: ("budget_not_initialised", BUDGET_NOT_INITIALISED),
    RecordingMissingError: ("recording_missing", RECORDING_MISSING),
    RecordingCorruptError: ("recording_missing", RECORDING_MISSING),
    ProviderRejectedError: ("provider_rejected", SCORING_FAILED),
    ProviderProtocolError: ("provider_protocol_error", SCORING_FAILED),
}


def _is_transient_database_error(error: Exception) -> bool:
    if isinstance(error, OperationalError | InterfaceError):
        return True
    orig = getattr(error, "orig", None)
    return getattr(orig, "sqlstate", None) in _RETRYABLE_SQLSTATES


def _retry_or_fail(
    code: str, reason: str, attempt: int, now: datetime, deadline: datetime
) -> Retry | Failed:
    """Retry at the backoff for this attempt while attempts and the deadline allow."""
    if attempt < MAX_ATTEMPTS:
        run_after = now + timedelta(seconds=BACKOFF_SECONDS[attempt - 1])
        if run_after < deadline:
            return Retry(run_after, code)
    return Failed(code, reason)


def next_step(error: Exception, attempt: int, now: datetime, deadline: datetime) -> Retry | Failed:
    """Decide what happens to a job whose attempt raised `error`.

    `attempt` is the value after the claim (1 to 3). Never reads the error's message: a
    message can carry text (tenet 7), so an unexpected exception is recorded by class name.
    """
    if isinstance(error, GatewayError):
        if error.retryable:
            return _retry_or_fail(error.code, MODEL_UNAVAILABLE, attempt, now, deadline)
        code, reason = _GATEWAY_FAILURES.get(type(error), (error.code, SOMETHING_WENT_WRONG))
        return Failed(code, reason)
    if isinstance(error, ExtractionError):
        return Failed(error.code, EXTRACTION_FAILED)
    if _is_transient_database_error(error):
        return _retry_or_fail(
            DATABASE_UNAVAILABLE_CODE, DATABASE_UNAVAILABLE, attempt, now, deadline
        )
    return Failed(type(error).__name__, SOMETHING_WENT_WRONG)
