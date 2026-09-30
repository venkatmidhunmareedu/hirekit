"""GatewayLedger against Postgres: the atomic reserve, guarded settle and release, and seeding."""

import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.budget.policy import BUDGET_LIMIT_USD
from app.db.models import Budget, CallLog
from app.db.repositories.budget import read_spent
from app.db.repositories.gateway_ledger import GatewayLedger, Reservation

pytestmark = pytest.mark.integration

LIMIT = BUDGET_LIMIT_USD
KEY = "a" * 64
ledger = GatewayLedger()


async def start(session: AsyncSession, spent: str = "0") -> None:
    await ledger.ensure_budget(session, ledger=Decimal(spent))


async def reserve(session: AsyncSession, amount: str) -> Reservation | None:
    return await ledger.reserve(
        session,
        amount=Decimal(amount),
        limit=LIMIT,
        role_id=None,
        purpose="scoring",
        model="m",
        request_key=KEY,
        schema_retry=0,
    )


async def settle(session: AsyncSession, call_id: int, actual: str) -> bool:
    return await ledger.settle(
        session,
        call_id=call_id,
        input_tokens=1,
        output_tokens=1,
        actual=Decimal(actual),
        limit=LIMIT,
    )


async def call_row(session: AsyncSession, call_id: int) -> CallLog:
    row = await session.scalar(select(CallLog).where(CallLog.id == call_id))
    assert row is not None
    return row


async def test_reserve_within_the_limit_raises_spent_and_logs_a_reserved_row(
    session: AsyncSession,
) -> None:
    """AC-US-02-002-1."""
    await start(session)
    reservation = await reserve(session, "0.01")

    assert reservation is not None
    assert await read_spent(session) == Decimal("0.010000")
    row = await call_row(session, reservation.call_id)
    assert (row.status, row.cost_usd, row.purpose) == ("reserved", Decimal("0.010000"), "scoring")


async def test_reserve_that_fits_exactly_at_the_limit_succeeds(session: AsyncSession) -> None:
    await start(session, "7.99")
    assert await reserve(session, "0.01") is not None
    assert await read_spent(session) == Decimal("8.000000")


async def test_reserve_over_the_limit_returns_none_and_changes_nothing(
    session: AsyncSession,
) -> None:
    """AC-US-02-002-2: refused before any call, no row, no change."""
    await start(session, "7.995")
    assert await reserve(session, "0.01") is None
    assert await read_spent(session) == Decimal("7.995000")
    count = await session.scalar(select(func.count()).select_from(CallLog))
    assert count == 0


async def test_reserve_without_a_budget_row_returns_none_and_the_row_reads_as_missing(
    session: AsyncSession,
) -> None:
    assert await reserve(session, "0.01") is None
    assert await read_spent(session) is None


async def test_settle_replaces_the_reservation_with_the_actual_cost(session: AsyncSession) -> None:
    await start(session)
    reservation = await reserve(session, "0.01")
    assert reservation is not None

    settled = await ledger.settle(
        session,
        call_id=reservation.call_id,
        input_tokens=1200,
        output_tokens=300,
        actual=Decimal("0.002700"),
        limit=LIMIT,
    )

    assert settled is True
    assert await read_spent(session) == Decimal("0.002700")
    row = await call_row(session, reservation.call_id)
    assert (row.status, row.input_tokens, row.output_tokens) == ("settled", 1200, 300)
    assert row.cost_usd == Decimal("0.002700")


async def test_second_settle_changes_nothing(session: AsyncSession) -> None:
    await start(session)
    reservation = await reserve(session, "0.01")
    assert reservation is not None
    call_id = reservation.call_id
    assert await settle(session, call_id, "0.002") is True

    assert await settle(session, call_id, "0.005") is False
    assert await read_spent(session) == Decimal("0.002000")


async def test_release_gives_the_reservation_back(session: AsyncSession) -> None:
    await start(session)
    reservation = await reserve(session, "0.01")
    assert reservation is not None

    assert await ledger.release(session, call_id=reservation.call_id) is True

    assert await read_spent(session) == Decimal("0.000000")
    row = await call_row(session, reservation.call_id)
    assert (row.status, row.cost_usd) == ("released", Decimal("0.000000"))


