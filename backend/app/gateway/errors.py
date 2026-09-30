"""Gateway errors. Each says whether the Worker may reschedule the job (`retryable`).

The Api never calls the gateway (tenet 1), so these are mapped by the Worker, not
to an HTTP status; `status_code` only satisfies the `DomainError` base.
"""

from decimal import Decimal

from app.core.errors import DomainError


class GatewayError(DomainError):
    """Base class for every error the gateway raises."""

    status_code = 500
    code = "gateway_error"
    retryable: bool = False
    # True when the call may have been billed, so the reservation stays (over-counted, never
    # under-counted, HLD section 7). False means the provider reported no usage: release it.
    billed: bool = False


class InvalidRequestError(GatewayError):
    """A `GatewayRequest` field is out of range: a programming error."""

    code = "invalid_request"


class InputNotAllowedError(GatewayError):
    """The input or system text is not the class the purpose requires."""

    code = "input_not_allowed"


class LiveCallForbiddenError(GatewayError):
    """A live call was attempted where live calls are not allowed (CI)."""

    code = "live_call_forbidden"


class BudgetReachedError(GatewayError):
    """The reservation would pass the spend limit; no call was made."""

    code = "budget_reached"

    def __init__(self, spent: Decimal, limit: Decimal) -> None:
        super().__init__(
            f"The model budget of ${limit:.2f} has been reached. No new model calls can be made.",
            details={"spent": f"{spent:f}", "limit": f"{limit:f}"},
        )
        self.spent = spent
        self.limit = limit


class ProviderCreditExhaustedError(GatewayError):
    """The provider refused for credit (402); treated like a reached budget."""

    code = "provider_credit_exhausted"


class BudgetNotInitialisedError(GatewayError):
    """The budget row does not exist; live mode was not started through the ledger."""

    code = "budget_not_initialised"


class BudgetLedgerError(GatewayError):
    """The committed spend ledger is missing or unreadable."""

    code = "budget_ledger_error"


class LedgerUnavailableError(GatewayError):
    """The database could not be reached to log or reserve; nothing was spent."""

    code = "ledger_unavailable"
    retryable = True


class RecordingMissingError(GatewayError):
    """Replay mode found no recording for the request key."""

    code = "recording_missing"

    def __init__(self, key: str, found_key: str | None = None) -> None:
        if found_key is None:
            message = f"no recording for {key}"
        else:
            message = (
                f"no recording for {key}; a recording exists for the same input under a "
                f"different prompt, model or criteria ({found_key}); re-record"
            )
        super().__init__(message, details={"request_key": key, "found_key": found_key})
        self.key = key
        self.stale = found_key is not None
        self.found_key = found_key


class RecordingCorruptError(GatewayError):
    """A recording file cannot be read or does not match its own key."""

    code = "recording_corrupt"


class RateLimitedError(GatewayError):
    """The provider answered 429."""

    code = "rate_limited"
    retryable = True


class ProviderUnavailableError(GatewayError):
    """The provider answered 5xx or could not be reached."""

    code = "provider_unavailable"
    retryable = True


class ProviderTimeoutError(GatewayError):
    """The call timed out after the request was probably sent; the reservation stays."""

    code = "provider_timeout"
    retryable = True
    billed = True


class ProviderRejectedError(GatewayError):
    """The provider refused the request (4xx other than 402, 408, 429)."""

    code = "provider_rejected"


class ProviderProtocolError(GatewayError):
    """A 2xx reply whose body cannot be parsed; the reservation stays for a person."""

    code = "provider_protocol_error"
    billed = True


class RecordRefusedError(GatewayError):
    """`make record` refused to start: a guard (credit limit, mode, budget) is not met."""

    code = "record_refused"
