"""The user and session repositories against Postgres (timestamptz, hash-only storage)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.passwords import hash_password
from app.db.repositories.sessions import SessionRepository, hash_token
from app.db.repositories.users import UserRepository
from app.domain.auth.service import login, logout

pytestmark = pytest.mark.integration

LIVE = timedelta(hours=1)


async def seed_user(session: AsyncSession, email: str = "Riya@Example.com") -> UUID:
    user_id = await session.scalar(
        text(
            "INSERT INTO users(name, email, role, password_hash) "
            "VALUES ('Riya', :email, 'recruiter', 'x') RETURNING id"
        ),
        {"email": email},
    )
    assert isinstance(user_id, UUID)
    return user_id


async def test_a_created_session_is_read_back_for_its_user(session: AsyncSession) -> None:
    user_id = await seed_user(session)
    sessions = SessionRepository(session)

    await sessions.create("tok-1", user_id, "csrf-1", datetime.now(UTC) + LIVE)
    row = await sessions.read_valid("tok-1")

    assert row is not None
    assert (row.user_id, row.csrf_token) == (user_id, "csrf-1")


async def test_the_session_token_is_stored_only_as_a_hash(session: AsyncSession) -> None:
    user_id = await seed_user(session)
    cookie_value = "tok-secret-value"

    await SessionRepository(session).create(
        cookie_value, user_id, "csrf-2", datetime.now(UTC) + LIVE
    )

    result = await session.execute(text("SELECT sessions::text, token_hash FROM sessions"))
    as_text, stored = result.one()
    assert bytes(stored) == hash_token(cookie_value)
    assert cookie_value not in as_text


async def test_read_valid_ignores_an_expired_session(session: AsyncSession) -> None:
    user_id = await seed_user(session)
    sessions = SessionRepository(session)
    await sessions.create("old", user_id, "c", datetime.now(UTC) - timedelta(seconds=5))
    await sessions.create("new", user_id, "c", datetime.now(UTC) + LIVE)

    assert await sessions.read_valid("old") is None
    assert await sessions.read_valid("new") is not None


async def test_by_email_ignores_case(session: AsyncSession) -> None:
    user_id = await seed_user(session, "Riya@Example.com")

    user = await UserRepository(session).by_email("rIYA@example.COM")

    assert user is not None
    assert user.id == user_id


async def test_login_and_logout_commit_through_the_service(engine: AsyncEngine) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    email = f"svc-{uuid4().hex}@example.com"
    async with factory.begin() as setup:
        await setup.execute(
            text(
                "INSERT INTO users(name, email, role, password_hash) "
                "VALUES ('Svc', :email, 'recruiter', :hash)"
            ),
            {"email": email, "hash": hash_password("correct-horse-battery")},
        )
    try:
        async with factory() as db:
            token, _, _user = await login(
                db,
                UserRepository(db),
                SessionRepository(db),
                email=email,
                password="correct-horse-battery",
                ttl=LIVE,
            )
        async with factory() as db:
            assert await SessionRepository(db).read_valid(token) is not None
            await logout(db, SessionRepository(db), token=token)
        async with factory() as db:
            assert await SessionRepository(db).read_valid(token) is None
    finally:
        async with factory.begin() as cleanup:
            await cleanup.execute(text("DELETE FROM users WHERE email = :e"), {"e": email})


async def test_delete_for_user_removes_only_that_users_sessions(session: AsyncSession) -> None:
    mine = await seed_user(session, "mine@example.com")
    other = await seed_user(session, "other@example.com")
    sessions = SessionRepository(session)
    expires = datetime.now(UTC) + LIVE
    await sessions.create("m1", mine, "c", expires)
    await sessions.create("m2", mine, "c", expires)
    await sessions.create("o1", other, "c", expires)

    await sessions.delete_for_user(mine)

    assert await sessions.read_valid("m1") is None
    assert await sessions.read_valid("m2") is None
    assert await sessions.read_valid("o1") is not None
