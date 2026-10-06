"""Retry and rescore writes: the needs-scoring rule, the open-job check and the job insert.

Methods join the caller's transaction and never commit. Lock order, as everywhere: `roles`, then
`candidates`, then `jobs`. The `jobs` insert is raw SQL because no Job model exists.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.budget import read_spent
from app.db.repositories.uploads import RoleState

# "Needs scoring" (docs/design/api-lld.md 4.5), written out in both queries: no score row at the
# role's current version, or a failed score row at its latest version, or a failed file.
# "Open" is a queued or running process_resume or rescore job.
_CANDIDATE_ROLE: Final = text("SELECT role_id FROM candidates WHERE id = :id")
_ROLE_SHARED: Final = text("SELECT status, criteria_version FROM roles WHERE id = :id FOR SHARE")
_CANDIDATE_LOCK: Final = text(
    """
    SELECT c.id,
      (c.processing_status = 'failed'
        OR NOT EXISTS (SELECT 1 FROM scores s WHERE s.candidate_id = c.id
                       AND s.criteria_version = :version)
        OR EXISTS (SELECT 1 FROM scores s WHERE s.candidate_id = c.id AND s.status = 'failed'
                   AND s.criteria_version = (SELECT max(m.criteria_version) FROM scores m
                                             WHERE m.candidate_id = c.id))) AS needs,
      EXISTS (SELECT 1 FROM jobs j WHERE j.candidate_id = c.id
              AND j.type IN ('process_resume', 'rescore')
              AND j.status IN ('queued', 'running')) AS open_job
    FROM candidates c WHERE c.id = :id FOR UPDATE OF c
    """
)
_ROLE_TARGETS: Final = text(
    """
    SELECT c.id, c.candidate_no,
      EXISTS (SELECT 1 FROM jobs j WHERE j.candidate_id = c.id
              AND j.type IN ('process_resume', 'rescore')
              AND j.status IN ('queued', 'running')) AS open_job
    FROM candidates c
    WHERE c.role_id = :role_id
      AND (c.processing_status = 'failed'
        OR NOT EXISTS (SELECT 1 FROM scores s WHERE s.candidate_id = c.id
                       AND s.criteria_version = :version)
        OR EXISTS (SELECT 1 FROM scores s WHERE s.candidate_id = c.id AND s.status = 'failed'
                   AND s.criteria_version = (SELECT max(m.criteria_version) FROM scores m
                                             WHERE m.candidate_id = c.id)))
    ORDER BY c.candidate_no FOR UPDATE OF c
    """
)
_ENQUEUE: Final = text(
    "INSERT INTO jobs (type, role_id, candidate_id, criteria_version) "
    "VALUES (:type, :role_id, :candidate_id, :version) RETURNING id"
)
_RESET: Final = text(
    "UPDATE candidates SET processing_status = 'queued', failure_reason = NULL, "
    "updated_at = now() WHERE id = :id"
)


@dataclass(frozen=True, slots=True)
class CandidateState:
    """A locked candidate: does it need scoring, and is a scoring job already open."""

    needs_scoring: bool
    open_job: bool


@dataclass(frozen=True, slots=True)
class RescoreTarget:
    """A locked candidate that needs scoring; `open_job` ones are skipped, not failed."""

    candidate_id: uuid.UUID
    candidate_no: int
    open_job: bool


class ScoringJobRepository:
    """Candidates that need scoring and the jobs that score them."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def spent_usd(self) -> Decimal | None:
        """USD spent or reserved so far; None when the budget row is missing."""
        return await read_spent(self._session)

    async def candidate_role_id(self, candidate_id: uuid.UUID) -> uuid.UUID | None:
        """The candidate's role, read without a lock so the role can be locked first."""
        row = (await self._session.execute(_CANDIDATE_ROLE, {"id": candidate_id})).first()
        return None if row is None else row.role_id

    async def lock_role(self, role_id: uuid.UUID) -> RoleState | None:
        """Lock the role FOR SHARE, so it cannot change version until this commits."""
        row = (await self._session.execute(_ROLE_SHARED, {"id": role_id})).first()
        return None if row is None else RoleState(row.status, row.criteria_version)

    async def lock_candidate(
        self, candidate_id: uuid.UUID, criteria_version: int
    ) -> CandidateState | None:
        """Lock the candidate row, then read the rule and the open-job check under that lock."""
        row = (
            await self._session.execute(
                _CANDIDATE_LOCK, {"id": candidate_id, "version": criteria_version}
            )
        ).first()
        return None if row is None else CandidateState(row.needs, row.open_job)

    async def lock_rescore_targets(
        self, role_id: uuid.UUID, criteria_version: int
    ) -> list[RescoreTarget]:
        """Every candidate of the role that needs scoring, locked in candidate_no order."""
        result = await self._session.execute(
            _ROLE_TARGETS, {"role_id": role_id, "version": criteria_version}
        )
        return [RescoreTarget(r.id, r.candidate_no, r.open_job) for r in result]

    async def enqueue(
        self, job_type: str, role_id: uuid.UUID, candidate_id: uuid.UUID, criteria_version: int
    ) -> int:
        """One queued job at the role's current version; returns its id."""
        result = await self._session.execute(
            _ENQUEUE,
            {
                "type": job_type,
                "role_id": role_id,
                "candidate_id": candidate_id,
                "version": criteria_version,
            },
        )
        return int(result.scalar_one())

    async def reset_candidate(self, candidate_id: uuid.UUID) -> None:
        """Back to queued with no failure reason, for a retry."""
        await self._session.execute(_RESET, {"id": candidate_id})
