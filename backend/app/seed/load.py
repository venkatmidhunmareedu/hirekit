"""Write the seed roles: draft role, criteria and rubric, then approve (US-02-007)."""

from collections.abc import Sequence

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.seed.data import SeedRole

log = structlog.get_logger()


async def seed_roles(session: AsyncSession, roles: Sequence[SeedRole]) -> int:
    """Insert each role not yet present (by title) as Approved; returns how many were created.

    The caller owns the transaction. Criteria and rubric SQL mirrors
    `worker_writes.insert_criteria`; each criteria write bumps `criteria_version`, so the
    role is approved at the version after the last one.
    """
    created = 0
    for role in roles:
        exists = await session.scalar(
            text("SELECT 1 FROM roles WHERE title = :title LIMIT 1"), {"title": role.title}
        )
        if exists is not None:
            log.info("seed_role_skipped", slug=role.slug)
            continue
        role_id = await session.scalar(
            text(
                "INSERT INTO roles (title, job_description) VALUES (:title, :description) "
                "RETURNING id"
            ),
            {"title": role.title, "description": role.job_description},
        )
        for position, criterion in enumerate(role.criteria, start=1):
            criterion_id = await session.scalar(
                text(
                    "INSERT INTO criteria (role_id, name, kind, weight, position) VALUES "
                    "(:role, :name, CAST(:kind AS criterion_kind), :weight, :position) "
                    "RETURNING id"
                ),
                {
                    "role": role_id,
                    "name": criterion.name,
                    "kind": criterion.kind,
                    "weight": criterion.weight,
                    "position": position,
                },
            )
            await session.execute(
                text(
                    "INSERT INTO rubric_levels (criterion_id, level, descriptor) "
                    "VALUES (:criterion, :level, :descriptor)"
                ),
                [
                    {"criterion": criterion_id, "level": level, "descriptor": descriptor}
                    for level, descriptor in enumerate(criterion.levels)
                ],
            )
        await session.execute(
            text(
                "UPDATE roles SET criteria_version = criteria_version + 1, "
                "status = CAST('approved' AS role_status), updated_at = now() WHERE id = :id"
            ),
            {"id": role_id},
        )
        log.info("seed_role_created", slug=role.slug)
        created += 1
    return created
