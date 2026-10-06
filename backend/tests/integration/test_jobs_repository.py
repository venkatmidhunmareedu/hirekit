"""The jobs repository against Postgres: claim, reclaim, fence, renew and finish (Q1 to Q4)."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.repositories import jobs
from app.worker.errors import LeaseLostError

pytestmark = pytest.mark.integration

LEASE = 180
EXPIRED = timedelta(seconds=-1)


async def seed_role(session: AsyncSession) -> UUID:
    role_id = uuid4()
    await session.execute(
        text("INSERT INTO roles(id, title, job_description) VALUES (:id, 'T', 'JD')"),
        {"id": role_id},
    )
    return role_id


async def seed_job(
    session: AsyncSession,
    role_id: UUID,
    *,
    run_in: timedelta = timedelta(0),
    running_lease_in: timedelta | None = None,
    attempt: int = 0,
) -> tuple[int, UUID]:
    """One process_resume job on a fresh candidate; returns (job id, candidate id).

    `running_lease_in` makes it a running job whose lease expires that long from now.
    """
    candidate_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO candidates(id, role_id, file_name, content_hash, identity_name) "
            "VALUES (:id, :role, 'f.pdf', :hash, 'Jane')"
        ),
        {"id": candidate_id, "role": role_id, "hash": candidate_id.hex * 2},
    )
    job_id = await session.scalar(
        text(
            "INSERT INTO jobs(type, role_id, candidate_id, criteria_version, run_after) "
            "VALUES ('process_resume', :role, :candidate, 1, now() + CAST(:run_in AS interval)) "
            "RETURNING id"
        ),
        {"role": role_id, "candidate": candidate_id, "run_in": run_in},
    )
    assert job_id is not None
    if running_lease_in is not None:
        await session.execute(
            text(
                "UPDATE jobs SET status = 'running', attempt = :a, lease_token = :token, "
                "lease_expires_at = now() + CAST(:lease AS interval) WHERE id = :id"
            ),
            {"a": attempt, "token": uuid4(), "lease": running_lease_in, "id": job_id},
        )
    return job_id, candidate_id


async def row(session: AsyncSession, job_id: int) -> tuple[str, int, UUID | None, str | None]:
    result = await session.execute(
        text("SELECT status, attempt, lease_token, last_error FROM jobs WHERE id = :id"),
        {"id": job_id},
    )
    status, attempt, token, error = result.one()
    return status, attempt, token, error


async def expire(session: AsyncSession, job_id: int) -> None:
    await session.execute(
        text("UPDATE jobs SET lease_expires_at = now() - interval '1 second' WHERE id = :id"),
        {"id": job_id},
    )


async def claimed(session: AsyncSession) -> jobs.Job:
    job = await jobs.claim(session, lease_seconds=LEASE)
    assert job is not None
    return job


async def test_claim_takes_the_oldest_due_queued_job(session: AsyncSession) -> None:
    role = await seed_role(session)
    newer, _ = await seed_job(session, role, run_in=timedelta(minutes=-1))
    older, _ = await seed_job(session, role, run_in=timedelta(hours=-1))

    job = await claimed(session)

    assert job.id == older
    assert (job.type, job.role_id, job.criteria_version, job.attempt) == (
        "process_resume",
        role,
        1,
        1,
    )
    status, _, token, _ = await row(session, older)
    assert (status, token) == ("running", job.lease_token)
    assert (await row(session, newer))[0] == "queued"


async def test_claim_ignores_a_job_whose_run_after_is_in_the_future(
    session: AsyncSession,
) -> None:
    role = await seed_role(session)
    await seed_job(session, role, run_in=timedelta(minutes=1))

    assert await jobs.claim(session, lease_seconds=LEASE) is None


async def test_two_workers_never_claim_the_same_job(engine: AsyncEngine) -> None:
    """ADR-0004: 20 concurrent claimers, 5 jobs, each job taken exactly once."""
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions.begin() as s:
            role = await seed_role(s)
            for _ in range(5):
                await seed_job(s, role)

        async def one() -> int | None:
            async with sessions.begin() as s:
                job = await jobs.claim(s, lease_seconds=LEASE)
                return None if job is None else job.id

        results = await asyncio.gather(*(one() for _ in range(20)))

        won = [r for r in results if r is not None]
        assert len(won) == 5
        assert len(set(won)) == 5
    finally:
        await cleanup(sessions)


async def test_expired_lease_is_reclaimed_and_attempt_increments(session: AsyncSession) -> None:
    role = await seed_role(session)
    job_id, _ = await seed_job(session, role, attempt=1, running_lease_in=EXPIRED)
    _, _, old_token, _ = await row(session, job_id)

    job = await claimed(session)

    assert (job.id, job.attempt) == (job_id, 2)
    assert job.lease_token != old_token


async def test_reclaim_at_attempt_three_fails_the_job_and_the_candidate_instead_of_incrementing(
    session: AsyncSession,
) -> None:
    role = await seed_role(session)
    job_id, candidate = await seed_job(session, role, attempt=3, running_lease_in=EXPIRED)

    assert await jobs.claim(session, lease_seconds=LEASE) is None

    assert await row(session, job_id) == ("failed", 3, None, jobs.LEASE_EXPIRED)
    result = await session.execute(
        text("SELECT processing_status, failure_reason FROM candidates WHERE id = :id"),
        {"id": candidate},
    )
    assert result.one() == ("failed", "Something went wrong. Try again.")


async def test_a_live_lease_is_not_reclaimed(session: AsyncSession) -> None:
    role = await seed_role(session)
    await seed_job(session, role, attempt=1, running_lease_in=timedelta(minutes=1))

    assert await jobs.claim(session, lease_seconds=LEASE) is None


async def test_a_crashed_job_is_reclaimed_before_a_queued_batch_is_claimed(
    session: AsyncSession,
) -> None:
    role = await seed_role(session)
    await seed_job(session, role, run_in=timedelta(hours=-1))
    crashed, _ = await seed_job(session, role, attempt=1, running_lease_in=EXPIRED)

    assert (await claimed(session)).id == crashed


async def test_fenced_write_after_the_lease_expired_and_was_reclaimed_writes_nothing(
    session: AsyncSession,
) -> None:
    """HLD section 7: the first Worker's token is dead once another Worker re-claimed."""
    role = await seed_role(session)
    job_id, _ = await seed_job(session, role)
    first = await claimed(session)
    await expire(session, job_id)
    second = await claimed(session)

    with pytest.raises(LeaseLostError):
        await jobs.fence(session, job_id, first.lease_token)
    with pytest.raises(LeaseLostError):
        await jobs.succeed(session, job_id, first.lease_token)
    with pytest.raises(LeaseLostError):
        await jobs.renew(session, job_id, first.lease_token, lease_seconds=LEASE)

    assert await row(session, job_id) == ("running", 2, second.lease_token, None)
    await jobs.fence(session, job_id, second.lease_token)


