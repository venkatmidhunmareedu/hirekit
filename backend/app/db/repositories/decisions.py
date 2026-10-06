"""Reads and writes behind the recruiter decisions: override, stage, reveal.

Lock order is the Worker's: `roles`, then `candidates`, then `scores`. Raw SQL because the
Api has no ORM models for scores. Nothing here commits; the service owns the transaction.
"""

import uuid
from dataclasses import dataclass
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_ROLE_OF: Final = text("SELECT role_id FROM candidates WHERE id = :id")
_ROLE_VERSION: Final = text("SELECT criteria_version FROM roles WHERE id = :id FOR SHARE")
_CANDIDATE: Final = text(
    "SELECT role_id, CAST(stage AS text) AS stage, file_name, identity_name "
    "FROM candidates WHERE id = :id FOR UPDATE"
)
_CRITERION: Final = text("SELECT name, kind FROM criteria WHERE id = :id AND role_id = :role")
_SCORE: Final = text(
    "SELECT CAST(status AS text) AS status, model_score, quote, flag_reason, override_score "
    "FROM scores WHERE candidate_id = :c AND criterion_id = :k AND criteria_version = :v "
    "FOR UPDATE"
)
_OVERRIDE: Final = text(
    "UPDATE scores SET override_score = :score, override_note = :note, overridden_by = :user, "
    "updated_at = now() WHERE candidate_id = :c AND criterion_id = :k AND criteria_version = :v"
)
_STAGE: Final = text(
    "UPDATE candidates SET stage = CAST(:stage AS candidate_stage), updated_at = now() "
    "WHERE id = :id"
)


@dataclass(frozen=True, slots=True)
class CandidateRow:
    """The locked candidate as a decision sees it."""

    role_id: uuid.UUID
    stage: str
    file_name: str
    identity_name: str | None


@dataclass(frozen=True, slots=True)
class CriterionRow:
    name: str
    kind: str


@dataclass(frozen=True, slots=True)
class ScoreRow:
    status: str
    model_score: int | None
    quote: str | None
    flag_reason: str | None
    override_score: int | None


class DecisionRepository:
    """SQL for override, stage and reveal."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def role_of(self, candidate_id: uuid.UUID) -> uuid.UUID | None:
        """The candidate's role (it never changes), read without a lock."""
        return (await self._session.execute(_ROLE_OF, {"id": candidate_id})).scalar_one_or_none()

    async def lock_role_version(self, role_id: uuid.UUID) -> int | None:
        """The role's criteria version, locked FOR SHARE so a criteria edit waits."""
        return (await self._session.execute(_ROLE_VERSION, {"id": role_id})).scalar_one_or_none()

    async def lock_candidate(self, candidate_id: uuid.UUID) -> CandidateRow | None:
        row = (await self._session.execute(_CANDIDATE, {"id": candidate_id})).first()
        if row is None:
            return None
        return CandidateRow(row.role_id, row.stage, row.file_name, row.identity_name)

    async def criterion(self, role_id: uuid.UUID, criterion_id: uuid.UUID) -> CriterionRow | None:
        row = (
            await self._session.execute(_CRITERION, {"id": criterion_id, "role": role_id})
        ).first()
        return None if row is None else CriterionRow(row.name, row.kind)

    async def lock_score(
        self, candidate_id: uuid.UUID, criterion_id: uuid.UUID, version: int
    ) -> ScoreRow | None:
        row = (
            await self._session.execute(
                _SCORE, {"c": candidate_id, "k": criterion_id, "v": version}
            )
        ).first()
        if row is None:
            return None
        return ScoreRow(row.status, row.model_score, row.quote, row.flag_reason, row.override_score)

    async def write_override(
        self,
        candidate_id: uuid.UUID,
        criterion_id: uuid.UUID,
        version: int,
        score: int,
        note: str,
        user_id: uuid.UUID,
    ) -> None:
        await self._session.execute(
            _OVERRIDE,
            {
                "c": candidate_id,
                "k": criterion_id,
                "v": version,
                "score": score,
                "note": note,
                "user": user_id,
            },
        )

    async def write_stage(self, candidate_id: uuid.UUID, stage: str) -> None:
        """The only statement in the Api that writes `candidates.stage`."""
        await self._session.execute(_STAGE, {"id": candidate_id, "stage": stage})
