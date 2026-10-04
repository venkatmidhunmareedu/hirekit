"""`seed_users` against Postgres: idempotent, keeps passwords, and the hash signs in."""

from collections.abc import AsyncIterator
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.passwords import verify_password
from app.db.repositories.sessions import SessionRepository
from app.db.repositories.users import UserRepository
from app.domain.auth.service import login
from app.seed import users as seed_module
from app.seed.users import SeedUser, seed_users

pytestmark = pytest.mark.integration


@pytest.fixture
async def unique_users(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[SeedUser, SeedUser]]:
    """Two users with emails unique to this test; deleted afterwards (committed writes)."""
    run = uuid4().hex[:12]
    pair = (
        SeedUser("T Recruiter", f"hk54-{run}-r@hirekit.local", "recruiter", "T_PW_R"),
        SeedUser("T Interviewer", f"hk54-{run}-i@hirekit.local", "interviewer", "T_PW_I"),
    )
    monkeypatch.setattr(seed_module, "USERS", pair)
    try:
        yield pair
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM users WHERE email LIKE :p"), {"p": f"hk54-{run}-%"}
            )


async def _run(
    factory: async_sessionmaker[AsyncSession], env: dict[str, str], reset: bool = False
) -> list[str]:
    async with factory.begin() as session:
        return [o.status for o in await seed_users(session, env, reset=reset)]


async def _hash(factory: async_sessionmaker[AsyncSession], email: str) -> str:
    async with factory() as session:
        return str(
            await session.scalar(
                text("SELECT password_hash FROM users WHERE email = :e"), {"e": email}
            )
        )


async def test_seeded_user_signs_in_and_a_rerun_changes_nothing(
    engine: AsyncEngine, unique_users: tuple[SeedUser, SeedUser]
) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    recruiter, _ = unique_users

    assert await _run(factory, {"T_PW_R": "first-pw-recruiter"}) == ["created", "created"]
    before = await _hash(factory, recruiter.email)
    assert await _run(factory, {"T_PW_R": "other-pw"}) == ["kept", "kept"]
    assert await _hash(factory, recruiter.email) == before

    async with factory() as db:
        token, _csrf, user = await login(
            db,
            UserRepository(db),
            SessionRepository(db),
            email=recruiter.email.upper(),  # lower(email) matching
            password="first-pw-recruiter",
            ttl=timedelta(minutes=1),
        )
        assert user.role == "recruiter"
        async with db.begin():
            await SessionRepository(db).delete(token)


async def test_reset_passwords_replaces_the_hash_without_a_second_row(
    engine: AsyncEngine, unique_users: tuple[SeedUser, SeedUser]
) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    recruiter, _ = unique_users
    await _run(factory, {"T_PW_R": "old-pw"})

    assert await _run(factory, {"T_PW_R": "new-pw"}, reset=True) == ["reset", "reset"]

    assert verify_password(await _hash(factory, recruiter.email), "new-pw")
    async with factory() as session:
        count = await session.scalar(
            text("SELECT count(*) FROM users WHERE lower(email) = :e"), {"e": recruiter.email}
        )
    assert count == 1
