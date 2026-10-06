"""Assignments: which interviewer may see which candidate. Writes join the caller's transaction.

Raw SQL because no Assignment or Feedback model exists yet (N-135).
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.candidates.assignment_schemas import CandidateAssignment, MyCandidate

_MINE = text(
    "SELECT c.id AS candidate_id, c.candidate_no, c.role_id, r.title AS role_title, "
    "EXISTS (SELECT 1 FROM feedback f WHERE f.candidate_id = c.id "
    "AND f.interviewer_id = :viewer) AS has_submitted "
    "FROM candidates c JOIN roles r ON r.id = c.role_id "
    "WHERE c.id IN (SELECT candidate_id FROM assignments WHERE user_id = :viewer) "
    "ORDER BY c.candidate_no, c.id LIMIT :n"
)

_FOR_CANDIDATE = text(
    "SELECT a.user_id, u.name FROM assignments a JOIN users u ON u.id = a.user_id "
    "WHERE a.candidate_id = :c ORDER BY u.name, a.user_id"
)


class AssignmentRepository:
    """Assign, remove and list; the interviewer predicate lives in the SQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def candidate_exists(self, candidate_id: uuid.UUID) -> bool:
        """True when the candidate row exists."""
        result = await self._session.execute(
            text("SELECT EXISTS (SELECT 1 FROM candidates WHERE id = :c)"), {"c": candidate_id}
        )
        return bool(result.scalar_one())

    async def user_role(self, user_id: uuid.UUID) -> str | None:
        """The user's role, or None for an unknown user."""
        result = await self._session.execute(
            text("SELECT role FROM users WHERE id = :u"), {"u": user_id}
        )
        return result.scalar_one_or_none()

    async def add(self, candidate_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Insert the pair; a repeat is a no-op."""
        await self._session.execute(
            text(
                "INSERT INTO assignments (candidate_id, user_id) VALUES (:c, :u) "
                "ON CONFLICT DO NOTHING"
            ),
            {"c": candidate_id, "u": user_id},
        )

    async def remove(self, candidate_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete the pair; an absent pair is a no-op."""
        await self._session.execute(
            text("DELETE FROM assignments WHERE candidate_id = :c AND user_id = :u"),
            {"c": candidate_id, "u": user_id},
        )

    async def for_interviewer(self, user_id: uuid.UUID, limit: int) -> list[MyCandidate]:
        """The interviewer's assigned candidates by candidate number, at most `limit`."""
        result = await self._session.execute(_MINE, {"viewer": user_id, "n": limit})
        return [MyCandidate.model_validate(dict(row._mapping)) for row in result]

    async def for_candidate(self, candidate_id: uuid.UUID) -> list[CandidateAssignment]:
        """The interviewers assigned to the candidate, by name."""
        result = await self._session.execute(_FOR_CANDIDATE, {"c": candidate_id})
        return [CandidateAssignment.model_validate(dict(row._mapping)) for row in result]
