"""`seed_roles` writes approved roles with live criteria, and twice changes nothing."""

from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.seed.data import SeedCriterion, SeedRole
from app.seed.load import seed_roles

pytestmark = pytest.mark.integration

LEVELS = ("none", "basic", "some", "good", "expert")
ROLE = SeedRole(
    slug="seedtest",
    title="Seed Test Role",
    job_description="Build things.",
    criteria=(
        SeedCriterion("Python", "must_have", Decimal(3), LEVELS),
        SeedCriterion("Testing", "nice_to_have", Decimal("1.5"), LEVELS),
    ),
)


async def test_the_role_is_approved_with_criteria_and_rubric(session: AsyncSession) -> None:
    created = await seed_roles(session, (ROLE,))

    assert created == 1
    row = (
        await session.execute(
            text(
                "SELECT status::text, criteria_version, "
                "(SELECT count(*) FROM criteria c "
                " WHERE c.role_id = r.id AND c.retired_at IS NULL), "
                "(SELECT count(*) FROM rubric_levels l JOIN criteria c ON c.id = l.criterion_id "
                " WHERE c.role_id = r.id) "
                "FROM roles r WHERE title = 'Seed Test Role'"
            )
        )
    ).one()
    assert tuple(row) == ("approved", 2, 2, 10)


async def test_a_second_run_changes_nothing(session: AsyncSession) -> None:
    await seed_roles(session, (ROLE,))

    created = await seed_roles(session, (ROLE,))

    assert created == 0
    count = await session.scalar(text("SELECT count(*) FROM roles WHERE title = 'Seed Test Role'"))
    assert count == 1
