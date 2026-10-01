"""The record command's preflight and finish against the real ledger and budget row."""

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.db.models import Budget, CallLog
from app.db.repositories.budget import read_spent
from app.db.repositories.gateway_ledger import GatewayLedger
from app.gateway.errors import RecordRefusedError
from app.gateway.record import record_finish, record_preflight
from app.gateway.spend_ledger import read_ledger, write_ledger
from tests.gateway.test_record import settings_for

pytestmark = pytest.mark.integration


async def test_preflight_seeds_the_budget_and_finish_writes_the_total_back(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """HLD section 3: the ledger file survives a recreated database and follows the spend."""
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    ledger = GatewayLedger()
    settings = settings_for(tmp_path)
    write_ledger(tmp_path / "spend-ledger.json", Decimal("2"))
    try:
        remaining = await record_preflight(
            settings=settings, transaction=sessions.begin, ledger=ledger
        )
        assert remaining == Decimal("6.000000")

        async with sessions.begin() as s:  # a live call reserves 0.25 during the run
            await ledger.reserve(
                s,
                amount=Decimal("0.25"),
                limit=Decimal(8),
                role_id=None,
                purpose="scoring",
                model="m",
                request_key="a" * 64,
                schema_retry=0,
            )
        total = await record_finish(settings=settings, transaction=sessions.begin, ledger=ledger)

        assert total == Decimal("2.250000")
        assert read_ledger(tmp_path / "spend-ledger.json") == Decimal("2.250000")
    finally:
        await cleanup(sessions)


async def test_preflight_refuses_when_the_seeded_budget_is_used_up(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    """AC-US-02-003-5."""
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    write_ledger(tmp_path / "spend-ledger.json", Decimal(8))
    try:
        with pytest.raises(RecordRefusedError, match="used up"):
            await record_preflight(
                settings=settings_for(tmp_path), transaction=sessions.begin, ledger=GatewayLedger()
            )
        async with sessions() as check:
            assert await read_spent(check) == Decimal("8.000000")
    finally:
        await cleanup(sessions)


async def cleanup(sessions: async_sessionmaker) -> None:  # type: ignore[type-arg]
    async with sessions.begin() as s:
        await s.execute(delete(CallLog))
        await s.execute(delete(Budget))
