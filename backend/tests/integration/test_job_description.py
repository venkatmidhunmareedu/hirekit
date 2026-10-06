"""`load_job_description` against Postgres, including as the Worker's database role."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.gateway.text import JobDescriptionText
from app.jobs.job_description import load_job_description
from app.worker.ports import CriterionSpec
from tests.integration.test_jobs_repository import seed_role

pytestmark = pytest.mark.integration

CRITERION = CriterionSpec(
    id=uuid4(),
    name="Python",
    kind="must_have",
    weight=Decimal(3),
    position=0,
    rubric=((0, "none"), (4, "expert")),
)


async def test_the_role_comes_back_as_job_description_text(session: AsyncSession) -> None:
    role = await seed_role(session)
    loaded = await load_job_description(session, role)
    assert isinstance(loaded, JobDescriptionText)
    assert loaded.value == "Title: T\n\nJob description:\nJD"


async def test_a_criterion_and_its_rubric_follow_the_description(session: AsyncSession) -> None:
    role = await seed_role(session)
    loaded = await load_job_description(session, role, CRITERION)
    assert loaded.value.endswith("Criterion: Python (must_have)\nRubric:\n0: none\n4: expert")


async def test_a_missing_role_is_not_found(session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await load_job_description(session, uuid4())


async def test_the_worker_role_may_read_the_role(session: AsyncSession) -> None:
    role = await seed_role(session)
    await session.execute(text("SET LOCAL ROLE hirekit_worker"))
    assert (await load_job_description(session, role)).value.startswith("Title: T")
