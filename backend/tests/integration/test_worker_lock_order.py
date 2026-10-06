"""Lock order (docs/design/worker-lld.md section 5): the role first, then the job."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.repositories import jobs, worker_writes
from app.db.repositories.worker_writes import NewQuestion, ScoreRow
from app.worker.context import JobContext
from app.worker.errors import LeaseLostError
from tests.integration.test_jobs_repository import cleanup, seed_job
from tests.integration.test_worker_writes import seed_approved_role

pytestmark = pytest.mark.integration

WAIT_SECONDS = 10
KIT_FENCE = {"lock_open_jobs": True}
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


CANCEL_JOB = (
    "UPDATE jobs SET status = 'cancelled', lease_token = NULL, lease_expires_at = NULL "
    "WHERE id = :i"
)
RECLAIM_JOB = "UPDATE jobs SET lease_token = gen_random_uuid() WHERE id = :i"
KIT_JOB = (
    "INSERT INTO jobs(type, role_id, criteria_version, status, attempt, lease_token, "
    "lease_expires_at) VALUES ('generate_kit', :r, 1, 'running', 1, :t, "
    "now() + interval '3 minutes') RETURNING id"
)


async def seed_kit_job(
    sessions: async_sessionmaker[AsyncSession],
) -> tuple[jobs.Job, UUID, int]:
    """An approved role with a running resume job (low id) and a running `generate_kit` (high id).

    Returns the kit job, a criterion of the role and the resume job's id.
    """
    async with sessions.begin() as s:
        role, criteria = await seed_approved_role(s)
        other, _ = await seed_job(s, role, running_lease_in=timedelta(minutes=3))
        token = uuid4()
        job_id = await s.scalar(text(KIT_JOB), {"r": role, "t": token})
        assert job_id is not None
        assert job_id > other
    job = jobs.Job(job_id, "generate_kit", role, None, None, 1, 1, datetime.now(UTC), token)
    return job, criteria[0], other


def kit_questions(criterion: UUID) -> list[NewQuestion]:
    return [NewQuestion(criterion, 1, "Q?", "strong", "weak")]


async def test_a_kit_write_locks_the_open_jobs_in_ascending_id_and_never_deadlocks(
    engine: AsyncEngine,
) -> None:
    """Another transaction holds the low id and wants the high one, as a cancel or a second
    kit path would; the kit job must not hold its own (higher) row while it waits for the low one.
    """
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    other_has_low = asyncio.Event()
    kit_pid: list[int] = []
    kit_inside = asyncio.Event()

    @asynccontextmanager
    async def kit_transaction() -> AsyncIterator[AsyncSession]:
        async with sessions.begin() as s:
            await s.execute(text("SET LOCAL lock_timeout = '5s'"))
            kit_pid.append(int(await s.scalar(text("SELECT pg_backend_pid()")) or 0))
            yield s

    try:
        job, criterion, low = await seed_kit_job(sessions)

        async def other_transaction() -> None:
            async with sessions.begin() as s, asyncio.timeout(WAIT_SECONDS):
                await s.execute(text("SET LOCAL lock_timeout = '5s'"))
                await s.execute(text("SELECT id FROM jobs WHERE id = :i FOR UPDATE"), {"i": low})
                other_has_low.set()
                async with sessions.begin() as watcher:
                    while not kit_inside.is_set():  # the kit job got through, or queues behind us
                        if kit_pid and await watcher.scalar(text(LOCK_WAIT), {"pid": kit_pid[0]}):
                            break
                        await asyncio.sleep(0.02)
                await s.execute(
                    text("SELECT id FROM jobs WHERE role_id = :r ORDER BY id FOR UPDATE"),
                    {"r": job.role_id},
                )

        async def kit_write() -> bool:
            await other_has_low.wait()
            ctx = JobContext(job, kit_transaction, jobs, 180)
            async with ctx.fenced(**KIT_FENCE) as s:
                kit_inside.set()
                return await worker_writes.replace_kit(
                    s,
                    role_id=job.role_id,
                    criteria_version=1,
                    questions=kit_questions(criterion),
                )

        outcomes = await asyncio.gather(other_transaction(), kit_write(), return_exceptions=True)

        assert list(outcomes) == [None, True], outcomes
    finally:
        await cleanup(sessions)


async def test_a_cancelled_or_reclaimed_kit_job_writes_nothing(engine: AsyncEngine) -> None:
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        for change in (CANCEL_JOB, RECLAIM_JOB):
            job, criterion, _ = await seed_kit_job(sessions)
            async with sessions.begin() as s:
                await s.execute(text(change), {"i": job.id})
            ctx = JobContext(job, sessions.begin, jobs, 180)

            with pytest.raises(LeaseLostError):
                async with ctx.fenced(**KIT_FENCE) as s:
                    await worker_writes.replace_kit(
                        s,
                        role_id=job.role_id,
                        criteria_version=1,
                        questions=kit_questions(criterion),
                    )

            async with sessions.begin() as s:
                kit = await s.scalar(
                    text("SELECT count(*) FROM interview_kits WHERE role_id = :r"),
                    {"r": job.role_id},
                )
                questions = await s.scalar(
                    text("SELECT count(*) FROM questions WHERE role_id = :r"), {"r": job.role_id}
                )
            assert (kit, questions) == (0, 0)
    finally:
        await cleanup(sessions)
