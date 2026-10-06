"""The real `seed/` tree loads into an empty database once and a second run adds nothing."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from scripts.build_seed_resumes import DOCX_MEDIA_TYPE
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from app.seed.__main__ import SeedResult, run_seed

pytestmark = pytest.mark.integration

SEED = Path(__file__).resolve().parents[3] / "seed"
TITLES = ["Backend Engineer", "Customer Support Lead"]


@pytest.fixture
async def factory(engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """One outer transaction, always rolled back; each `begin()` is a savepoint."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield _bound(connection)
        finally:
            await transaction.rollback()


def _bound(connection: AsyncConnection) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


async def _scalar(factory: async_sessionmaker[AsyncSession], sql: str, **params: object) -> int:
    async with factory() as session:
        return int(await session.scalar(text(sql), params) or 0)


async def test_real_seed_creates_roles_and_candidates_once(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory.begin() as session:  # rolled back with the rest: a seeded dev database
        await session.execute(
            text(
                "DELETE FROM candidates "
                "WHERE role_id IN (SELECT id FROM roles WHERE title = ANY(:t))"
            ),
            {"t": TITLES},
        )
        await session.execute(text("DELETE FROM roles WHERE title = ANY(:t)"), {"t": TITLES})
    jobs_before = await _scalar(factory, "SELECT count(*) FROM jobs")

    first = await run_seed(factory, SEED)
    second = await run_seed(factory, SEED)

    assert first == SeedResult(roles_created=2, candidates_created=40)
    assert second == SeedResult(roles_created=0, candidates_created=0)
    approved = "SELECT count(*) FROM roles WHERE title = ANY(:t) AND status = 'approved'"
    assert await _scalar(factory, approved, t=TITLES) == 2
    per_role = (
        "SELECT count(*) FROM candidates c JOIN roles r ON r.id = c.role_id WHERE r.title = :t"
    )
    for title in TITLES:
        assert await _scalar(factory, per_role, t=title) == 20
    by_media = "SELECT count(*) FROM resume_files WHERE media_type = :m"
    for media in ("application/pdf", DOCX_MEDIA_TYPE):
        assert await _scalar(factory, by_media, m=media) > 0
    assert await _scalar(factory, "SELECT count(*) FROM jobs") == jobs_before
