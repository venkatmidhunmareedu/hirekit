"""The audited recruiter decisions: override a score, change the stage, reveal the identity."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.candidates.decision_schemas import (
    Identity,
    OverrideRequest,
    ScoreCell,
    StageChanged,
    StageRequest,
)
from app.core.auth import RecruiterUser
from app.core.errors import ErrorEnvelope
from app.db.repositories.audit import AuditRepository
from app.db.repositories.decisions import DecisionRepository
from app.db.session import get_session
from app.domain.candidates import decisions as service

router = APIRouter(prefix="/v1/candidates", tags=["candidates"])


def _errors(*codes: int) -> dict[int | str, dict[str, type[ErrorEnvelope]]]:
    return {code: {"model": ErrorEnvelope} for code in (401, 403, *codes)}


def get_decisions(session: Annotated[AsyncSession, Depends(get_session)]) -> DecisionRepository:
    """The decision repository for this request."""
    return DecisionRepository(session)


def get_audit(session: Annotated[AsyncSession, Depends(get_session)]) -> AuditRepository:
    """The audit repository for this request."""
    return AuditRepository(session)


Db = Annotated[AsyncSession, Depends(get_session)]
Decisions = Annotated[DecisionRepository, Depends(get_decisions)]
Audit = Annotated[AuditRepository, Depends(get_audit)]


@router.put(
    "/{candidate_id}/scores/{criterion_id}/override",
    response_model=ScoreCell,
    responses=_errors(404, 409, 422),
)
async def override_score(
    candidate_id: uuid.UUID,
    criterion_id: uuid.UUID,
    body: OverrideRequest,
    user: RecruiterUser,
    db: Db,
    decisions: Decisions,
    audit: Audit,
    response: Response,
) -> ScoreCell:
    """Override one score with a note of at least 10 characters; the model's value is kept."""
    response.headers["Cache-Control"] = "no-store"
    return await service.override_score(
        db, decisions, audit, user, candidate_id, criterion_id, body
    )


@router.post(
    "/{candidate_id}/stage",
    response_model=StageChanged,
    responses=_errors(404, 409, 422),
)
async def change_stage(
    candidate_id: uuid.UUID,
    body: StageRequest,
    user: RecruiterUser,
    db: Db,
    decisions: Decisions,
    audit: Audit,
    response: Response,
) -> StageChanged:
    """The only route that writes a candidate's stage."""
    response.headers["Cache-Control"] = "no-store"
    return await service.change_stage(db, decisions, audit, user, candidate_id, body)


@router.post(
    "/{candidate_id}:reveal-identity",
    response_model=Identity,
    responses=_errors(404),
)
async def reveal_identity(
    candidate_id: uuid.UUID,
    user: RecruiterUser,
    db: Db,
    decisions: Decisions,
    audit: Audit,
    response: Response,
) -> Identity:
    """Audited reveal of the name and file name; never cached."""
    response.headers["Cache-Control"] = "no-store"
    return await service.reveal_identity(db, decisions, audit, user, candidate_id)
