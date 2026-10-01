"""Gateway.complete in live mode: reserve first, settle or release after, never overshoot."""

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from structlog.testing import capture_logs

from app.budget.policy import actual_cost
from app.core.config import Settings
from app.gateway.errors import (
    BudgetNotInitialisedError,
    BudgetReachedError,
    GatewayError,
    LedgerUnavailableError,
    LiveCallForbiddenError,
    ProviderCreditExhaustedError,
    ProviderProtocolError,
    ProviderRejectedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)
from app.gateway.service import Gateway
from app.gateway.transport import Transport, TransportReply
from tests.gateway.fakes import (
    FakeLedger,
    ScriptedTransport,
    TrackingTransaction,
    billed,
    key_for,
    make_gateway,
    make_settings,
)
from tests.gateway.helpers import make_request

KEY = "sk-or-live-secret"
RESUME = "Built a payments service in Python at Acme."
GOOD = TransportReply(
    text='{"scores": []}', input_tokens=1200, output_tokens=300, finish_reason="stop"
)
PRICE_IN, PRICE_OUT = Decimal(1), Decimal(5)
ACTUAL = actual_cost(1200, 300, PRICE_IN, PRICE_OUT)


def live_settings(tmp_path: Path, *, record_responses: bool = False) -> Settings:
    return make_settings(
        tmp_path, model_mode="live", openrouter_api_key=KEY, record_responses=record_responses
    )


def build(
    tmp_path: Path,
    transport: Transport,
    ledger: FakeLedger | None = None,
    *,
    record_responses: bool = False,
    transactions: TrackingTransaction | None = None,
) -> tuple[Gateway, FakeLedger]:
    ledger = ledger or FakeLedger()
    gateway = make_gateway(
        live_settings(tmp_path, record_responses=record_responses),
        ledger,
        transport_factory=lambda: transport,
        transaction=transactions or TrackingTransaction(),
    )
    return gateway, ledger


def recorded(directory: Path) -> list[str]:
    """Names of the recording files in `directory`, or none if it does not exist."""
    return sorted(p.name for p in directory.glob("*.json")) if directory.is_dir() else []


async def test_completed_call_logs_tokens_cost_purpose_role_through_ledger(tmp_path: Path) -> None:
    """AC-US-02-001-4."""
    gateway, ledger = build(tmp_path, ScriptedTransport(GOOD))

    reply = await gateway.complete(make_request(purpose="scoring", text=RESUME))

    [row] = ledger.rows
    assert (row.status, row.purpose, row.input_tokens, row.output_tokens) == (
        "settled",
        "scoring",
        1200,
        300,
    )
    assert row.cost_usd == ACTUAL
    assert row.role_id is not None
    assert reply.replayed is False
    assert (reply.cost_usd, reply.input_tokens, reply.output_tokens) == (ACTUAL, 1200, 300)
    assert reply.text == '{"scores": []}'


async def test_running_total_rises_by_call_cost(tmp_path: Path) -> None:
    """AC-US-02-002-1."""
    gateway, ledger = build(tmp_path, ScriptedTransport(GOOD, GOOD))

    await gateway.complete(make_request(text="first"))
    await gateway.complete(make_request(text="second"))

    assert ledger.spent == ACTUAL * 2


async def test_finish_reason_length_is_passed_to_the_caller(tmp_path: Path) -> None:
    cut = TransportReply(text="{", input_tokens=10, output_tokens=1500, finish_reason="length")
    gateway, _ = build(tmp_path, ScriptedTransport(cut))

    assert (await gateway.complete(make_request(text=RESUME))).finish_reason == "length"


async def test_the_request_sent_has_the_model_the_clamped_cap_and_both_texts(
    tmp_path: Path,
) -> None:
    """AC-US-02-001-2, AC-US-02-001-3."""
    transport = ScriptedTransport(GOOD)
    gateway, _ = build(tmp_path, transport)

    await gateway.complete(make_request(max_tokens=99_999, text=RESUME))

    [sent] = transport.requests
    assert sent.model == "anthropic/claude-haiku-4.5"
    assert sent.max_tokens == 1500
    assert sent.user == RESUME
    assert sent.system == "Score each criterion."


