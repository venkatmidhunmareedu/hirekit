"""Sign-in and sign-out: the service owns the transactions (repositories never commit)."""

import secrets
from datetime import UTC, datetime, timedelta

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnauthenticatedError
from app.core.passwords import DUMMY_HASH, verify_password
from app.db.models import User
from app.db.repositories.sessions import SessionRepository
from app.db.repositories.users import UserRepository


async def login(
    db: AsyncSession,
    users: UserRepository,
    sessions: SessionRepository,
    *,
    email: str,
    password: str,
    ttl: timedelta,
) -> tuple[str, str, User]:
    """The new cookie value, its CSRF token and the user.

    An unknown email verifies against a dummy hash, so it costs the same as a wrong password
    and answers with the same text. No transaction is open during the verify: the read ends
    first, and the write transaction covers only the session insert (LLD T1).
    """
    user = await users.by_email(email)
    stored = user.password_hash if user is not None else DUMMY_HASH
    await db.commit()  # ends the read transaction (nothing written); rows stay loaded
    matched = await run_in_threadpool(verify_password, stored, password)
    if user is None or not matched:
        raise UnauthenticatedError("invalid email or password")
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    async with db.begin():
        await sessions.create(token, user.id, csrf_token, datetime.now(UTC) + ttl)
    return token, csrf_token, user


async def logout(db: AsyncSession, sessions: SessionRepository, *, token: str) -> None:
    """Delete the session row for this cookie value."""
    await db.commit()  # ends the read transaction the session check opened
    async with db.begin():
        await sessions.delete(token)
