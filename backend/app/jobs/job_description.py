"""`load_job_description`: the one way a role's stored job description becomes `JobDescriptionText`.

Reads `roles` only, never a candidate or resume table (tenet 1). The text is recruiter-authored
data: it is passed on as it is, never interpreted, logged or quoted in an error. For a kit the
criterion and its rubric follow the description. Runs inside the caller's transaction.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.gateway.text import JobDescriptionText, mint_job_description
from app.worker.ports import CriterionSpec


def job_description_text(
    title: str, description: str, criterion: CriterionSpec | None = None
) -> JobDescriptionText:
    """The text the model sees for one role; the evals build it too, so recordings match."""
    body = f"Title: {title}\n\nJob description:\n{description}"
    if criterion is not None:
        levels = "\n".join(f"{level}: {descriptor}" for level, descriptor in criterion.rubric)
        body += f"\n\nCriterion: {criterion.name} ({criterion.kind})\nRubric:\n{levels}"
    return mint_job_description(body)


_Q1 = text("SELECT title, job_description FROM roles WHERE id = :role_id")


async def load_job_description(
    session: AsyncSession, role_id: UUID, criterion: CriterionSpec | None = None
) -> JobDescriptionText:
    """Title and description of one role, plus the criterion and rubric for a kit."""
    row = (await session.execute(_Q1, {"role_id": role_id})).one_or_none()
    if row is None:
        msg = "No such role."
        raise NotFoundError(msg)
    title, description = row
    return job_description_text(title, description, criterion)