async def test_reservation_that_fits_exactly_at_the_limit_succeeds(tmp_path: Path) -> None:
    """AC-US-02-002-1, the pair: the last reservation that fits is allowed."""
    request = make_request(max_tokens=1500, text="x" * 30)
    # 1500 * 5 / 1e6 = 0.0075, plus 51 chars / 3 = 17 tokens at 1 / 1e6 = 0.000017
    ledger = FakeLedger(spent=Decimal("8") - Decimal("0.007517"))
    gateway, _ = build(tmp_path, ScriptedTransport(GOOD), ledger)

    reply = await gateway.complete(request)

    assert reply.replayed is False


async def test_call_refused_before_transport_when_reserve_would_pass_the_limit(
    tmp_path: Path,
) -> None:
    """AC-US-02-002-2: refused before the provider is contacted."""
    transport = ScriptedTransport(GOOD)
    gateway, ledger = build(tmp_path, transport, FakeLedger(spent=Decimal("7.999")))

    with pytest.raises(BudgetReachedError):
        await gateway.complete(make_request(text=RESUME))

    assert transport.requests == []
    assert ledger.rows == []
    assert ledger.spent == Decimal("7.999")


async def test_budget_reached_carries_total_and_limit(tmp_path: Path) -> None:
    """AC-US-02-002-3."""
    gateway, _ = build(tmp_path, ScriptedTransport(GOOD), FakeLedger(spent=Decimal("7.999")))

    with pytest.raises(BudgetReachedError) as caught:
        await gateway.complete(make_request(text=RESUME))

    assert (caught.value.spent, caught.value.limit) == (Decimal("7.999"), Decimal(8))
    assert caught.value.retryable is False


async def test_missing_budget_row_raises_budget_not_initialised(tmp_path: Path) -> None:
    transport = ScriptedTransport(GOOD)
    gateway, _ = build(tmp_path, transport, FakeLedger(spent=None))

    with pytest.raises(BudgetNotInitialisedError):
        await gateway.complete(make_request(text=RESUME))

    assert transport.requests == []


async def test_reserve_database_failure_raises_ledger_unavailable_and_makes_no_call(
    tmp_path: Path,
) -> None:
    transport = ScriptedTransport(GOOD)
    gateway, _ = build(tmp_path, transport, FakeLedger(fail_reserve=True))

    with pytest.raises(LedgerUnavailableError) as caught:
        await gateway.complete(make_request(text=RESUME))

    assert caught.value.retryable is True
    assert transport.requests == []


async def test_reservation_is_committed_before_the_call_and_no_transaction_is_open_during_it(
    tmp_path: Path,
) -> None:
    """Tenet 8, python rules: no lock is held across the network call."""
    transactions = TrackingTransaction()
    transport = ScriptedTransport(GOOD, transactions=transactions)
    gateway, ledger = build(tmp_path, transport, transactions=transactions)

    await gateway.complete(make_request(text=RESUME))

    assert transport.open_transactions_at_call == [0]
    assert ledger.budget_calls == ["reserve", "settle"]
    assert transactions.total == 2


@pytest.mark.parametrize(
    ("error", "kept"),
    [
        (ProviderUnavailableError("5xx, no usage"), False),
        (RateLimitedError("429"), False),
        (ProviderCreditExhaustedError("402"), False),
        (ProviderRejectedError("400"), False),
        (ProviderUnavailableError("5xx with usage"), True),
        (ProviderTimeoutError("read timeout"), True),
        (ProviderProtocolError("unparseable 2xx"), True),
    ],
    ids=["5xx", "429", "402", "4xx", "5xx-billed", "timeout", "unparseable"],
)
async def test_a_failed_call_releases_or_keeps_the_reservation_by_billed(
    tmp_path: Path, error: GatewayError, kept: bool
) -> None:
    """HLD section 3: released when the provider reported no usage, kept when it may have billed."""
    billed(error, kept=kept)
    transport = ScriptedTransport(error)
    gateway, ledger = build(tmp_path, transport)

    with pytest.raises(GatewayError) as caught:
        await gateway.complete(make_request(text=RESUME))

    assert caught.value is error
    [row] = ledger.rows
    if kept:
        assert row.status == "reserved"
        assert ledger.spent is not None
        assert ledger.spent > 0
    else:
        assert row.status == "released"
        assert ledger.spent == 0


