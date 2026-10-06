"""POST/GET/PUT /v1/candidates/{id}/feedback and POST .../feedback/{interviewer_id}:approve-edit."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.feedback.schemas import FeedbackList, FeedbackSubmit
from app.api.roles.router import Criteria
from app.core.auth import CurrentUser, InterviewerUser, RecruiterUser
from app.core.errors import ErrorEnvelope
from app.db.repositories.feedback import FeedbackRepository
from app.db.session import get_session
from app.domain.feedback import service

router = APIRouter(prefix="/v1/candidates", tags=["feedback"])


def _errors(*codes: int) -> dict[int | str, dict[str, type[ErrorEnvelope]]]:
    return {code: {"model": ErrorEnvelope} for code in (401, 403, *codes)}


def get_feedback(session: Annotated[AsyncSession, Depends(get_session)]) -> FeedbackRepository:
    """The feedback repository for this request."""
    return FeedbackRepository(session)


Db = Annotated[AsyncSession, Depends(get_session)]
Feedback = Annotated[FeedbackRepository, Depends(get_feedback)]


@router.post(
    "/{candidate_id}/feedback",
    status_code=201,
    response_model=FeedbackList,
    responses=_errors(404, 409, 422),
)
async def submit_feedback(
    candidate_id: uuid.UUID,
    body: FeedbackSubmit,
    user: InterviewerUser,
    db: Db,
    feedback: Feedback,
    criteria: Criteria,
    response: Response,
) -> FeedbackList:
    """Submit feedback for every live criterion; it is locked on save."""
    response.headers["Cache-Control"] = "no-store"
    return await service.submit(db, feedback, criteria, user, candidate_id, body)


@router.get("/{candidate_id}/feedback", response_model=FeedbackList, responses=_errors(404))
async def get_candidate_feedback(
    candidate_id: uuid.UUID, user: CurrentUser, feedback: Feedback, response: Response
) -> FeedbackList:
    """A recruiter sees every interviewer's feedback; an interviewer only their own."""
    response.headers["Cache-Control"] = "no-store"
    return await service.read(feedback, user, candidate_id)


@router.put(
    "/{candidate_id}/feedback",
    response_model=FeedbackList,
    responses=_errors(404, 409, 422),
)
async def edit_feedback(
    candidate_id: uuid.UUID,
    body: FeedbackSubmit,
    user: InterviewerUser,
    db: Db,
    feedback: Feedback,
    criteria: Criteria,
    response: Response,
) -> FeedbackList:
    """Save an approved edit and lock the feedback again."""
    response.headers["Cache-Control"] = "no-store"
    return await service.edit(db, feedback, criteria, user, candidate_id, body)


@router.post(
    "/{candidate_id}/feedback/{interviewer_id}:approve-edit",
    response_model=FeedbackList,
    responses=_errors(404),
)
async def approve_feedback_edit(
    candidate_id: uuid.UUID,
    interviewer_id: uuid.UUID,
    user: RecruiterUser,
    db: Db,
    feedback: Feedback,
    response: Response,
) -> FeedbackList:
    """Unlock one interviewer's feedback for one edit."""
    response.headers["Cache-Control"] = "no-store"
    return await service.approve_edit(db, feedback, user, candidate_id, interviewer_id)
