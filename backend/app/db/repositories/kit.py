"""Kit SQL: the header, its questions, and the two kit jobs. Writes join the caller's transaction.

An enqueue is `INSERT ... ON CONFLICT DO NOTHING RETURNING id`: the partial unique indexes on `jobs`
refuse a second open job, and None means one is already open (no aborted transaction to unwind).
Lock order is `roles`, then `jobs`, as everywhere (worker-lld section 5).
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.budget import read_spent
from app.db.repositories.uploads import RoleState

_ROLE_SHARED: Final = text("SELECT status, criteria_version FROM roles WHERE id = :id FOR SHARE")
_QUESTIONS: Final = text(
    "SELECT id, criterion_id, question_text, strong_answer, weak_answer, position "
    "FROM questions WHERE role_id = :role_id "
    "ORDER BY criterion_id, position, id LIMIT 500"
)
_UPDATE: Final = text(
    "UPDATE questions SET question_text = COALESCE(:question_text, question_text), "
    "strong_answer = COALESCE(:strong_answer, strong_answer), "
    "weak_answer = COALESCE(:weak_answer, weak_answer), "
    "position = COALESCE(:position, position), updated_at = now() "
    "WHERE id = :id RETURNING id, criterion_id, question_text, strong_answer, weak_answer, position"
)
_ENQUEUE_KIT: Final = text(
    "INSERT INTO jobs (type, role_id, criteria_version) "
    "VALUES ('generate_kit', :role_id, :version) ON CONFLICT DO NOTHING RETURNING id"
)
_ENQUEUE_QUESTION: Final = text(
    "INSERT INTO jobs (type, role_id, question_id, criteria_version) "
    "SELECT 'regenerate_question', :role_id, :question_id, :version "
    "WHERE EXISTS (SELECT 1 FROM questions WHERE id = :question_id) "
    "ON CONFLICT DO NOTHING RETURNING id"
)


def _opt_int(value: object) -> int | None:
    return None if value is None else int(str(value))


@dataclass(frozen=True, slots=True)
class QuestionRef:
    """A question's id and the role whose kit holds it."""

    id: uuid.UUID
    role_id: uuid.UUID


class KitRepository:
    """The kit header, its questions, and the `generate_kit` and `regenerate_question` jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def spent_usd(self) -> Decimal | None:
        """USD spent or reserved so far; None when the budget row is missing."""
        return await read_spent(self._session)

    async def lock_role(self, role_id: uuid.UUID) -> RoleState | None:
        """Lock the role FOR SHARE, so it cannot go back to Draft before the job commits."""
        row = (await self._session.execute(_ROLE_SHARED, {"id": role_id})).first()
        return None if row is None else RoleState(row.status, row.criteria_version)

    async def kit_version(self, role_id: uuid.UUID) -> int | None:
        """The criteria version the kit was generated against; None when no kit exists."""
        return _opt_int(
            await self._session.scalar(
                text("SELECT criteria_version FROM interview_kits WHERE role_id = :id"),
                {"id": role_id},
            )
        )

    async def questions(self, role_id: uuid.UUID) -> list[Row[tuple[object, ...]]]:
        """Q16: the role's questions by criterion then position, at most 500."""
        return list((await self._session.execute(_QUESTIONS, {"role_id": role_id})).all())

    async def question(self, question_id: uuid.UUID) -> QuestionRef | None:
        """The question's role, or None."""
        row = (
            await self._session.execute(
                text("SELECT id, role_id FROM questions WHERE id = :id"), {"id": question_id}
            )
        ).first()
        return None if row is None else QuestionRef(row.id, row.role_id)

    async def update_question(
        self,
        question_id: uuid.UUID,
        *,
        question_text: str | None,
        strong_answer: str | None,
        weak_answer: str | None,
        position: int | None,
    ) -> Row[tuple[object, ...]] | None:
        """Change the given fields in place (None keeps a field); the row, or None if gone."""
        params = {
            "id": question_id,
            "question_text": question_text,
            "strong_answer": strong_answer,
            "weak_answer": weak_answer,
            "position": position,
        }
        return (await self._session.execute(_UPDATE, params)).first()

    async def delete_question(self, question_id: uuid.UUID) -> bool:
        """Delete one question; False when it was not there."""
        result = await self._session.execute(
            text("DELETE FROM questions WHERE id = :id RETURNING id"), {"id": question_id}
        )
        return result.first() is not None

    async def enqueue_generate_kit(self, role_id: uuid.UUID, version: int) -> int | None:
        """A `generate_kit` job id, or None when one is already open for the role."""
        job_id = await self._session.scalar(_ENQUEUE_KIT, {"role_id": role_id, "version": version})
        return _opt_int(job_id)

    async def enqueue_regenerate(
        self, role_id: uuid.UUID, question_id: uuid.UUID, version: int
    ) -> int | None:
        """A `regenerate_question` job id; None when one is open or the question is gone."""
        job_id = await self._session.scalar(
            _ENQUEUE_QUESTION, {"role_id": role_id, "question_id": question_id, "version": version}
        )
        return _opt_int(job_id)
