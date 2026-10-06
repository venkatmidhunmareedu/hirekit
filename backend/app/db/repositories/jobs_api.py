"""The Api's SQL on `jobs`: enqueue a proposal, read, cancel, and the queue view.

Methods join the caller's transaction and never commit. The Api may write only `status`,
`lease_token`, `lease_expires_at` and `updated_at` on an existing job (migration 0002), so a
cancel cannot touch `last_error`. Claim, fence and finish belong to the Worker (`jobs.py`).
Lock order: `roles`, then `jobs`, then `candidates`.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.budget import read_spent

CANCEL_REASON: Final = "Cancelled by a recruiter"


@dataclass(frozen=True, slots=True)
class JobView:
    """A job as the API shows it."""

    id: int
    type: str
    status: str
    role_id: UUID
    candidate_no: int | None
    criteria_version: int
    attempt: int
    last_error: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class QueueRow:
    """A candidate with its latest scoring job, if any."""

    candidate_id: UUID
    candidate_no: int
    processing_status: str
    failure_reason: str | None
    job: JobView | None


def _job(row: Row[tuple[object, ...]], prefix: str = "") -> JobView:
    m = row._mapping
    return JobView(
        m[f"{prefix}id"],
        m[f"{prefix}type"],
        m[f"{prefix}status"],
        m["role_id"],
        m["job_candidate_no" if prefix else "candidate_no"],
        m["criteria_version"],
        m["attempt"],
        m["last_error"],
        m["created_at"],
    )


class JobsApiRepository:
    """Jobs for the Api."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def spent(self) -> Decimal | None:
        """USD spent or reserved so far, or None when there is no budget row."""
        return await read_spent(self._session)

    async def enqueue_propose(self, role_id: UUID, criteria_version: int) -> int | None:
        """Insert a queued propose_criteria job; None when one is already open for the role."""
        job_id: int | None = await self._session.scalar(
            text(
                "INSERT INTO jobs(type, role_id, criteria_version) "
                "VALUES ('propose_criteria', :role, :version) "
                "ON CONFLICT (role_id, type) WHERE candidate_id IS NULL AND question_id IS NULL "
                "AND status IN ('queued', 'running') DO NOTHING RETURNING id"
            ),
            {"role": role_id, "version": criteria_version},
        )
        return job_id

    async def get(self, job_id: int) -> JobView | None:
        """The job with its candidate number, or None."""
        row = (
            await self._session.execute(
                text(
                    "SELECT j.id, j.type, j.status, j.role_id, c.candidate_no, "
                    "j.criteria_version, j.attempt, j.last_error, j.created_at FROM jobs j "
                    "LEFT JOIN candidates c ON c.id = j.candidate_id WHERE j.id = :id"
                ),
                {"id": job_id},
            )
        ).first()
        return None if row is None else _job(row)

    async def cancel(self, job_id: int) -> bool:
        """Cancel a queued or running job and drop its lease; False when it is not open.

        A cancelled process_resume job also fails its candidate with a plain reason (the same
        columns `worker_writes.set_status` writes; that module is Worker-side, so the Api
        does not import it). A rescore job leaves the candidate as it was.
        """
        row = (
            await self._session.execute(
                text(
                    "UPDATE jobs SET status = 'cancelled', lease_token = NULL, "
                    "lease_expires_at = NULL, updated_at = now() "
                    "WHERE id = :id AND status IN ('queued', 'running') "
                    "RETURNING type, candidate_id"
                ),
                {"id": job_id},
            )
        ).first()
        if row is None:
            return False
        if row.type == "process_resume" and row.candidate_id is not None:
            await self._session.execute(
                text(
                    "UPDATE candidates SET processing_status = 'failed', "
                    "failure_reason = :reason, updated_at = now() WHERE id = :id"
                ),
                {"id": row.candidate_id, "reason": CANCEL_REASON},
            )
        return True

    async def queue(self, role_id: UUID, limit: int) -> list[QueueRow]:
        """Newest candidates first, each with its latest process_resume or rescore job."""
        rows = (
            await self._session.execute(
                text(
                    "SELECT c.id AS candidate_id, c.candidate_no AS job_candidate_no, "
                    "c.processing_status::text AS processing_status, c.failure_reason, "
                    "j.id AS job_id, j.type AS job_type, j.status AS job_status, j.role_id, "
                    "j.criteria_version, j.attempt, j.last_error, j.created_at "
                    "FROM candidates c LEFT JOIN LATERAL ("
                    "SELECT * FROM jobs WHERE candidate_id = c.id "
                    "AND type IN ('process_resume', 'rescore') ORDER BY id DESC LIMIT 1) j ON true "
                    "WHERE c.role_id = :role ORDER BY c.candidate_no DESC LIMIT :limit"
                ),
                {"role": role_id, "limit": limit},
            )
        ).all()
        return [
            QueueRow(
                r.candidate_id,
                r.job_candidate_no,
                r.processing_status,
                r.failure_reason,
                None if r.job_id is None else _job(r, "job_"),
            )
            for r in rows
        ]

    async def open_counts(self, role_id: UUID) -> tuple[int, int]:
        """(queued, running) scoring jobs of the role."""
        row = (
            await self._session.execute(
                text(
                    "SELECT count(*) FILTER (WHERE status = 'queued') AS waiting, "
                    "count(*) FILTER (WHERE status = 'running') AS running FROM jobs "
                    "WHERE role_id = :role AND type IN ('process_resume', 'rescore') "
                    "AND status IN ('queued', 'running')"
                ),
                {"role": role_id},
            )
        ).one()
        return row.waiting, row.running
