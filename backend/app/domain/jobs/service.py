"""Enqueue a proposal, read and cancel jobs, show the queue. The service owns every transaction.

Each write commits the read the auth check opened, then runs in one `db.begin()` block. The
Api never makes a model call and never writes roles, criteria or scores.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.jobs.schemas import Job, JobAccepted, QueueItem, QueueView
from app.budget.policy import model_actions_allowed
from app.core.config import Settings
from app.core.errors import (
    BudgetReachedError,
    JobAlreadyOpenError,
    JobNotCancellableError,
    NotFoundError,
    RoleNotDraftError,
)
from app.db.repositories.jobs_api import JobsApiRepository
from app.db.repositories.roles import RoleRepository

BUDGET_MESSAGE = "The model budget of $8.00 has been reached. No new model calls can be made."


async def propose_criteria(
    db: AsyncSession,
    roles: RoleRepository,
    jobs: JobsApiRepository,
    settings: Settings,
    role_id: uuid.UUID,
) -> JobAccepted:
    """Queue one propose_criteria job for a Draft role (AC-US-00-001-2)."""
    await db.commit()
    async with db.begin():
        role = await roles.get(role_id, lock=True)
        if role is None:
            raise NotFoundError("role not found")
        if role.status != "draft":
            raise RoleNotDraftError("criteria can be proposed only for a Draft role")
        if not model_actions_allowed(
            settings.model_mode,
            await jobs.spent(),
            settings.price_input_usd_per_mtok,
            settings.price_output_usd_per_mtok,
        ):
            raise BudgetReachedError(BUDGET_MESSAGE)
        job_id = await jobs.enqueue_propose(role_id, role.criteria_version)
        if job_id is None:
            raise JobAlreadyOpenError("a criteria proposal is already queued or running")
    return JobAccepted(job_id=job_id)


async def get_job(jobs: JobsApiRepository, job_id: int) -> Job:
    """One job, or 404."""
    job = await jobs.get(job_id)
    if job is None:
        raise NotFoundError("job not found")
    return Job.model_validate(job)


async def cancel_job(db: AsyncSession, jobs: JobsApiRepository, job_id: int) -> Job:
    """Cancel an open job; 404 when it does not exist, 409 when it is already over."""
    await db.commit()
    async with db.begin():
        if not await jobs.cancel(job_id):
            if await jobs.get(job_id) is None:
                raise NotFoundError("job not found")
            raise JobNotCancellableError("the job is already finished")
        job = await jobs.get(job_id)
    return Job.model_validate(job)


async def queue(
    roles: RoleRepository, jobs: JobsApiRepository, role_id: uuid.UUID, limit: int
) -> QueueView:
    """Candidates of the role with their latest scoring job, and job-based counts."""
    if await roles.get(role_id) is None:
        raise NotFoundError("role not found")
    rows = await jobs.queue(role_id, limit)
    waiting, running = await jobs.open_counts(role_id)
    return QueueView(
        data=[QueueItem.model_validate(r) for r in rows], waiting=waiting, running=running
    )