async def test_a_released_call_frees_room_for_the_next(tmp_path: Path) -> None:
    almost_full = FakeLedger(spent=Decimal("7.99"))
    transport = ScriptedTransport(billed(RateLimitedError("429"), kept=False), GOOD)
    gateway, ledger = build(tmp_path, transport, almost_full)

    with pytest.raises(RateLimitedError):
        await gateway.complete(make_request(text=RESUME))
    reply = await gateway.complete(make_request(text=RESUME))

    assert reply.replayed is False
    assert ledger.spent is not None
    assert ledger.spent < Decimal("8")


async def test_settle_above_the_reservation_is_clamped_to_the_limit(tmp_path: Path) -> None:
    """The total never passes the limit; the log keeps the true cost."""
    huge = TransportReply(text="x", input_tokens=2_000_000, output_tokens=0, finish_reason="stop")
    gateway, ledger = build(tmp_path, ScriptedTransport(huge), FakeLedger(spent=Decimal("7.99")))

    await gateway.complete(make_request(text=RESUME))

    assert ledger.spent == Decimal(8)
    assert ledger.rows[0].cost_usd == Decimal("2.000000")


async def test_settle_failure_still_returns_reply_and_leaves_row_reserved(tmp_path: Path) -> None:
    """HLD section 7: the call was paid for, so the reply is not thrown away."""
    gateway, ledger = build(tmp_path, ScriptedTransport(GOOD), FakeLedger(fail_settle=True))

    with capture_logs() as logs:
        reply = await gateway.complete(make_request(text=RESUME))

    assert reply.text == '{"scores": []}'
    assert ledger.rows[0].status == "reserved"
    assert any(line["event"] == "budget_settle_failed" for line in logs)


async def test_release_failure_still_raises_the_original_error_and_leaves_row_reserved(
    tmp_path: Path,
) -> None:
    error = billed(RateLimitedError("429"), kept=False)
    gateway, ledger = build(tmp_path, ScriptedTransport(error), FakeLedger(fail_release=True))

    with pytest.raises(RateLimitedError) as caught:
        await gateway.complete(make_request(text=RESUME))

    assert caught.value is error
    assert ledger.rows[0].status == "reserved"


async def test_a_cancelled_call_leaves_the_reservation_in_place(tmp_path: Path) -> None:
    """HLD section 7: a crash or cancel after the reservation over-counts, never under-counts."""
    gateway, ledger = build(tmp_path, ScriptedTransport(asyncio.CancelledError()))

    with pytest.raises(asyncio.CancelledError):
        await gateway.complete(make_request(text=RESUME))

    assert ledger.rows[0].status == "reserved"
    assert ledger.spent is not None
    assert ledger.spent > 0


async def test_ci_blocks_a_live_call_before_any_reservation(tmp_path: Path) -> None:
    """AC-US-02-003-4: the transport refuses to be built, and nothing was reserved."""

    def refuse() -> Transport:
        msg = "a live model call is not allowed when CI is set"
        raise LiveCallForbiddenError(msg)

    ledger = FakeLedger()
    gateway = make_gateway(live_settings(tmp_path), ledger, transport_factory=refuse)

    with pytest.raises(LiveCallForbiddenError):
        await gateway.complete(make_request(text=RESUME))

    assert ledger.budget_calls == []
    assert ledger.rows == []


