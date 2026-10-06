"""`run_seed` loads a seed tree and writes roles then candidates in one transaction."""

import csv
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from scripts.build_seed_resumes import build
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from app.seed.__main__ import SeedResult, run_seed
from app.seed.data import Expected, SeedError

pytestmark = pytest.mark.integration

EXPECTED = Expected(roles=2, resumes=4, per_role=2, pairs=1)
RESUMES = ("cmda-01", "cmda-02", "cmdb-01", "cmdb-02")
COUNT_ROLES = "SELECT count(*) FROM roles WHERE title LIKE 'Seed Cmd %'"


def _role_md(title: str) -> str:
    levels = "\n".join(f"{n}: level {n}" for n in range(5))
    return (
        f"# {title}\n\n## Job description\nBuild things.\n\n"
        f"## Criterion: Python\nkind: must_have\nweight: 3\n{levels}\n"
    )


def _csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "roles").mkdir()
    (tmp_path / "resumes").mkdir()
    for slug, title in (("cmda", "Seed Cmd Alpha"), ("cmdb", "Seed Cmd Beta")):
        (tmp_path / "roles" / f"{slug}.md").write_text(_role_md(title))
    for resume_id in RESUMES:
        body = f"Resume {resume_id}\nPython for {resume_id}."
        (tmp_path / "resumes" / f"{resume_id}.txt").write_text(body)
        (tmp_path / "resumes" / f"{resume_id}.pdf").write_bytes(build(body, "single", "pdf"))
    _csv(
        tmp_path / "labels.csv",
        [["resume_id", "criterion", "label", "rationale"]]
        + [[resume_id, "Python", "3", "ok"] for resume_id in RESUMES],
    )
    _csv(
        tmp_path / "pairs.csv",
        [
            ["base_id", "swap_id", "origin_pair", "signals_swapped"],
            ["cmda-01", "cmda-02", "p1", "name"],
        ],
    )
    return tmp_path


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


async def _count(factory: async_sessionmaker[AsyncSession], sql: str) -> int:
    async with factory() as session:
        return int(await session.scalar(text(sql)) or 0)


async def test_first_run_creates_and_second_run_creates_nothing(
    factory: async_sessionmaker[AsyncSession], root: Path
) -> None:
    first = await run_seed(factory, root, EXPECTED)
    second = await run_seed(factory, root, EXPECTED)

    assert first == SeedResult(roles_created=2, candidates_created=4)
    assert second == SeedResult(roles_created=0, candidates_created=0)


async def test_a_broken_seed_tree_raises_and_writes_nothing(
    factory: async_sessionmaker[AsyncSession], root: Path
) -> None:
    _csv(
        root / "labels.csv",
        [["resume_id", "criterion", "label", "rationale"]]
        + [[resume_id, "Rust", "3", "ok"] for resume_id in RESUMES],
    )

    with pytest.raises(SeedError, match=r"labels\.csv"):
        await run_seed(factory, root, EXPECTED)

    assert await _count(factory, COUNT_ROLES) == 0


async def test_a_failure_after_the_roles_rolls_the_roles_back(
    factory: async_sessionmaker[AsyncSession], root: Path
) -> None:
    (root / "resumes" / "cmdb-02.pdf").unlink()

    with pytest.raises(ValueError, match="cmdb-02"):
        await run_seed(factory, root, EXPECTED)

    assert await _count(factory, COUNT_ROLES) == 0
