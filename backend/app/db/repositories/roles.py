"""Roles. Writes join the caller's transaction; the service owns it."""

import uuid

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Role


class RoleRepository:
    """Roles by id, newest first, and the interviewer visibility predicate."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, title: str, job_description: str) -> Role:
        """Insert a role; the database defaults give status draft and version 1."""
        role = Role(title=title, job_description=job_description)
        self._session.add(role)
        await self._session.flush()
        await self._session.refresh(role)  # reads back the server defaults
        return role

    async def list_recent(self, limit: int) -> list[Role]:
        """The newest roles first, at most `limit`."""
        result = await self._session.execute(
            select(Role).order_by(Role.created_at.desc(), Role.id).limit(limit)
        )
        return list(result.scalars())

    async def get(self, role_id: uuid.UUID, *, lock: bool = False) -> Role | None:
        """The role, or None; `lock` takes SELECT ... FOR UPDATE and reads fresh values."""
        stmt = select(Role).where(Role.id == role_id).execution_options(populate_existing=True)
        if lock:
            stmt = stmt.with_for_update()
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def interviewer_can_read(self, role_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """True when the user is assigned a candidate of this role (the only way in)."""
        result = await self._session.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM candidates c JOIN assignments a "
                "ON a.candidate_id = c.id WHERE c.role_id = :role_id AND a.user_id = :user_id)"
            ),
            {"role_id": role_id, "user_id": user_id},
        )
        return bool(result.scalar_one())

    async def mark_draft_and_bump(self, role_id: uuid.UUID) -> Role:
        """Status draft, version + 1, updated_at now; returns the fresh row."""
        await self._session.execute(
            update(Role)
            .where(Role.id == role_id)
            .values(
                status="draft",
                criteria_version=Role.criteria_version + 1,
                updated_at=func.now(),
            )
        )
        return await self._fresh(role_id)

    async def mark_approved(self, role_id: uuid.UUID) -> Role:
        """Status approved; the version is not bumped."""
        await self._session.execute(
            update(Role).where(Role.id == role_id).values(status="approved", updated_at=func.now())
        )
        return await self._fresh(role_id)

    async def _fresh(self, role_id: uuid.UUID) -> Role:
        return (
            await self._session.execute(
                select(Role).where(Role.id == role_id).execution_options(populate_existing=True)
            )
        ).scalar_one()
