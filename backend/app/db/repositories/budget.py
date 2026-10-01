"""Read-only access to the budget row, for the Api and the gateway."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Budget


async def read_spent(session: AsyncSession) -> Decimal | None:
    """USD spent or reserved so far, or None when the budget row does not exist."""
    result = await session.execute(select(Budget.spent_usd).where(Budget.id == 1))
    return result.scalar_one_or_none()
