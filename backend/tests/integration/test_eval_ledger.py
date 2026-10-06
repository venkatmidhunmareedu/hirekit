"""The evals on the real ledger: `call_log.role_id` is a foreign key, an eval call has no role."""

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.db.models import Budget, CallLog
from app.db.repositories.gateway_ledger import GatewayLedger
from app.evals.run import run_scoring
from app.gateway.recordings import RecordingStore
from app.gateway.service import Gateway
from app.gateway.transport import Transport, TransportReply
from app.seed.data import load_seed
from tests.evals.test_run import EXPECTED, GOOD, root
from tests.gateway.fakes import ScriptedTransport, make_settings

__all__ = ["root"]

pytestmark = pytest.mark.integration

ledger = GatewayLedger()


def _factory(transport: ScriptedTransport) -> Callable[[], Transport]:
    return lambda: transport


async def test_live_then_replayed_eval_calls_log_without_a_role(
    engine: AsyncEngine, tmp_path: Path, root: Path
) -> None:
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    seed = load_seed(root, EXPECTED)
    reply = TransportReply(text=GOOD, input_tokens=100, output_tokens=50, finish_reason="stop")
    recordings = tmp_path / "rec"
    recordings.mkdir()
    async with sessions.begin() as s:
        await ledger.ensure_budget(s, ledger=Decimal(0))
    try:
        for live in (True, False):
            settings = make_settings(
                recordings,
                model_mode="live" if live else "replay",
                openrouter_api_key="k" if live else None,
                record_responses=live,
            )
            transport = ScriptedTransport(*[reply] * len(seed.resumes))
            gateway = Gateway(
                settings=settings,
                transaction=sessions.begin,
                ledger=ledger,
                store=RecordingStore(recordings),
                transport_factory=_factory(transport) if live else None,
            )
            results = await run_scoring(seed, gateway, seed_root=root)
            assert len(results) == len(seed.resumes)

        async with sessions() as check:
            rows = (await check.execute(select(CallLog.role_id, CallLog.status))).all()
        assert len(rows) == 2 * len(seed.resumes)
        assert {role_id for role_id, _ in rows} == {None}
    finally:
        async with sessions.begin() as s:
            await s.execute(delete(CallLog))
            await s.execute(delete(Budget))
            assert await s.scalar(select(func.count()).select_from(CallLog)) == 0