async def test_fenced_write_after_cancel_writes_nothing(session: AsyncSession) -> None:
    """AC-US-00-001-4: the Api cancels by clearing the lease; the Worker then finds it lost."""
    role = await seed_role(session)
    job_id, _ = await seed_job(session, role)
    job = await claimed(session)
    await session.execute(
        text(
            "UPDATE jobs SET status = 'cancelled', lease_token = NULL, lease_expires_at = NULL "
            "WHERE id = :id"
        ),
        {"id": job_id},
    )

    with pytest.raises(LeaseLostError):
        await jobs.fence(session, job_id, job.lease_token)
    with pytest.raises(LeaseLostError):
        await jobs.fail(session, job_id, job.lease_token, code="x")

    assert await row(session, job_id) == ("cancelled", 1, None, None)


async def test_finish_is_conditional_on_the_lease_token(session: AsyncSession) -> None:
    role = await seed_role(session)
    job_id, _ = await seed_job(session, role)
    job = await claimed(session)

    with pytest.raises(LeaseLostError):
        await jobs.succeed(session, job_id, uuid4())
    assert (await row(session, job_id))[0] == "running"

    await jobs.succeed(session, job_id, job.lease_token)
    assert await row(session, job_id) == ("succeeded", 1, None, None)


async def test_reschedule_requeues_with_the_backoff_and_the_error_code(
    session: AsyncSession,
) -> None:
    role = await seed_role(session)
    job_id, _ = await seed_job(session, role)
    job = await claimed(session)
    later = datetime.now(UTC) + timedelta(minutes=5)

    await jobs.reschedule(session, job_id, job.lease_token, run_after=later, code="rate_limited")

    assert await row(session, job_id) == ("queued", 1, None, "rate_limited")
    assert await jobs.claim(session, lease_seconds=LEASE) is None
    stored = await session.scalar(text("SELECT run_after FROM jobs WHERE id = :id"), {"id": job_id})
    assert stored == later


