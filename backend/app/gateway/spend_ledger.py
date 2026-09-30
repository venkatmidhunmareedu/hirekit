"""The committed spend ledger: cumulative live spend, so a recreated database cannot reset the cap.

`backend/recordings/spend-ledger.json` holds one decimal. It seeds the `budget` row
(GREATEST of the database and this file) and is rewritten by `record_finish`.
"""

import json
import os
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.gateway.errors import BudgetLedgerError

FIELD = "cumulative_live_usd"


def read_ledger(path: Path) -> Decimal:
    """The cumulative live spend in USD; raises `BudgetLedgerError` if it is missing or bad."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        value = Decimal(str(data[FIELD]))
    except (OSError, ValueError, KeyError, TypeError, InvalidOperation) as exc:
        msg = f"spend ledger {path} is missing or unreadable"
        raise BudgetLedgerError(msg) from exc
    if not value.is_finite() or value < 0:
        msg = f"spend ledger {path} holds {value}, which is not a non-negative amount"
        raise BudgetLedgerError(msg)
    return value


def write_ledger(path: Path, spent: Decimal) -> None:
    """Rewrite the ledger atomically with the new cumulative spend."""
    if not spent.is_finite() or spent < 0:
        msg = f"refusing to write {spent} to the spend ledger"
        raise BudgetLedgerError(msg)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps({FIELD: format(spent, "f")}, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
