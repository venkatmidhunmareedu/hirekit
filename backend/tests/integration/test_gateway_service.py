"""Gateway.complete end to end on Postgres: real ledger, real transactions, scripted transport."""

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.budget.policy import actual_cost
from app.db.models import Budget, CallLog
from app.db.repositories.budget import read_spent
from app.db.repositories.gateway_ledger import GatewayLedger
from app.gateway.errors import BudgetReachedError
from app.gateway.recordings import RecordingStore
from app.gateway.service import Gateway
from app.gateway.transport import TransportReply
from tests.gateway.fakes import ScriptedTransport, make_settings, record
from tests.gateway.helpers import ROLE, make_request

pytestmark = pytest.mark.integration

GOOD = TransportReply(text="{}", input_tokens=1200, output_tokens=300, finish_reason="stop")
ledger = GatewayLedger()


def gateway_on(
    engine: AsyncEngine, tmp_path: Path, transport: ScriptedTransport | None, *, live: bool
) -> Gateway:
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = make_settings(
        tmp_path, model_mode="live" if live else "replay", openrouter_api_key="k" if live else None
    )
    return Gateway(
        settings=settings,
        transaction=sessions.begin,
        ledger=ledger,
        store=RecordingStore(tmp_path),
        transport_factory=(lambda: transport) if transport else None,
    )


async def seed_budget(engine: AsyncEngine, spent: str) -> async_sessionmaker[AsyncSession]:
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions.begin() as s:
        await ledger.ensure_budget(s, ledger=Decimal(spent))
        # call_log.role_id is a real foreign key: the role the test requests must exist
        await s.execute(
            text("INSERT INTO roles(id, title, job_description) VALUES (:id, 'T', 'JD')"),
            {"id": str(ROLE)},
        )
    return sessions


async def cleanup(sessions: async_sessionmaker[AsyncSession]) -> None:
    async with sessions.begin() as s:
        await s.execute(delete(CallLog))
        await s.execute(delete(Budget))
        await s.execute(text("DELETE FROM roles WHERE id = :id"), {"id": str(ROLE)})


async def test_a_live_call_reserves_then_settles_in_postgres(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """AC-US-02-001-4, AC-US-02-002-1 against the real ledger."""
    sessions = await seed_budget(engine, "1")
    try:
        gateway = gateway_on(engine, tmp_path, ScriptedTransport(GOOD), live=True)

        await gateway.complete(make_request(text="a resume"))

        cost = actual_cost(1200, 300, Decimal(1), Decimal(5))
        async with sessions() as check:
            assert await read_spent(check) == Decimal(1) + cost
            row = await check.scalar(select(CallLog))
            assert row is not None
            assert (row.status, row.cost_usd, row.purpose) == ("settled", cost, "scoring")
    finally:
        await cleanup(sessions)


async def test_concurrent_live_calls_never_pass_the_limit(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """AC-US-02-002-2, tenet 8: 40 workers call at once with room for only some of them."""
    sessions = await seed_budget(engine, "7.95")
    try:
        transport = ScriptedTransport(*([GOOD] * 40))
        gateway = gateway_on(engine, tmp_path, transport, live=True)

        results = await asyncio.gather(
            *(gateway.complete(make_request(text=f"resume {n}")) for n in range(40)),
            return_exceptions=True,
        )

        refused = [r for r in results if isinstance(r, BudgetReachedError)]
        served = [r for r in results if not isinstance(r, BaseException)]
        assert len(refused) > 0
        assert len(served) > 0
        assert len(refused) + len(served) == 40
        assert len(transport.requests) == len(served)
        async with sessions() as check:
            spent = await read_spent(check)
            assert spent is not None
            assert spent <= Decimal(8)
    finally:
        await cleanup(sessions)


async def test_ten_replay_passes_never_touch_the_budget_row_in_postgres(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """HLD section 16 falsifier: replay at 7.995 spent must not raise BudgetReached or move it."""
    sessions = await seed_budget(engine, "7.995")
    try:
        requests = [make_request(text=f"resume {n}") for n in range(9)]
        gateway = gateway_on(engine, tmp_path, None, live=False)
        for request in requests:
            record(request, gateway._settings)

        for _ in range(10):
            for request in requests:
                assert (await gateway.complete(request)).replayed is True

        async with sessions() as check:
            assert await read_spent(check) == Decimal("7.995000")
            replayed = await check.scalar(select(func.count()).select_from(CallLog))
            assert replayed == 90
    finally:
        await cleanup(sessions)
