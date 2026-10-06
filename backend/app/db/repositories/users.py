"""Read access to users, for sign-in and the session check."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.candidates.assignment_schemas import InterviewerOption
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

    async def list_by_role(self, role: str, limit: int) -> list[InterviewerOption]:
        """Id and name of users with this role, by name then id, at most `limit`."""
        result = await self._session.execute(
            select(User.id, User.name)
            .where(User.role == role)
            .order_by(User.name, User.id)
            .limit(limit)
        )
        return [InterviewerOption(id=row.id, name=row.name) for row in result]
