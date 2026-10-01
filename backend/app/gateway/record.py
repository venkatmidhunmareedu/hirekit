"""Guards around `make record`: the only manual, budget-checked way to make live calls.

`record_preflight` refuses unless the maintainer confirmed a provider-side credit limit, the
process is in live recording mode outside CI, and budget remains; it seeds the `budget` row from
the committed spend ledger and reports what is left. `record_finish` writes the new cumulative
spend back to that ledger, which is then committed (docs/design/gateway-lld.md section 4.4).

    python -m app.gateway.record preflight | finish
"""

import asyncio
import sys
from decimal import Decimal
from typing import Protocol, TextIO

from pydantic import ValidationError
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.budget.policy import BUDGET_LIMIT_USD
from app.core.config import Settings
from app.db.repositories.gateway_ledger import GatewayLedger
from app.db.session import make_engine
from app.gateway.errors import (
    BudgetNotInitialisedError,
    GatewayError,
    LedgerUnavailableError,
    LiveCallForbiddenError,
    RecordRefusedError,
)
from app.gateway.service import Transaction
from app.gateway.spend_ledger import read_ledger, write_ledger

LEDGER_NAME = "spend-ledger.json"
_UNREACHABLE = (OperationalError, InterfaceError, OSError)


class RecordLedger(Protocol):
    """What the record command needs from `GatewayLedger`."""

    async def ensure_budget(self, session: AsyncSession, *, ledger: Decimal) -> None:
        """Create the budget row from the ledger, or raise it to the ledger."""
        ...

    async def read_spent(self, session: AsyncSession) -> Decimal | None:
        """USD spent or reserved so far, or None when the budget row is missing."""
        ...


async def record_preflight(
    *, settings: Settings, transaction: Transaction, ledger: RecordLedger
) -> Decimal:
    """Refuse or return the USD remaining. Nothing is spent here.

    Cheap refusals come first and touch neither the ledger file nor the database.
    """
    if settings.ci:
        msg = "recording is a manual step and is not allowed when CI is set"
        raise LiveCallForbiddenError(msg)
    if settings.key_credit_limit_confirmed != "yes":
        msg = (
            "set a credit limit of at most USD 8 on the OpenRouter key, then set "
            "KEY_CREDIT_LIMIT_CONFIRMED=yes (HLD section 6); that limit is the real backstop"
        )
        raise RecordRefusedError(msg)
    if settings.model_mode != "live" or not settings.record_responses:
        msg = (
            "run recording through make record (it sets MODEL_MODE=live and RECORD_RESPONSES=true)"
        )
        raise RecordRefusedError(msg)
    seed = read_ledger(settings.recordings_dir / LEDGER_NAME)
    try:
        async with transaction() as session:
            await ledger.ensure_budget(session, ledger=seed)
            spent = await ledger.read_spent(session)
    except _UNREACHABLE as exc:
        msg = "the database could not be reached to read the budget"
        raise LedgerUnavailableError(msg) from exc
    if spent is None:  # pragma: no cover  (ensure_budget just created the row)
        msg = "the budget row is missing after seeding"
        raise BudgetNotInitialisedError(msg)
    remaining = BUDGET_LIMIT_USD - spent
    if remaining <= 0:
        msg = f"the budget is used up (USD {spent:.6f} of {BUDGET_LIMIT_USD:f} spent)"
        raise RecordRefusedError(msg)
    return remaining


async def record_finish(
    *, settings: Settings, transaction: Transaction, ledger: RecordLedger
) -> Decimal:
    """Write the cumulative spend to the ledger file and return it. Commit the file afterwards.

    Reserved rows a timeout left behind are counted, so the ledger over-states spend, never
    under-states it. It is written even when the pipeline failed part-way, because the money
    was spent.
    """
    try:
        async with transaction() as session:
            spent = await ledger.read_spent(session)
    except _UNREACHABLE as exc:
        msg = "the database could not be reached to read the budget"
        raise LedgerUnavailableError(msg) from exc
    if spent is None:
        msg = "the budget row does not exist, so there is no total to write"
        raise BudgetNotInitialisedError(msg)
    write_ledger(settings.recordings_dir / LEDGER_NAME, spent)
    return spent


async def run(
    command: str,
    *,
    settings: Settings,
    transaction: Transaction,
    ledger: RecordLedger,
    out: TextIO,
) -> int:
    """Run one command and return the exit code: 0 done, 1 refused or failed, 2 bad usage."""
    if command not in ("preflight", "finish"):
        out.write("usage: python -m app.gateway.record preflight | finish\n")
        return 2
    try:
        if command == "preflight":
            remaining = await record_preflight(
                settings=settings, transaction=transaction, ledger=ledger
            )
            out.write(f"record: USD {remaining:.6f} of {BUDGET_LIMIT_USD:f} remaining\n")
        else:
            spent = await record_finish(settings=settings, transaction=transaction, ledger=ledger)
            out.write(
                f"record: spend ledger set to USD {spent:.6f}; commit "
                f"{settings.recordings_dir / LEDGER_NAME} with the new recordings\n"
            )
    except GatewayError as error:
        out.write(f"record: refused: {error.message}\n")
        return 1
    return 0


async def main(command: str, out: TextIO | None = None) -> int:
    """Build the real dependencies and run `command`; invalid settings are a refusal."""
    out = out or sys.stdout
    try:
        settings = Settings()
    except ValidationError as exc:
        problems = "; ".join(
            (f"{'.'.join(str(p) for p in e['loc']).upper()}: " if e["loc"] else "")
            + e["msg"].removeprefix("Value error, ")
            for e in exc.errors(include_input=False, include_url=False)
        )
        out.write(f"record: refused: the settings are not valid for recording ({problems})\n")
        return 1
    engine = make_engine(settings)
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        return await run(
            command,
            settings=settings,
            transaction=sessions.begin,
            ledger=GatewayLedger(),
            out=out,
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "")))
