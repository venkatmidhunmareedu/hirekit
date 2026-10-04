"""Upload writes: a candidate, its file and its job, inside the caller's transaction.

Lock order, the same as the Worker's: `roles`, then `candidates`, then `jobs`. The `jobs` insert
is raw SQL because no Job model exists; column defaults give status queued and a 30 minute deadline.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Candidate, ResumeFile
from app.db.repositories.budget import read_spent

_ROLE_SHARED: Final = text("SELECT status, criteria_version FROM roles WHERE id = :id FOR SHARE")
_ENQUEUE: Final = text(
    "INSERT INTO jobs (type, role_id, candidate_id, criteria_version) "
    "VALUES ('process_resume', :role_id, :candidate_id, :criteria_version)"
)


@dataclass(frozen=True, slots=True)
class RoleState:
    """The locked role as an upload sees it."""

    status: str
    criteria_version: int


class UploadRepository:
    """Candidates, resume files and process_resume jobs for one upload."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def spent_usd(self) -> Decimal | None:
        """USD spent or reserved so far; None when the budget row is missing."""
        return await read_spent(self._session)

    async def lock_role(self, role_id: uuid.UUID) -> RoleState | None:
        """Lock the role FOR SHARE, so it cannot go back to Draft until this file commits."""
        row = (await self._session.execute(_ROLE_SHARED, {"id": role_id})).first()
        return None if row is None else RoleState(row.status, row.criteria_version)

    async def find_duplicate(
        self, role_id: uuid.UUID, content_hash: str
    ) -> tuple[uuid.UUID, int] | None:
        """The earliest candidate of this role with the same hash: (id, candidate_no)."""
        row = (
            await self._session.execute(
                select(Candidate.id, Candidate.candidate_no)
                .where(Candidate.role_id == role_id, Candidate.content_hash == content_hash)
                .order_by(Candidate.created_at, Candidate.id)
                .limit(1)
            )
        ).first()
        return None if row is None else (row.id, row.candidate_no)

    async def insert_candidate(
        self,
        role_id: uuid.UUID,
        file_name: str,
        content_hash: str,
        duplicate_of_id: uuid.UUID | None,
    ) -> tuple[uuid.UUID, int]:
        """Insert a queued candidate; returns (id, candidate_no)."""
        row = (
            await self._session.execute(
                insert(Candidate)
                .values(
                    role_id=role_id,
                    file_name=file_name,
                    content_hash=content_hash,
                    duplicate_of_id=duplicate_of_id,
                )
                .returning(Candidate.id, Candidate.candidate_no)
            )
        ).one()
        return row.id, row.candidate_no

    async def insert_file(self, candidate_id: uuid.UUID, media_type: str, content: bytes) -> None:
        """Store the uploaded bytes until extraction succeeds."""
        await self._session.execute(
            insert(ResumeFile).values(
                candidate_id=candidate_id, media_type=media_type, content=content
            )
        )

    async def enqueue_process_resume(
        self, role_id: uuid.UUID, candidate_id: uuid.UUID, criteria_version: int
    ) -> None:
        """One process_resume job at the role's current criteria version."""
        await self._session.execute(
            _ENQUEUE,
            {
                "role_id": role_id,
                "candidate_id": candidate_id,
                "criteria_version": criteria_version,
            },
        )
