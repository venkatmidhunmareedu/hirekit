"""Lock order (docs/design/worker-lld.md section 5): the role first, then the job."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.repositories import jobs, worker_writes
from app.db.repositories.worker_writes import ScoreRow
from app.worker.context import JobContext
from tests.integration.test_jobs_repository import cleanup, seed_job
from tests.integration.test_worker_writes import seed_approved_role

pytestmark = pytest.mark.integration

WAIT_SECONDS = 10
LOCK_WAIT = "SELECT 1 FROM pg_stat_activity WHERE pid = :pid AND wait_event_type = 'Lock'"


async def test_a_criteria_edit_and_a_scoring_result_write_never_deadlock(
    engine: AsyncEngine,
) -> None:
    """The edit holds the role and wants the job; the write must not do the reverse."""
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    edit_has_role = asyncio.Event()
    writer_started = asyncio.Event()
    writer_pid: list[int] = []

    async def claimed_job() -> jobs.Job:
        async with sessions.begin() as s:
            role, _ = await seed_approved_role(s)
            await seed_job(s, role)
            job = await jobs.claim(s, lease_seconds=180)
        assert job is not None
        return job

    try:
        job = await claimed_job()
        async with sessions.begin() as s:
            criterion = await s.scalar(
                text("SELECT id FROM criteria WHERE role_id = :r LIMIT 1"), {"r": job.role_id}
            )
            candidate = job.candidate_id
        assert criterion is not None
        assert candidate is not None

        @asynccontextmanager
        async def worker_transaction() -> AsyncIterator[AsyncSession]:
            async with sessions.begin() as s:
                await s.execute(text("SET LOCAL lock_timeout = '10s'"))
                writer_pid.append(int(await s.scalar(text("SELECT pg_backend_pid()")) or 0))
                writer_started.set()
                yield s

        async def criteria_edit() -> None:
            """The Api's order: lock the role, change it, then lock the job rows."""
            async with sessions.begin() as s, asyncio.timeout(WAIT_SECONDS):
                await s.execute(text("SET LOCAL lock_timeout = '10s'"))
                await s.execute(
                    text("SELECT id FROM roles WHERE id = :r FOR UPDATE"), {"r": job.role_id}
                )
                edit_has_role.set()
                await writer_started.wait()
                async with sessions.begin() as watcher:
                    for _ in range(WAIT_SECONDS * 50):
                        if await watcher.scalar(text(LOCK_WAIT), {"pid": writer_pid[0]}):
                            break
                        await asyncio.sleep(0.02)
                await s.execute(
                    text("UPDATE roles SET criteria_version = criteria_version + 1 WHERE id = :r"),
                    {"r": job.role_id},
                )
                await s.execute(
                    text("SELECT id FROM jobs WHERE role_id = :r ORDER BY id FOR UPDATE"),
                    {"r": job.role_id},
                )

        async def scoring_write() -> bool:
            await edit_has_role.wait()
            ctx = JobContext(job, worker_transaction, jobs, 180)
            async with ctx.fenced() as s:
                return await worker_writes.write_scores(
                    s,
                    role_id=job.role_id,
                    criteria_version=job.criteria_version,
                    candidate_id=candidate,
                    scores=[ScoreRow(criterion, "scored", 3, "built payments", None)],
                )

        outcomes = await asyncio.gather(criteria_edit(), scoring_write(), return_exceptions=True)

        assert not [o for o in outcomes if isinstance(o, BaseException)], outcomes
        assert outcomes[1] is False  # the edit bumped the version first, so the write is stale
    finally:
        await cleanup(sessions)
