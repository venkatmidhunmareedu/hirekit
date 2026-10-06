"""Response for GET /v1/cost-log (api/openapi.yaml CostLog). Money is a decimal string."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_serializer


class BudgetState(BaseModel):
    """Spend against the limit, and whether a model action may start now."""

    spent_usd: Decimal
    limit_usd: Decimal
    mode: Literal["replay", "live"]
    model_actions_allowed: bool

    @field_serializer("spent_usd", "limit_usd")
    def _money(self, value: Decimal) -> str:
        return str(value)


class CallEntry(BaseModel):
    """One gateway call."""

    id: int
    purpose: Literal["criteria", "scoring", "kit", "eval"]
    status: Literal["reserved", "settled", "replayed", "released"]
    model: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal
    created_at: datetime

    @field_serializer("cost_usd")
    def _money(self, value: Decimal) -> str:
        return str(value)


class Page(BaseModel):
    """Cursor paging: pass `next_cursor` back as `cursor` while `has_more`."""

    next_cursor: str | None
    has_more: bool


class CostLog(BaseModel):
    """The budget and one page of the call log, newest first."""

    budget: BudgetState
    data: list[CallEntry]
    page: Page
