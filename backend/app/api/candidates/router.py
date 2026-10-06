"""GET /v1/roles/{id}/candidates, GET /v1/candidates/{id} and GET /v1/candidates/{id}/text."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.candidates.schemas import CandidateDetail, CandidateText, RankedList, Stage
from app.api.roles.router import Criteria
from app.core.auth import CurrentUser, RecruiterUser
from app.core.errors import ErrorEnvelope
from app.db.repositories.candidates import CandidateRepository
from app.db.session import get_session
from app.domain.candidates import read

router = APIRouter(tags=["candidates"])


def _errors(*codes: int) -> dict[int | str, dict[str, type[ErrorEnvelope]]]:
    return {code: {"model": ErrorEnvelope} for code in (401, 403, *codes)}


def get_candidates(session: Annotated[AsyncSession, Depends(get_session)]) -> CandidateRepository:
    """The candidate read repository for this request."""
    return CandidateRepository(session)


Candidates = Annotated[CandidateRepository, Depends(get_candidates)]
_NO_STORE = "no-store"


@router.get(
    "/v1/roles/{role_id}/candidates",
    response_model=RankedList,
    responses=_errors(404, 422),
)
async def list_candidates(
    role_id: uuid.UUID,
    _: RecruiterUser,
    candidates: Candidates,
    criteria: Criteria,
    response: Response,
    stage: Annotated[Stage | None, Query(alias="filter[stage]")] = None,
    sort: str = "total",
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0, le=1000)] = 0,
) -> RankedList:
    """The ranked list: every candidate of the role, scores from older versions marked stale."""
    response.headers["Cache-Control"] = _NO_STORE
    return await read.ranked_list(candidates, criteria, role_id, stage, sort, limit, offset)


@router.get(
    "/v1/candidates/{candidate_id}",
    response_model=CandidateDetail,
    response_model_exclude_unset=True,
    responses=_errors(404),
)
async def get_candidate(
    candidate_id: uuid.UUID, user: CurrentUser, candidates: Candidates, response: Response
) -> CandidateDetail:
    """One candidate; an interviewer gets it only when assigned, and a reduced view."""
    response.headers["Cache-Control"] = _NO_STORE
    return await read.detail(candidates, user, candidate_id)


@router.get(
    "/v1/candidates/{candidate_id}/text",
    response_model=CandidateText,
    responses=_errors(404),
)
async def get_candidate_text(
    candidate_id: uuid.UUID, _: RecruiterUser, candidates: Candidates, response: Response
) -> CandidateText:
    """Raw and anonymized resume text, personal data, recruiters only."""
    response.headers["Cache-Control"] = _NO_STORE
    return await read.resume_text(candidates, candidate_id)
