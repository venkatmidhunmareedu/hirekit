"""Feedback rows and their audit events. Writes join the caller's transaction.

The assignment predicate sits inside the INSERT, so an assignment removed between the check and the
write cannot leave feedback behind (api-lld Q17).
"""

import uuid
from dataclasses import dataclass
from typing import Final

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import FeedbackLockedError

_UNIQUE: Final = "feedback_pkey"
_ROWS: Final = text(
    "SELECT f.interviewer_id, f.criterion_id, f.score, f.comment, f.locked, c.name "
    "FROM feedback f JOIN criteria c ON c.id = f.criterion_id "
    "WHERE f.candidate_id = :c AND (CAST(:i AS uuid) IS NULL OR f.interviewer_id = :i) "
    "ORDER BY f.interviewer_id, c.position, f.criterion_id"
)
_INSERT: Final = text(
    "INSERT INTO feedback (candidate_id, interviewer_id, criterion_id, score, comment) "
    "SELECT :c, :i, :cr, :s, :cm WHERE EXISTS "
    "(SELECT 1 FROM assignments WHERE candidate_id = :c AND user_id = :i) "
    "RETURNING criterion_id"
)
_UPDATE: Final = text(
    "UPDATE feedback SET score = :s, comment = :cm, locked = true, updated_at = now() "
    "WHERE candidate_id = :c AND interviewer_id = :i AND criterion_id = :cr"
)
_UNLOCK: Final = text(
    "UPDATE feedback SET locked = false, updated_at = now() "
    "WHERE candidate_id = :c AND interviewer_id = :i AND locked RETURNING criterion_id"
)
_AUDIT_APPROVED: Final = text(
    "INSERT INTO audit_events (candidate_id, actor_id, kind, subject_user_id) "
    "VALUES (:c, :a, 'feedback_edit_approved', :i)"
)
_AUDIT_EDITED: Final = text(
    "INSERT INTO audit_events "
    "(candidate_id, actor_id, kind, criterion_name, old_score, new_score, subject_user_id, "
    "old_comment) VALUES (:c, :i, 'feedback_edited', :n, :os, :ns, :i, :oc)"
)


@dataclass(frozen=True, slots=True)
class StoredFeedback:
    """A feedback row with its criterion's name, for the audit trail."""

    interviewer_id: uuid.UUID
    criterion_id: uuid.UUID
    score: int
    comment: str
    locked: bool
    criterion_name: str


class FeedbackRepository:
    """Feedback by (candidate, interviewer); the viewer decides whose rows are read."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def candidate_role(self, candidate_id: uuid.UUID) -> uuid.UUID | None:
        """The role of the candidate, or None when there is no such candidate."""
        result = await self._session.execute(
            text("SELECT role_id FROM candidates WHERE id = :c"), {"c": candidate_id}
        )
        return result.scalar_one_or_none()

    async def is_assigned(self, candidate_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """True when the interviewer is assigned this candidate."""
        result = await self._session.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM assignments WHERE candidate_id = :c AND user_id = :u)"
            ),
            {"c": candidate_id, "u": user_id},
        )
        return bool(result.scalar_one())

    async def rows(
        self, candidate_id: uuid.UUID, interviewer_id: uuid.UUID | None
    ) -> list[StoredFeedback]:
        """One interviewer's rows, or every interviewer's when `interviewer_id` is None."""
        result = await self._session.execute(_ROWS, {"c": candidate_id, "i": interviewer_id})
        return [StoredFeedback(*row) for row in result.all()]

    async def insert_all(
        self,
        candidate_id: uuid.UUID,
        interviewer_id: uuid.UUID,
        items: list[tuple[uuid.UUID, int, str]],
    ) -> bool:
        """Insert one row per item, locked. False when the interviewer is no longer assigned.

        A repeat submit hits `feedback_pkey` and becomes `FeedbackLockedError`.
        """
        try:
            for criterion_id, score, comment in items:
                result = await self._session.execute(
                    _INSERT,
                    {
                        "c": candidate_id,
                        "i": interviewer_id,
                        "cr": criterion_id,
                        "s": score,
                        "cm": comment,
                    },
                )
                if result.first() is None:
                    return False
        except IntegrityError as exc:
            if _UNIQUE in str(exc.orig):
                raise FeedbackLockedError("feedback is already submitted") from exc
            raise
        return True

    async def save_edit(
        self,
        candidate_id: uuid.UUID,
        interviewer_id: uuid.UUID,
        before: list[StoredFeedback],
        items: dict[uuid.UUID, tuple[int, str]],
    ) -> None:
        """Overwrite the rows, lock them again, and audit each change with the old values."""
        for old in before:
            score, comment = items[old.criterion_id]
            await self._session.execute(
                _UPDATE,
                {
                    "c": candidate_id,
                    "i": interviewer_id,
                    "cr": old.criterion_id,
                    "s": score,
                    "cm": comment,
                },
            )
            if (score, comment) != (old.score, old.comment):
                await self._session.execute(
                    _AUDIT_EDITED,
                    {
                        "c": candidate_id,
                        "i": interviewer_id,
                        "n": old.criterion_name,
                        "os": old.score,
                        "ns": score,
                        "oc": old.comment,
                    },
                )

    async def unlock(
        self, candidate_id: uuid.UUID, interviewer_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        """Unlock the interviewer's rows and audit it; a repeat on unlocked rows writes nothing."""
        result = await self._session.execute(_UNLOCK, {"c": candidate_id, "i": interviewer_id})
        if result.first() is not None:
            await self._session.execute(
                _AUDIT_APPROVED, {"c": candidate_id, "a": actor_id, "i": interviewer_id}
            )
