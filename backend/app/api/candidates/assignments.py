"""POST/DELETE /v1/candidates/{id}/assignments and GET /v1/me/candidates."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.candidates.assignment_schemas import Assignment, AssignRequest, MyCandidates
from app.core.auth import InterviewerUser, RecruiterUser
from app.core.errors import ErrorEnvelope
from app.db.repositories.assignments import AssignmentRepository
from app.db.session import get_session
from app.domain.candidates import assignments as service

router = APIRouter(prefix="/v1", tags=["candidates"])


def _errors(*codes: int) -> dict[int | str, dict[str, type[ErrorEnvelope]]]:
    return {code: {"model": ErrorEnvelope} for code in (401, 403, *codes)}


def get_assignments(session: Annotated[AsyncSession, Depends(get_session)]) -> AssignmentRepository:
    """The assignment repository for this request."""
    return AssignmentRepository(session)


Db = Annotated[AsyncSession, Depends(get_session)]
Assignments = Annotated[AssignmentRepository, Depends(get_assignments)]


@router.get("/me/candidates", response_model=MyCandidates, responses=_errors())
async def list_my_candidates(
    user: InterviewerUser,
    repo: Assignments,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> MyCandidates:
    """The caller's assigned candidates; nobody else's, whatever the query says."""
    response.headers["Cache-Control"] = "no-store"
    return MyCandidates(data=await service.my_candidates(repo, user.id, limit))


@router.post(
    "/candidates/{candidate_id}/assignments",
    status_code=201,
    response_model=Assignment,
    responses=_errors(404, 422),
)
async def assign_interviewer(
    candidate_id: uuid.UUID,
    body: AssignRequest,
    _: RecruiterUser,
    db: Db,
    repo: Assignments,
    response: Response,
) -> Assignment:
    """Assign an interviewer; a repeat returns 201 again and changes nothing."""
    response.headers["Cache-Control"] = "no-store"
    return await service.assign(db, repo, candidate_id, body.user_id)


@router.delete(
    "/candidates/{candidate_id}/assignments/{user_id}",
    status_code=204,
    responses=_errors(404),
)
async def remove_assignment(
    candidate_id: uuid.UUID, user_id: uuid.UUID, _: RecruiterUser, db: Db, repo: Assignments
) -> Response:
    """Remove an assignment; the candidate disappears from that interviewer's view."""
    await service.unassign(db, repo, candidate_id, user_id)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
