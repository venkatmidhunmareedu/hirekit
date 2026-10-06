"""Append one audit_events row. Callers run it in the same transaction as the change."""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_INSERT = text(
    "INSERT INTO audit_events (candidate_id, actor_id, kind, criterion_name, old_score, "
    "new_score, from_stage, to_stage, note) VALUES (:candidate, :actor, :kind, :criterion, "
    ":old_score, :new_score, CAST(:from_stage AS candidate_stage), "
    "CAST(:to_stage AS candidate_stage), :note)"
)


class AuditRepository:
    """The only writer of audit rows from the Api."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _add(
        self,
        candidate_id: uuid.UUID,
        actor_id: uuid.UUID,
        kind: str,
        *,
        criterion: str | None = None,
        old_score: int | None = None,
        new_score: int | None = None,
        from_stage: str | None = None,
        to_stage: str | None = None,
        note: str | None = None,
    ) -> None:
        await self._session.execute(
            _INSERT,
            {
                "candidate": candidate_id,
                "actor": actor_id,
                "kind": kind,
                "criterion": criterion,
                "old_score": old_score,
                "new_score": new_score,
                "from_stage": from_stage,
                "to_stage": to_stage,
                "note": note,
            },
        )

    async def score_override(
        self,
        candidate_id: uuid.UUID,
        actor_id: uuid.UUID,
        criterion_name: str,
        old_score: int | None,
        new_score: int,
        note: str,
    ) -> None:
        await self._add(
            candidate_id,
            actor_id,
            "score_override",
            criterion=criterion_name,
            old_score=old_score,
            new_score=new_score,
            note=note,
        )

    async def stage_change(
        self,
        candidate_id: uuid.UUID,
        actor_id: uuid.UUID,
        from_stage: str,
        to_stage: str,
        note: str | None,
    ) -> None:
        await self._add(
            candidate_id,
            actor_id,
            "stage_change",
            from_stage=from_stage,
            to_stage=to_stage,
            note=note,
        )

    async def identity_reveal(self, candidate_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        await self._add(candidate_id, actor_id, "identity_reveal")