async def test_the_transport_is_built_once_and_closed_with_the_gateway(tmp_path: Path) -> None:
    built: list[int] = []
    transport = ScriptedTransport(GOOD, GOOD)

    def factory() -> Transport:
        built.append(1)
        return transport

    gateway = make_gateway(live_settings(tmp_path), FakeLedger(), transport_factory=factory)
    await gateway.complete(make_request(text="one"))
    await gateway.complete(make_request(text="two"))
    await gateway.aclose()

    assert built == [1]
    assert transport.closed is True


async def test_aclose_before_any_live_call_is_harmless(tmp_path: Path) -> None:
    gateway = make_gateway(live_settings(tmp_path), FakeLedger())
    await gateway.aclose()


async def test_a_recording_is_written_only_when_record_responses_is_true(tmp_path: Path) -> None:
    request = make_request(text=RESUME)
    off_dir, on_dir = tmp_path / "off", tmp_path / "on"

    gateway_off, _ = build(off_dir, ScriptedTransport(GOOD))
    await gateway_off.complete(request)
    gateway_on, _ = build(on_dir, ScriptedTransport(GOOD), record_responses=True)
    await gateway_on.complete(request)

    assert recorded(off_dir) == []
    assert recorded(on_dir) == [f"{key_for(request, live_settings(on_dir))}.json"]


async def test_a_live_recording_replays_the_same_reply(tmp_path: Path) -> None:
    """The record and replay halves meet: what make record writes, replay serves."""
    request = make_request(text=RESUME)
    gateway, _ = build(tmp_path, ScriptedTransport(GOOD), record_responses=True)
    live = await gateway.complete(request)

    replay = await make_gateway(make_settings(tmp_path), FakeLedger()).complete(request)

    assert replay.replayed is True
    assert (replay.text, replay.input_tokens, replay.output_tokens) == (
        live.text,
        live.input_tokens,
        live.output_tokens,
    )
    assert replay.request_key == live.request_key


async def test_only_successful_replies_are_recorded(tmp_path: Path) -> None:
    """decisions.md conflict 2: a failed call leaves no recording."""
    transport = ScriptedTransport(billed(ProviderUnavailableError("5xx"), kept=False))
    gateway, _ = build(tmp_path, transport, record_responses=True)

    with pytest.raises(ProviderUnavailableError):
        await gateway.complete(make_request(text=RESUME))

    assert recorded(tmp_path) == []


async def test_no_key_or_resume_text_in_log_lines_or_rows(tmp_path: Path) -> None:
    """AC-US-02-001-5, AC-US-02-001-6, tenet 7."""
    error = billed(ProviderTimeoutError("timed out"), kept=True)
    gateway, ledger = build(tmp_path, ScriptedTransport(GOOD, error))

    with capture_logs() as logs:
        await gateway.complete(make_request(text=RESUME))
        with pytest.raises(ProviderTimeoutError):
            await gateway.complete(make_request(text="another Acme resume"))

    everything = f"{logs} {ledger.rows}"
    assert KEY not in everything
    assert "Acme" not in everything
    assert "payments" not in everything
    assert any(line["event"] == "gateway_call" and line["replayed"] is False for line in logs)


class BrokenReferenceLedger(FakeLedger):
    """A ledger whose reserve fails like a bad role id: an integrity error, not an outage."""

    async def reserve(self, *args: object, **kwargs: object) -> None:
        raise IntegrityError("INSERT", {}, Exception("violates foreign key"))


async def test_an_integrity_error_is_a_bug_and_is_not_reported_as_a_retryable_outage(
    tmp_path: Path,
) -> None:
    """A retry would fail forever, so it must not look like LedgerUnavailableError."""
    transport = ScriptedTransport(GOOD)
    gateway, _ = build(tmp_path, transport, BrokenReferenceLedger())

    with pytest.raises(IntegrityError):
        await gateway.complete(make_request(text=RESUME))

    assert transport.requests == []
