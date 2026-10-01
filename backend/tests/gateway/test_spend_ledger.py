"""The committed spend ledger holds one non-negative decimal."""

from decimal import Decimal
from pathlib import Path

import pytest

from app.core.config import DEFAULT_RECORDINGS_DIR
from app.gateway.errors import BudgetLedgerError
from app.gateway.spend_ledger import read_ledger, write_ledger


def test_committed_ledger_starts_at_zero() -> None:
    assert read_ledger(DEFAULT_RECORDINGS_DIR / "spend-ledger.json") == Decimal(0)


def test_write_then_read_round_trips_exactly(tmp_path: Path) -> None:
    path = tmp_path / "spend-ledger.json"
    write_ledger(path, Decimal("1.234567"))
    assert read_ledger(path) == Decimal("1.234567")
    assert path.read_text(encoding="utf-8").endswith("}\n")


def test_write_creates_the_directory_and_leaves_no_temp_files(tmp_path: Path) -> None:
    path = tmp_path / "new" / "spend-ledger.json"
    write_ledger(path, Decimal(2))
    assert [p.name for p in path.parent.iterdir()] == ["spend-ledger.json"]


def test_missing_ledger_file_raises_ledger_error(tmp_path: Path) -> None:
    """HLD section 3: live mode must not start from an unknown total."""
    with pytest.raises(BudgetLedgerError):
        read_ledger(tmp_path / "spend-ledger.json")


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        "{}",
        '{"cumulative_live_usd": "abc"}',
        '{"cumulative_live_usd": "-1"}',
        '{"cumulative_live_usd": "NaN"}',
        "[]",
    ],
)
def test_unreadable_or_invalid_ledger_raises(tmp_path: Path, body: str) -> None:
    path = tmp_path / "spend-ledger.json"
    path.write_text(body)
    with pytest.raises(BudgetLedgerError):
        read_ledger(path)


@pytest.mark.parametrize("bad", [Decimal(-1), Decimal("NaN"), Decimal("Infinity")])
def test_write_refuses_a_bad_amount(tmp_path: Path, bad: Decimal) -> None:
    with pytest.raises(BudgetLedgerError):
        write_ledger(tmp_path / "spend-ledger.json", bad)
