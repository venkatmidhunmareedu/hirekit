"""Roles, criteria and approval. The service owns every transaction (repositories never commit).

Each write commits the read the auth check opened, then runs in one `db.begin()` block.
"""

import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.roles.schemas import (
    CriteriaReplace,
    CriterionOut,
    RoleCreate,
    RoleDetail,
    RoleOut,
    RubricLevelOut,
)
from app.core.criteria_limits import LEVELS
from app.core.errors import (
    CriteriaChangedError,
    IncompleteRubricError,
    NoCriteriaError,
    NotFoundError,
    ValidationFailedError,
)
from app.db.models import Role, User
from app.db.repositories.criteria import CriteriaRepository
from app.db.repositories.roles import RoleRepository

LIST_LIMIT = 50


def _role_out(role: Role) -> RoleOut:
    return RoleOut.model_validate(role)


async def _detail(role: Role, criteria: CriteriaRepository) -> RoleDetail:
    live = await criteria.live(role.id)
    by_criterion: dict[uuid.UUID, list[RubricLevelOut]] = defaultdict(list)
    for level in await criteria.levels([c.id for c in live]):
        by_criterion[level.criterion_id].append(
            RubricLevelOut(level=level.level, descriptor=level.descriptor)
        )
    return RoleDetail(
        **_role_out(role).model_dump(),
        criteria=[
            CriterionOut.model_validate(
                {
                    "id": c.id,
                    "name": c.name,
                    "kind": c.kind,
                    "weight": float(c.weight),
                    "position": c.position,
                    "rubric": by_criterion[c.id],
                }
            )
            for c in live
        ],
    )


async def create_role(db: AsyncSession, roles: RoleRepository, body: RoleCreate) -> RoleOut:
    """Insert a Draft role at version 1."""
    await db.commit()  # ends the read transaction the auth check opened
    async with db.begin():
        role = await roles.create(body.title, body.job_description)
    return _role_out(role)


async def list_roles(roles: RoleRepository) -> list[RoleOut]:
    """The newest roles, at most 50."""
    return [_role_out(r) for r in await roles.list_recent(LIST_LIMIT)]


async def get_role(
    roles: RoleRepository, criteria: CriteriaRepository, user: User, role_id: uuid.UUID
) -> RoleDetail:
    """A role with its live criteria; an interviewer needs an assigned candidate, else 404."""
    if user.role == "interviewer" and not await roles.interviewer_can_read(role_id, user.id):
        raise NotFoundError("role not found")
    role = await roles.get(role_id)
    if role is None:
        raise NotFoundError("role not found")
    return await _detail(role, criteria)


async def replace_criteria(
    db: AsyncSession,
    roles: RoleRepository,
    criteria: CriteriaRepository,
    role_id: uuid.UUID,
    body: CriteriaReplace,
) -> RoleDetail:
    """Replace the set in one transaction; every call returns the role to Draft and bumps it."""
    await db.commit()
    async with db.begin():
        if await roles.get(role_id, lock=True) is None:
            raise NotFoundError("role not found")
        live_ids = {c.id for c in await criteria.live(role_id)}
        sent_ids = {c.id for c in body.criteria if c.id is not None}
        for index, item in enumerate(body.criteria):
            if item.id is not None and item.id not in live_ids:
                raise ValidationFailedError(
                    "request failed validation",
                    details={
                        "errors": [
                            {
                                "loc": ["body", "criteria", index, "id"],
                                "msg": "not a live criterion of this role",
                                "type": "value_error",
                            }
                        ]
                    },
                )
        await criteria.retire(sorted(live_ids - sent_ids))
        for position, item in enumerate(body.criteria):
            if item.id is None:
                criterion_id = await criteria.add(
                    role_id, name=item.name, kind=item.kind, weight=item.weight, position=position
                )
            else:
                criterion_id = item.id
                await criteria.edit(
                    criterion_id,
                    name=item.name,
                    kind=item.kind,
                    weight=item.weight,
                    position=position,
                )
            await criteria.replace_levels(
                criterion_id, [(r.level, r.descriptor) for r in item.rubric]
            )
        role = await roles.mark_draft_and_bump(role_id)
    return await _detail(role, criteria)


async def approve_role(
    db: AsyncSession,
    roles: RoleRepository,
    criteria: CriteriaRepository,
    role_id: uuid.UUID,
    criteria_version: int,
) -> RoleOut:
    """Approve the version the recruiter saw; a repeat at the same version is a no-op."""
    await db.commit()
    async with db.begin():
        role = await roles.get(role_id, lock=True)
        if role is None:
            raise NotFoundError("role not found")
        if role.criteria_version != criteria_version:
            raise CriteriaChangedError(
                "the criteria changed since you loaded them",
                details={"current_version": role.criteria_version},
            )
        if role.status == "approved":
            return _role_out(role)
        live = await criteria.live(role_id)
        if not live:
            raise NoCriteriaError("add at least one criterion before approving")
        have: dict[uuid.UUID, set[int]] = defaultdict(set)
        for level in await criteria.levels([c.id for c in live]):
            have[level.criterion_id].add(level.level)
        incomplete = [str(c.id) for c in live if have[c.id] != set(LEVELS)]
        if incomplete:
            raise IncompleteRubricError(
                "every criterion needs a descriptor for levels 0 to 4",
                details={"criterion_ids": incomplete},
            )
        role = await roles.mark_approved(role_id)
    return _role_out(role)
