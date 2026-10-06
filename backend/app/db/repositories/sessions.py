"""Server-side sessions. Only the SHA-256 of the cookie value is stored."""

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserSession


def hash_token(token: str) -> bytes:
    """The 32-byte value stored in sessions.token_hash."""
    return hashlib.sha256(token.encode()).digest()


class SessionRepository:
    """Sessions by cookie value. Writes join the caller's transaction; the service owns it."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, token: str, user_id: uuid.UUID, csrf_token: str, expires_at: datetime
    ) -> None:
        """Store the session under the hash of `token`, never `token` itself."""
        self._session.add(
            UserSession(
                token_hash=hash_token(token),
                user_id=user_id,
                csrf_token=csrf_token,
                expires_at=expires_at,
            )
        )
        await self._session.flush()

    async def read_valid(self, token: str) -> UserSession | None:
        """The session for this cookie value when it has not expired, else None."""
        result = await self._session.execute(
            select(UserSession).where(
                UserSession.token_hash == hash_token(token),
                UserSession.expires_at > func.now(),
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, token: str) -> None:
        """Remove the session (sign out)."""
        await self._session.execute(
            delete(UserSession).where(UserSession.token_hash == hash_token(token))
        )

    async def delete_for_user(self, user_id: uuid.UUID) -> None:
        """Remove every session of this user (sign out everywhere)."""
        await self._session.execute(delete(UserSession).where(UserSession.user_id == user_id))
