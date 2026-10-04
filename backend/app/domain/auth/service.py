"""Sign-in: check the password and open a session."""

import secrets
from datetime import UTC, datetime, timedelta

from fastapi.concurrency import run_in_threadpool

from app.core.errors import UnauthenticatedError
from app.core.passwords import DUMMY_HASH, verify_password
from app.db.models import User
from app.db.repositories.sessions import SessionRepository
from app.db.repositories.users import UserRepository


async def login(
    users: UserRepository,
    sessions: SessionRepository,
    *,
    email: str,
    password: str,
    ttl: timedelta,
) -> tuple[str, str, User]:
    """The new cookie value, its CSRF token and the user.

    An unknown email verifies against a dummy hash, so it costs the same as a wrong password
    and answers with the same text.
    """
    user = await users.by_email(email)
    stored = user.password_hash if user is not None else DUMMY_HASH
    matched = await run_in_threadpool(verify_password, stored, password)
    if user is None or not matched:
        raise UnauthenticatedError("invalid email or password")
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    await sessions.create(token, user.id, csrf_token, datetime.now(UTC) + ttl)
    return token, csrf_token, user