async def test_fail_and_stale_end_the_job_and_clear_the_lease(session: AsyncSession) -> None:
    role = await seed_role(session)
    failing, _ = await seed_job(session, role)
    staling, _ = await seed_job(session, role)
    first = await claimed(session)
    second = await claimed(session)

    await jobs.fail(session, first.id, first.lease_token, code="budget_reached")
    await jobs.mark_stale(session, second.id, second.lease_token)

    assert await row(session, failing) == ("failed", 1, None, "budget_reached")
    assert await row(session, staling) == ("stale", 1, None, None)


async def test_renew_extends_the_lease(session: AsyncSession) -> None:
    role = await seed_role(session)
    job_id, _ = await seed_job(session, role)
    job = await claimed(session)

    await jobs.renew(session, job_id, job.lease_token, lease_seconds=3600)

    expires = await session.scalar(
        text("SELECT lease_expires_at - now() FROM jobs WHERE id = :id"), {"id": job_id}
    )
    assert expires is not None
    assert expires > timedelta(minutes=59)


async def test_every_repository_statement_is_allowed_to_the_worker_role(
    session: AsyncSession,
) -> None:
    """Migration 2 grants: claim, reclaim, renew, fence, finish and the exhausted path."""
    role = await seed_role(session)
    job_id, _ = await seed_job(session, role)
    crashed, _ = await seed_job(session, role, attempt=3, running_lease_in=EXPIRED)
    await session.execute(text("SET LOCAL ROLE hirekit_worker"))

    job = await claimed(session)
    await jobs.renew(session, job_id, job.lease_token, lease_seconds=LEASE)
    await jobs.fence(session, job_id, job.lease_token)
    await jobs.reschedule(
        session, job_id, job.lease_token, run_after=datetime.now(UTC), code="rate_limited"
    )

    assert (await row(session, job_id))[0] == "queued"
    assert (await row(session, crashed))[0] == "failed"


async def test_a_database_that_refuses_a_job_write_raises_instead_of_hiding_it(
    session: AsyncSession,
) -> None:
    """A status outside the CHECK is an error, never a silent lost update."""
    role = await seed_role(session)
    job_id, _ = await seed_job(session, role)
    job = await claimed(session)

    with pytest.raises(DBAPIError, match="chk_jobs_status"):
        async with session.begin_nested():
            await jobs.finish(session, job_id, job.lease_token, status="bogus")


async def cleanup(sessions: async_sessionmaker[AsyncSession]) -> None:
    """The concurrency test commits for real, so it removes what it wrote."""
    async with sessions.begin() as s:
        await s.execute(text("DELETE FROM jobs"))
        await s.execute(text("DELETE FROM candidates"))
        await s.execute(text("DELETE FROM roles"))