async def test_release_after_settle_changes_nothing(session: AsyncSession) -> None:
    await start(session)
    reservation = await reserve(session, "0.01")
    assert reservation is not None
    await ledger.settle(
        session,
        call_id=reservation.call_id,
        input_tokens=1,
        output_tokens=1,
        actual=Decimal("0.004"),
        limit=LIMIT,
    )

    assert await ledger.release(session, call_id=reservation.call_id) is False
    assert await read_spent(session) == Decimal("0.004000")


async def test_settle_above_the_reservation_is_clamped_to_the_limit(session: AsyncSession) -> None:
    """The total never passes the limit, but the log keeps the true cost."""
    await start(session, "7.99")
    reservation = await reserve(session, "0.01")
    assert reservation is not None

    await ledger.settle(
        session,
        call_id=reservation.call_id,
        input_tokens=1,
        output_tokens=1,
        actual=Decimal("0.05"),
        limit=LIMIT,
    )

    assert await read_spent(session) == Decimal("8.000000")
    assert (await call_row(session, reservation.call_id)).cost_usd == Decimal("0.050000")


async def test_replayed_call_writes_a_log_row_with_cost_zero_and_leaves_the_budget(
    session: AsyncSession,
) -> None:
    """AC-US-02-001-4, AC-US-02-003-1."""
    await start(session, "7.5")
    call_id = await ledger.log_replay(
        session,
        role_id=None,
        purpose="eval",
        model="m",
        request_key=KEY,
        schema_retry=1,
        input_tokens=10,
        output_tokens=5,
    )

    row = await call_row(session, call_id)
    assert (row.status, row.cost_usd, row.schema_retry) == ("replayed", Decimal("0.000000"), 1)
    assert await read_spent(session) == Decimal("7.500000")


async def test_ledger_seeds_budget_with_greatest_of_database_and_file(
    session: AsyncSession,
) -> None:
    """REQ-043: a recreated database cannot reset the cap, and a higher database keeps its value."""
    await start(session, "5")
    assert await read_spent(session) == Decimal("5.000000")
    await start(session, "3")
    assert await read_spent(session) == Decimal("5.000000")
    await start(session, "6")
    assert await read_spent(session) == Decimal("6.000000")


async def test_a_ledger_above_the_limit_is_refused_by_the_cap(session: AsyncSession) -> None:
    with pytest.raises(Exception, match="chk_budget_spent_cap"):
        await start(session, "8.5")


async def test_crash_after_reserve_leaves_a_reserved_row_holding_the_amount(
    engine: AsyncEngine,
) -> None:
    """HLD section 7: a reservation committed before the call survives a crash, over-counted."""
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions.begin() as s:
            await start(s)
            reservation = await reserve(s, "0.01")
        assert reservation is not None
        # the process "crashes" here: nothing settles or releases

        async with sessions() as check:
            row = await call_row(check, reservation.call_id)
            assert (row.status, row.cost_usd) == ("reserved", Decimal("0.010000"))
            assert await read_spent(check) == Decimal("0.010000")
    finally:
        await cleanup(sessions)


async def test_concurrent_reservations_never_pass_the_limit(engine: AsyncEngine) -> None:
    """AC-US-02-002-2, tenet 8: 30 workers reserve 0.5 each against a limit of 8."""
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions.begin() as s:
            await start(s)

        async def one() -> Reservation | None:
            async with sessions.begin() as s:
                return await reserve(s, "0.5")

        results = await asyncio.gather(*(one() for _ in range(30)))

        assert sum(r is not None for r in results) == 16
        async with sessions() as check:
            assert await read_spent(check) == Decimal("8.000000")
            count = await check.scalar(select(func.count()).select_from(CallLog))
            assert count == 16
    finally:
        await cleanup(sessions)


async def cleanup(sessions: async_sessionmaker[AsyncSession]) -> None:
    """These tests commit for real, so they remove what they wrote."""
    async with sessions.begin() as s:
        await s.execute(delete(CallLog))
        await s.execute(delete(Budget))
