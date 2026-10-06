"""Criteria and their rubric levels. Writes join the caller's transaction."""

import uuid
from decimal import Decimal

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Criterion, RubricLevel


class CriteriaRepository:
    """Live criteria of a role (retired_at IS NULL) and their levels."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def live(self, role_id: uuid.UUID) -> list[Criterion]:
        """The role's live criteria in display order (idx_criteria_role_position)."""
        result = await self._session.execute(
            select(Criterion)
            .where(Criterion.role_id == role_id, Criterion.retired_at.is_(None))
            .order_by(Criterion.position, Criterion.id)
            .execution_options(populate_existing=True)
        )
        return list(result.scalars())

    async def levels(self, criterion_ids: list[uuid.UUID]) -> list[RubricLevel]:
        """Every rubric level of these criteria, by criterion then level."""
        if not criterion_ids:
            return []
        result = await self._session.execute(
            select(RubricLevel)
            .where(RubricLevel.criterion_id.in_(criterion_ids))
            .order_by(RubricLevel.criterion_id, RubricLevel.level)
            .execution_options(populate_existing=True)
        )
        return list(result.scalars())

    async def add(
        self, role_id: uuid.UUID, *, name: str, kind: str, weight: int, position: int
    ) -> uuid.UUID:
        """Insert a criterion; returns its new id."""
        result = await self._session.execute(
            insert(Criterion)
            .values(
                role_id=role_id, name=name, kind=kind, weight=Decimal(weight), position=position
            )
            .returning(Criterion.id)
        )
        return result.scalar_one()

    async def edit(
        self, criterion_id: uuid.UUID, *, name: str, kind: str, weight: int, position: int
    ) -> None:
        """Update a criterion in place."""
        await self._session.execute(
            update(Criterion)
            .where(Criterion.id == criterion_id)
            .values(
                name=name,
                kind=kind,
                weight=Decimal(weight),
                position=position,
                updated_at=func.now(),
            )
        )

    async def retire(self, criterion_ids: list[uuid.UUID]) -> None:
        """Set retired_at; the rows stay so scores keep their target."""
        if criterion_ids:
            await self._session.execute(
                update(Criterion)
                .where(Criterion.id.in_(criterion_ids))
                .values(retired_at=func.now(), updated_at=func.now())
            )

    async def replace_levels(self, criterion_id: uuid.UUID, levels: list[tuple[int, str]]) -> None:
        """Delete the criterion's levels and insert these."""
        await self._session.execute(
            delete(RubricLevel).where(RubricLevel.criterion_id == criterion_id)
        )
        if levels:
            await self._session.execute(
                insert(RubricLevel),
                [{"criterion_id": criterion_id, "level": n, "descriptor": d} for n, d in levels],
            )
