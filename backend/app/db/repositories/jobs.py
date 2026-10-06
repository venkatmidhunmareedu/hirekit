"""All SQL on `jobs`: claim, reclaim, renew, fence, finish, reschedule, fail, stale.

Methods take the caller's `AsyncSession` and never commit; the loop and `JobContext` own the
transactions (docs/design/worker-lld.md section 5, Q1 to Q4). Lock order is `jobs`, then
`candidates`. Every write after the claim is conditional on the lease token, so a Worker whose
lease was lost writes nothing and finds out through `LeaseLostError`.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.worker.errors import LeaseLostError
from app.worker.outcome import SOMETHING_WENT_WRONG
from app.worker.policy import MAX_ATTEMPTS

LEASE_EXPIRED: Final = "lease_expired"
LEASE_LOST: Final = "The job lease is gone"


@dataclass(frozen=True, slots=True)
class Job:
    """A claimed job: ids and one integer, no text (tenet 7)."""

    id: int
    type: str
    role_id: UUID
    candidate_id: UUID | None
    question_id: UUID | None
    criteria_version: int
    attempt: int
    deadline_at: datetime
    lease_token: UUID


async def claim(session: AsyncSession, *, lease_seconds: int) -> Job | None:
    """Q2 then Q1: take an expired lease, else the oldest due queued job; None if neither.

    An expired lease whose job already used every attempt is failed instead of re-leased,
    together with its candidate, and the search goes on. Two sessions never take the same row:
    both selects are `FOR UPDATE SKIP LOCKED`.
    """
    lease = timedelta(seconds=lease_seconds)
    while True:
        row = (
            await session.execute(
                text(
                    "SELECT id, attempt, candidate_id, type FROM jobs "
                    "WHERE status = 'running' AND lease_expires_at < now() "
                    "ORDER BY lease_expires_at, id LIMIT 1 FOR UPDATE SKIP LOCKED"
                )
            )
        ).first()
        if row is None:
            break
        if row.attempt >= MAX_ATTEMPTS:
            await _fail_exhausted(session, row.id, row.type, row.candidate_id)
            continue
        return await _lease(session, row.id, lease)
    queued = await session.scalar(
        text(
            "SELECT id FROM jobs WHERE status = 'queued' AND run_after <= now() "
            "ORDER BY run_after, id LIMIT 1 FOR UPDATE SKIP LOCKED"
        )
    )
    if queued is None:
        return None
    return await _lease(session, queued, lease)


async def _lease(session: AsyncSession, job_id: int, lease: timedelta) -> Job:
    row = (
        await session.execute(
            text(
                "UPDATE jobs SET status = 'running', attempt = attempt + 1, "
                "lease_token = :token, lease_expires_at = now() + CAST(:lease AS interval), "
                "updated_at = now() WHERE id = :id RETURNING id, type, role_id, candidate_id, "
                "question_id, criteria_version, attempt, deadline_at, lease_token"
            ),
            {"id": job_id, "token": uuid4(), "lease": lease},
        )
    ).one()
    return Job(*row)


async def _fail_exhausted(
    session: AsyncSession, job_id: int, job_type: str, candidate_id: UUID | None
) -> None:
    """A crashed job at its last attempt: dead-letter it and fail a resume's candidate."""
    await session.execute(
        text(
            "UPDATE jobs SET status = 'failed', last_error = :code, lease_token = NULL, "
            "lease_expires_at = NULL, updated_at = now() WHERE id = :id"
        ),
        {"id": job_id, "code": LEASE_EXPIRED},
    )
    if job_type == "process_resume":
        await session.execute(
            text(
                "UPDATE candidates SET processing_status = 'failed', failure_reason = :reason, "
                "updated_at = now() WHERE id = :candidate"
            ),
            {"candidate": candidate_id, "reason": SOMETHING_WENT_WRONG},
        )


async def fence(session: AsyncSession, job_id: int, lease_token: UUID) -> None:
    """Q3: lock the job row if this Worker still holds it; else raise `LeaseLostError`."""
    found = await session.scalar(
        text(
            "SELECT id FROM jobs WHERE id = :id AND lease_token = :token "
            "AND status = 'running' FOR UPDATE"
        ),
        {"id": job_id, "token": lease_token},
    )
    if found is None:
        raise LeaseLostError(LEASE_LOST)


async def renew(
    session: AsyncSession, job_id: int, lease_token: UUID, *, lease_seconds: int
) -> None:
    """Q3b: push the lease out; zero rows means it is gone, so raise `LeaseLostError`."""
    result = await session.execute(
        text(
            "UPDATE jobs SET lease_expires_at = now() + CAST(:lease AS interval), "
            "updated_at = now() WHERE id = :id AND lease_token = :token AND status = 'running' "
            "RETURNING id"
        ),
        {"id": job_id, "token": lease_token, "lease": timedelta(seconds=lease_seconds)},
    )
    if result.first() is None:
        raise LeaseLostError(LEASE_LOST)


async def finish(
    session: AsyncSession,
    job_id: int,
    lease_token: UUID,
    *,
    status: str,
    run_after: datetime | None = None,
    last_error: str | None = None,
) -> None:
    """Q4: end the attempt and clear the lease, only while `lease_token` still matches.

    `run_after` keeps its value when None. Raises `LeaseLostError` when no row matched.
    """
    result = await session.execute(
        text(
            "UPDATE jobs SET status = :status, run_after = COALESCE(:run_after, run_after), "
            "last_error = :error, lease_token = NULL, lease_expires_at = NULL, "
            "updated_at = now() WHERE id = :id AND lease_token = :token RETURNING id"
        ),
        {
            "id": job_id,
            "token": lease_token,
            "status": status,
            "run_after": run_after,
            "error": last_error,
        },
    )
    if result.first() is None:
        raise LeaseLostError(LEASE_LOST)


async def succeed(session: AsyncSession, job_id: int, lease_token: UUID) -> None:
    await finish(session, job_id, lease_token, status="succeeded")


async def reschedule(
    session: AsyncSession, job_id: int, lease_token: UUID, *, run_after: datetime, code: str
) -> None:
    """Put the job back to queued at `run_after`, with the error code of the failed attempt."""
    await finish(
        session, job_id, lease_token, status="queued", run_after=run_after, last_error=code
    )


async def fail(session: AsyncSession, job_id: int, lease_token: UUID, *, code: str) -> None:
    """Dead-letter the job."""
    await finish(session, job_id, lease_token, status="failed", last_error=code)


async def mark_stale(session: AsyncSession, job_id: int, lease_token: UUID) -> None:
    """The criteria or role changed since enqueue: end the job as stale."""
    await finish(session, job_id, lease_token, status="stale")
