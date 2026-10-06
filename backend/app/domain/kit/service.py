"""Kit rules. The Api never calls a model: generate and regenerate only enqueue a job.

Reads need the role to be visible to the caller (an interviewer only with an assigned candidate in
it, in SQL). Writes are recruiter-only at the route; a question is reached through its own role.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.kit.schemas import JobAccepted, KitOut, QuestionOut, QuestionUpdate
from app.budget.policy import BUDGET_LIMIT_USD, model_actions_allowed
from app.core.config import Settings
from app.core.errors import (
    BudgetReachedError,
    JobAlreadyOpenError,
    NotFoundError,
    RoleNotApprovedError,
)
from app.db.models import User
from app.db.repositories.kit import KitRepository
from app.db.repositories.roles import RoleRepository

BUDGET_MESSAGE = (
    f"The model budget of ${BUDGET_LIMIT_USD:.2f} has been reached. No new model calls can be made."
)
OPEN_MESSAGE = "a kit job for this target is already open"


async def get_kit(
    roles: RoleRepository, kits: KitRepository, user: User, role_id: uuid.UUID
) -> KitOut:
    """The kit with `stale` derived; 404 for an unseen role or a role with no kit yet."""
    if user.role == "interviewer" and not await roles.interviewer_can_read(role_id, user.id):
        raise NotFoundError("kit not found")
    role = await roles.get(role_id)
    version = await kits.kit_version(role_id)
    if role is None or version is None:
        raise NotFoundError("kit not found")
    return KitOut(
        role_id=role_id,
        stale=version < role.criteria_version,
        criteria_version=version,
        questions=[QuestionOut.model_validate(q) for q in await kits.questions(role_id)],
    )


async def _lock_approved_role(kits: KitRepository, settings: Settings, role_id: uuid.UUID) -> int:
    """Lock the role; return its criteria version, or refuse a Draft role or a spent budget."""
    state = await kits.lock_role(role_id)
    if state is None:
        raise NotFoundError("not found")
    if state.status == "draft":
        raise RoleNotApprovedError("approve the criteria first")
    allowed = model_actions_allowed(
        settings.model_mode,
        await kits.spent_usd(),
        settings.price_input_usd_per_mtok,
        settings.price_output_usd_per_mtok,
    )
    if not allowed:
        raise BudgetReachedError(BUDGET_MESSAGE)
    return state.criteria_version


async def generate_kit(
    db: AsyncSession, kits: KitRepository, settings: Settings, role_id: uuid.UUID
) -> JobAccepted:
    """Enqueue `generate_kit` for an approved role; one open job per role (else 409)."""
    await db.commit()  # ends the read transaction the auth check opened
    async with db.begin():
        version = await _lock_approved_role(kits, settings, role_id)
        job_id = await kits.enqueue_generate_kit(role_id, version)
    if job_id is None:
        raise JobAlreadyOpenError(OPEN_MESSAGE)
    return JobAccepted(job_id=job_id)


async def update_question(
    db: AsyncSession, kits: KitRepository, question_id: uuid.UUID, body: QuestionUpdate
) -> QuestionOut:
    """Edit or reorder a question in place."""
    await db.commit()
    async with db.begin():
        row = await kits.update_question(
            question_id,
            question_text=body.question_text,
            strong_answer=body.strong_answer,
            weak_answer=body.weak_answer,
            position=body.position,
        )
    if row is None:
        raise NotFoundError("question not found")
    return QuestionOut.model_validate(row)


async def delete_question(db: AsyncSession, kits: KitRepository, question_id: uuid.UUID) -> None:
    """Delete a question; 404 when it is not there."""
    await db.commit()
    async with db.begin():
        found = await kits.delete_question(question_id)
    if not found:
        raise NotFoundError("question not found")


async def regenerate_question(
    db: AsyncSession, kits: KitRepository, settings: Settings, question_id: uuid.UUID
) -> JobAccepted:
    """Enqueue `regenerate_question`; one open job per question (else 409)."""
    await db.commit()
    async with db.begin():
        question = await kits.question(question_id)
        if question is None:
            raise NotFoundError("question not found")
        version = await _lock_approved_role(kits, settings, question.role_id)
        job_id = await kits.enqueue_regenerate(question.role_id, question_id, version)
        if job_id is None and await kits.question(question_id) is None:
            raise NotFoundError("question not found")
    if job_id is None:
        raise JobAlreadyOpenError(OPEN_MESSAGE)
    return JobAccepted(job_id=job_id)
