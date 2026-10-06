"""The record command's guards: credit-limit confirmation, live mode, remaining budget, ledger."""

import io
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateway.errors import (
    BudgetLedgerError,
    BudgetNotInitialisedError,
    LedgerUnavailableError,
    LiveCallForbiddenError,
    RecordRefusedError,
)
from app.gateway.record import main, record_finish, record_preflight, run
from app.gateway.spend_ledger import read_ledger, write_ledger
from tests.gateway.fakes import DB, FakeLedger, fake_transaction


def settings_for(
    directory: Path,
    *,
    confirmed: str | None = "yes",
    live: bool = True,
    record_responses: bool = True,
    ci: bool = False,
) -> Settings:
    return Settings(
        _env_file=None,
        database_url=DB,
        recordings_dir=directory,
        model_mode="live" if live else "replay",
        openrouter_api_key=SecretStr("k") if live else None,
        record_responses=record_responses,
        key_credit_limit_confirmed=confirmed,
        ci=ci and not live,
    )


def ledger_file(directory: Path) -> Path:
    return directory / "spend-ledger.json"


async def preflight(directory: Path, ledger: FakeLedger, **overrides: object) -> Decimal:
    return await record_preflight(
        settings=settings_for(directory, **overrides),  # type: ignore[arg-type]  # test kwargs
        transaction=fake_transaction,
        ledger=ledger,
    )


async def test_record_preflight_returns_the_remaining_budget(tmp_path: Path) -> None:
    """AC-US-02-003-5: it reports what is left before anything is recorded."""
    write_ledger(ledger_file(tmp_path), Decimal("1.5"))

    remaining = await preflight(tmp_path, FakeLedger(spent=None))

    assert remaining == Decimal("6.5")


async def test_preflight_seeds_the_budget_from_the_ledger_file(tmp_path: Path) -> None:
    """HLD section 3: a recreated database cannot reset the cap."""
    write_ledger(ledger_file(tmp_path), Decimal("3"))
    ledger = FakeLedger(spent=None)

    await preflight(tmp_path, ledger)

    assert ledger.spent == Decimal(3)
    assert ledger.budget_calls[0] == "ensure_budget"


async def test_preflight_keeps_a_higher_database_total_over_the_ledger_file(tmp_path: Path) -> None:
    write_ledger(ledger_file(tmp_path), Decimal(2))

    remaining = await preflight(tmp_path, FakeLedger(spent=Decimal(5)))

    assert remaining == Decimal(3)


async def test_record_preflight_refuses_when_budget_used_up(tmp_path: Path) -> None:
    """AC-US-02-003-5."""
    write_ledger(ledger_file(tmp_path), Decimal(8))

    with pytest.raises(RecordRefusedError, match="used up"):
        await preflight(tmp_path, FakeLedger(spent=Decimal(8)))


@pytest.mark.parametrize("confirmed", [None, "", "no", "YES", "true"])
async def test_record_preflight_refuses_without_credit_limit_confirmation(
    tmp_path: Path, confirmed: str | None
) -> None:
    """AC-US-02-003-5, HLD section 6: only the exact word yes counts."""
    write_ledger(ledger_file(tmp_path), Decimal(0))
    ledger = FakeLedger(spent=None)

    with pytest.raises(RecordRefusedError, match="credit limit"):
        await preflight(tmp_path, ledger, confirmed=confirmed)

    assert ledger.budget_calls == []


async def test_record_preflight_refuses_in_ci_before_anything_else(tmp_path: Path) -> None:
    """AC-US-02-003-4."""
    ledger = FakeLedger(spent=None)

    with pytest.raises(LiveCallForbiddenError):
        await preflight(tmp_path, ledger, ci=True, live=False)

    assert ledger.budget_calls == []


async def test_record_preflight_refuses_outside_live_recording_mode(tmp_path: Path) -> None:
    write_ledger(ledger_file(tmp_path), Decimal(0))

    with pytest.raises(RecordRefusedError, match="make record"):
        await preflight(tmp_path, FakeLedger(spent=None), live=False)
    with pytest.raises(RecordRefusedError, match="make record"):
        await preflight(tmp_path, FakeLedger(spent=None), record_responses=False)


async def test_missing_ledger_file_refuses_live_start(tmp_path: Path) -> None:
    """HLD section 3: live mode must not start from an unknown total."""
    with pytest.raises(BudgetLedgerError):
        await preflight(tmp_path, FakeLedger(spent=None))


