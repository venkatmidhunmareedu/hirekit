"""Read-only SQL for the comparison view. No query here selects a quote, note or flag column.

An interviewer's queries carry the assignment predicate and see only their own feedback; model
and override scores are masked in SQL until that interviewer has submitted for the candidate.
Each statement is a complete constant, one per viewer type, so none is built from strings.
"""

import uuid
from dataclasses import dataclass
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.visibility import Viewer

_CANDIDATES: Final = text(
    "SELECT c.id, c.candidate_no, c.role_id FROM candidates c WHERE c.id = ANY(:ids)"
)
_CANDIDATES_ASSIGNED: Final = text(
    "SELECT c.id, c.candidate_no, c.role_id FROM candidates c WHERE c.id = ANY(:ids) "
    "AND c.id IN (SELECT a.candidate_id FROM assignments a WHERE a.user_id = :viewer)"
)
_SCORES: Final = text(
    "SELECT s.candidate_id, s.criterion_id, s.model_score, s.override_score "
    "FROM scores s WHERE s.candidate_id = ANY(:ids) "
    "AND s.criteria_version = "
    "(SELECT max(m.criteria_version) FROM scores m WHERE m.candidate_id = s.candidate_id)"
)
_SCORES_ASSIGNED: Final = text(
    "SELECT s.candidate_id, s.criterion_id, "
    "CASE WHEN EXISTS (SELECT 1 FROM feedback f WHERE f.candidate_id = s.candidate_id "
    "AND f.interviewer_id = :viewer) THEN s.model_score END AS model_score, "
    "CASE WHEN EXISTS (SELECT 1 FROM feedback f WHERE f.candidate_id = s.candidate_id "
    "AND f.interviewer_id = :viewer) THEN s.override_score END AS override_score "
    "FROM scores s WHERE s.candidate_id = ANY(:ids) "
    "AND s.candidate_id IN (SELECT a.candidate_id FROM assignments a WHERE a.user_id = :viewer) "
    "AND s.criteria_version = "
    "(SELECT max(m.criteria_version) FROM scores m WHERE m.candidate_id = s.candidate_id)"
)
_FEEDBACK: Final = text(
    "SELECT f.candidate_id, f.interviewer_id, f.criterion_id, f.score, f.comment, f.locked "
    "FROM feedback f WHERE f.candidate_id = ANY(:ids) ORDER BY f.interviewer_id"
)
_FEEDBACK_OWN: Final = text(
    "SELECT f.candidate_id, f.interviewer_id, f.criterion_id, f.score, f.comment, f.locked "
    "FROM feedback f WHERE f.candidate_id = ANY(:ids) AND f.interviewer_id = :viewer "
    "AND f.candidate_id IN (SELECT a.candidate_id FROM assignments a WHERE a.user_id = :viewer) "
    "ORDER BY f.interviewer_id"
)


@dataclass(frozen=True, slots=True)
class CandidateRef:
    id: uuid.UUID
    candidate_no: int
    role_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ScoreCell:
    candidate_id: uuid.UUID
    criterion_id: uuid.UUID
    model_score: int | None
    override_score: int | None


@dataclass(frozen=True, slots=True)
class FeedbackCell:
    candidate_id: uuid.UUID
    interviewer_id: uuid.UUID
    criterion_id: uuid.UUID
    score: int
    comment: str
    locked: bool


class CompareRepository:
    """Candidates, latest-version scores and feedback for a comparison."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def candidates(self, viewer: Viewer, ids: list[uuid.UUID]) -> list[CandidateRef]:
        """The candidates this viewer may see among `ids`; an interviewer's only if assigned."""
        stmt = _CANDIDATES_ASSIGNED if viewer.is_interviewer else _CANDIDATES
        rows = (await self._session.execute(stmt, {"ids": ids, "viewer": viewer.user_id})).all()
        return [CandidateRef(r.id, r.candidate_no, r.role_id) for r in rows]

    async def scores(self, viewer: Viewer, ids: list[uuid.UUID]) -> list[ScoreCell]:
        """Each candidate's scores at its latest criteria version."""
        stmt = _SCORES_ASSIGNED if viewer.is_interviewer else _SCORES
        rows = (await self._session.execute(stmt, {"ids": ids, "viewer": viewer.user_id})).all()
        return [
            ScoreCell(r.candidate_id, r.criterion_id, r.model_score, r.override_score) for r in rows
        ]

    async def feedback(self, viewer: Viewer, ids: list[uuid.UUID]) -> list[FeedbackCell]:
        """All interviewers' feedback for a recruiter, only the viewer's own for an interviewer."""
        stmt = _FEEDBACK_OWN if viewer.is_interviewer else _FEEDBACK
        rows = (await self._session.execute(stmt, {"ids": ids, "viewer": viewer.user_id})).all()
        return [
            FeedbackCell(
                r.candidate_id, r.interviewer_id, r.criterion_id, r.score, r.comment, r.locked
            )
            for r in rows
        ]
