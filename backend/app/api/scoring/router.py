"""POST /v1/candidates/{id}:retry and POST /v1/roles/{id}:rescore (recruiter only)."""

import uuid
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.roles.router import Roles
from app.api.scoring.schemas import JobAccepted, RescoreAccepted
from app.core.auth import RecruiterUser
from app.core.config import Settings
from app.core.errors import ErrorEnvelope
from app.db.repositories.scoring_jobs import ScoringJobRepository
from app.db.session import get_session
from app.domain.scoring import service

router = APIRouter(tags=["jobs"])

_ERRORS: Final[dict[int | str, dict[str, type[ErrorEnvelope]]]] = {
    code: {"model": ErrorEnvelope} for code in (401, 403, 404, 409)
}


def get_scoring_jobs(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ScoringJobRepository:
    """The scoring job repository for this request."""
    return ScoringJobRepository(session)


Db = Annotated[AsyncSession, Depends(get_session)]
ScoringJobs = Annotated[ScoringJobRepository, Depends(get_scoring_jobs)]


@router.post(
    "/v1/candidates/{candidate_id}:retry",
    status_code=202,
    response_model=JobAccepted,
    responses=_ERRORS,
)
async def retry_candidate(
    candidate_id: uuid.UUID,
    _: RecruiterUser,
    request: Request,
    db: Db,
    jobs: ScoringJobs,
    response: Response,
) -> JobAccepted:
    """Enqueue a new process_resume job for a candidate that needs scoring."""
    response.headers["Cache-Control"] = "no-store"
    settings: Settings = request.app.state.settings
    return await service.retry_candidate(db, jobs, candidate_id, settings)


@router.post(
    "/v1/roles/{role_id}:rescore",
    status_code=202,
    response_model=RescoreAccepted,
    responses=_ERRORS,
)
async def rescore_role(
    role_id: uuid.UUID,
    _: RecruiterUser,
    request: Request,
    db: Db,
    roles: Roles,
    jobs: ScoringJobs,
    response: Response,
) -> RescoreAccepted:
    """Enqueue a rescore job for every candidate that needs scoring and has none open."""
    response.headers["Cache-Control"] = "no-store"
    settings: Settings = request.app.state.settings
    return await service.rescore_role(db, roles, jobs, role_id, settings)