async def test_record_finish_writes_ledger_to_spent_total(tmp_path: Path) -> None:
    """HLD section 3: the ledger is updated after each live run."""
    write_ledger(ledger_file(tmp_path), Decimal(1))

    await record_finish(
        settings=settings_for(tmp_path),
        transaction=fake_transaction,
        ledger=FakeLedger(spent=Decimal("1.234567")),
    )

    assert read_ledger(ledger_file(tmp_path)) == Decimal("1.234567")


async def test_record_finish_needs_a_budget_row(tmp_path: Path) -> None:
    write_ledger(ledger_file(tmp_path), Decimal(1))

    with pytest.raises(BudgetNotInitialisedError):
        await record_finish(
            settings=settings_for(tmp_path),
            transaction=fake_transaction,
            ledger=FakeLedger(spent=None),
        )

    assert read_ledger(ledger_file(tmp_path)) == Decimal(1)


async def test_run_preflight_prints_the_remaining_budget_and_exits_zero(tmp_path: Path) -> None:
    write_ledger(ledger_file(tmp_path), Decimal("2.5"))
    out = io.StringIO()

    code = await run(
        "preflight",
        settings=settings_for(tmp_path),
        transaction=fake_transaction,
        ledger=FakeLedger(spent=None),
        out=out,
    )

    assert code == 0
    assert "USD 5.500000 of 8 remaining" in out.getvalue()


async def test_run_preflight_prints_the_refusal_and_exits_one(tmp_path: Path) -> None:
    out = io.StringIO()

    code = await run(
        "preflight",
        settings=settings_for(tmp_path, confirmed=None),
        transaction=fake_transaction,
        ledger=FakeLedger(spent=None),
        out=out,
    )

    assert code == 1
    assert "credit limit" in out.getvalue()


async def test_run_finish_prints_the_new_ledger_total(tmp_path: Path) -> None:
    write_ledger(ledger_file(tmp_path), Decimal(1))
    out = io.StringIO()

    code = await run(
        "finish",
        settings=settings_for(tmp_path),
        transaction=fake_transaction,
        ledger=FakeLedger(spent=Decimal("1.5")),
        out=out,
    )

    assert code == 0
    assert "1.500000" in out.getvalue()
    assert "commit" in out.getvalue()


async def test_run_rejects_an_unknown_command(tmp_path: Path) -> None:
    out = io.StringIO()

    code = await run(
        "bogus",
        settings=settings_for(tmp_path),
        transaction=fake_transaction,
        ledger=FakeLedger(),
        out=out,
    )

    assert code == 2
    assert "preflight" in out.getvalue()


async def test_main_turns_invalid_settings_into_a_refusal_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Live mode with no OPENROUTER_API_KEY fails settings validation; that is a refusal."""
    monkeypatch.chdir(tmp_path)  # Settings reads ./.env; a developer's real .env must not leak in
    monkeypatch.setenv("DATABASE_URL", DB)
    monkeypatch.setenv("MODEL_MODE", "live")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("CI", raising=False)

    code = await main("preflight")

    output = capsys.readouterr().out
    assert code == 1
    assert "refused" in output
    assert "OPENROUTER_API_KEY" in output
    assert "Traceback" not in output


class DownLedger(FakeLedger):
    """A ledger whose database cannot be reached."""

    async def ensure_budget(self, session: AsyncSession, *, ledger: Decimal) -> None:
        raise OperationalError("STATEMENT", {}, Exception("database down"))

    async def read_spent(self, session: AsyncSession) -> Decimal | None:
        raise OperationalError("STATEMENT", {}, Exception("database down"))


async def test_preflight_reports_an_unreachable_database_as_retryable(tmp_path: Path) -> None:
    write_ledger(ledger_file(tmp_path), Decimal(0))

    with pytest.raises(LedgerUnavailableError):
        await preflight(tmp_path, DownLedger())


async def test_finish_reports_an_unreachable_database_and_leaves_the_ledger_alone(
    tmp_path: Path,
) -> None:
    write_ledger(ledger_file(tmp_path), Decimal(1))

    with pytest.raises(LedgerUnavailableError):
        await record_finish(
            settings=settings_for(tmp_path), transaction=fake_transaction, ledger=DownLedger()
        )

    assert read_ledger(ledger_file(tmp_path)) == Decimal(1)
