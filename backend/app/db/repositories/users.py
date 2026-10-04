"""Read access to users, for sign-in and the session check."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class UserRepository:
    """Users by email (case-insensitive) or id."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def by_email(self, email: str) -> User | None:
        """The user whose lower(email) matches (uq_users_email), or None."""
        result = await self._session.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def by_id(self, user_id: uuid.UUID) -> User | None:
        """The user with this id, or None."""
        return await self._session.get(User, user_id)
