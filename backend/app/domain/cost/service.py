"""The cost log: the budget state and one keyset page of the call log."""

import base64
import binascii
from datetime import datetime
from decimal import Decimal

from app.api.cost.schemas import BudgetState, CallEntry, CostLog, Page
from app.budget.policy import BUDGET_LIMIT_USD, model_actions_allowed
from app.core.config import Settings
from app.core.errors import ValidationFailedError
from app.db.repositories.cost import CostRepository


def encode_cursor(created_at: datetime, call_id: int) -> str:
    """Opaque to the client: the last row's (created_at, id), url-safe base64."""
    return base64.urlsafe_b64encode(f"{created_at.isoformat()}|{call_id}".encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    """Back to (created_at, id); anything else is a 422, never a 500."""
    try:
        stamp, _, number = base64.urlsafe_b64decode(cursor.encode()).decode().partition("|")
        created_at = datetime.fromisoformat(stamp)
        if created_at.tzinfo is None:
            raise ValueError("naive timestamp")
        return created_at, int(number)
    except (binascii.Error, UnicodeError, ValueError) as exc:
        raise ValidationFailedError(
            "request failed validation",
            details={
                "errors": [{"loc": ["query", "cursor"], "msg": "bad cursor", "type": "value"}]
            },
        ) from exc


async def cost_log(
    costs: CostRepository, settings: Settings, limit: int, cursor: str | None
) -> CostLog:
    """Budget first, then `limit` calls; one extra row tells whether another page exists."""
    after = decode_cursor(cursor) if cursor else None
    spent = await costs.spent_usd() or Decimal(0)
    rows = await costs.page(limit + 1, after)
    shown = rows[:limit]
    more = len(rows) > limit
    return CostLog(
        budget=BudgetState(
            spent_usd=spent,
            limit_usd=BUDGET_LIMIT_USD,
            mode=settings.model_mode,
            model_actions_allowed=model_actions_allowed(
                settings.model_mode,
                spent,
                settings.price_input_usd_per_mtok,
                settings.price_output_usd_per_mtok,
            ),
        ),
        data=[CallEntry.model_validate(r, from_attributes=True) for r in shown],
        page=Page(
            next_cursor=encode_cursor(shown[-1].created_at, shown[-1].id) if more else None,
            has_more=more,
        ),
    )
