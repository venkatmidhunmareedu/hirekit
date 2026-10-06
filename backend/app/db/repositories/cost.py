"""The call log, read only (Q20): newest first, keyset paged on (created_at, id)."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.budget import read_spent

_FIRST: Final = text(
    "SELECT id, purpose, status, model, input_tokens, output_tokens, cost_usd, created_at "
    "FROM call_log ORDER BY created_at DESC, id DESC LIMIT :n"
)
_AFTER: Final = text(
    "SELECT id, purpose, status, model, input_tokens, output_tokens, cost_usd, created_at "
    "FROM call_log WHERE (created_at, id) < (:t, :i) ORDER BY created_at DESC, id DESC LIMIT :n"
)


@dataclass(frozen=True, slots=True)
class CallRow:
    """One gateway call as the cost log shows it (no request key, no role)."""

    id: int
    purpose: str
    status: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal
    created_at: datetime


class CostRepository:
    """Spend and the call log page."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def spent_usd(self) -> Decimal | None:
        """USD spent or reserved so far; None when the budget row is missing."""
        return await read_spent(self._session)

    async def page(self, limit: int, after: tuple[datetime, int] | None) -> list[CallRow]:
        """At most `limit` calls, strictly older than `after` when given."""
        if after is None:
            result = await self._session.execute(_FIRST, {"n": limit})
        else:
            result = await self._session.execute(_AFTER, {"n": limit, "t": after[0], "i": after[1]})
        return [
            CallRow(
                r.id,
                r.purpose,
                r.status,
                r.model,
                r.input_tokens,
                r.output_tokens,
                r.cost_usd,
                r.created_at,
            )
            for r in result
        ]
