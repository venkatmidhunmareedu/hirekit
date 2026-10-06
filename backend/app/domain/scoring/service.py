"""Retry one candidate and rescore a role (docs/design/api-lld.md 4.5).

One rule decides both: a candidate needs scoring, and two paid scoring jobs for one candidate
never coexist. Each call is one transaction; the role is locked first, then the candidate rows.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.scoring.schemas import JobAccepted, RescoreAccepted
from app.budget.policy import BUDGET_LIMIT_USD, model_actions_allowed
from app.core.config import Settings
from app.core.errors import (
    BudgetReachedError,
    JobAlreadyOpenError,
    NotFoundError,
    NotRetryableError,
    RoleNotApprovedError,
)
from app.db.repositories.roles import RoleRepository
from app.db.repositories.scoring_jobs import ScoringJobRepository

BUDGET_MESSAGE = (
    f"The model budget of ${BUDGET_LIMIT_USD:.2f} has been reached. No new model calls can be made."
)


async def _require_budget(jobs: ScoringJobRepository, settings: Settings) -> None:
    allowed = model_actions_allowed(
        settings.model_mode,
        await jobs.spent_usd(),
        settings.price_input_usd_per_mtok,
        settings.price_output_usd_per_mtok,
    )
    if not allowed:
        raise BudgetReachedError(BUDGET_MESSAGE)


async def retry_candidate(
    db: AsyncSession, jobs: ScoringJobRepository, candidate_id: uuid.UUID, settings: Settings
) -> JobAccepted:
    """A new process_resume job for a candidate that needs scoring and has no scoring job open."""
    role_id = await jobs.candidate_role_id(candidate_id)
    if role_id is None:
        raise NotFoundError("candidate not found")
    await db.commit()  # ends the read transaction the auth check opened
    async with db.begin():
        role = await jobs.lock_role(role_id)
        if role is None:
            raise NotFoundError("candidate not found")
        state = await jobs.lock_candidate(candidate_id, role.criteria_version)
        if state is None:
            raise NotFoundError("candidate not found")
        if not state.needs_scoring:
            raise NotRetryableError("this candidate does not need scoring")
        if state.open_job:
            raise JobAlreadyOpenError("a scoring job is already open for this candidate")
        await _require_budget(jobs, settings)
        job_id = await jobs.enqueue("process_resume", role_id, candidate_id, role.criteria_version)
        await jobs.reset_candidate(candidate_id)
    return JobAccepted(job_id=job_id)


async def rescore_role(
    db: AsyncSession,
    roles: RoleRepository,
    jobs: ScoringJobRepository,
    role_id: uuid.UUID,
    settings: Settings,
) -> RescoreAccepted:
    """One rescore job per candidate that needs scoring; candidates with an open job are skipped."""
    role = await roles.get(role_id)
    if role is None:
        raise NotFoundError("role not found")
    if role.status == "draft":
        raise RoleNotApprovedError("approve the criteria first")
    await _require_budget(jobs, settings)
    await db.commit()
    async with db.begin():
        state = await jobs.lock_role(role_id)
        if state is None:
            raise NotFoundError("role not found")
        if state.status == "draft":  # went back to Draft after the first read
            raise RoleNotApprovedError("approve the criteria first")
        targets = await jobs.lock_rescore_targets(role_id, state.criteria_version)
        job_ids = [
            await jobs.enqueue("rescore", role_id, t.candidate_id, state.criteria_version)
            for t in targets
            if not t.open_job
        ]
    return RescoreAccepted(
        job_ids=job_ids, skipped_candidate_nos=[t.candidate_no for t in targets if t.open_job]
    )
