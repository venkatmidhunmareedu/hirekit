"""GET and generate the kit, and edit, delete or regenerate one question."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.kit.schemas import JobAccepted, KitOut, QuestionOut, QuestionUpdate
from app.api.roles.router import Db, Roles
from app.core.auth import CurrentUser, RecruiterUser
from app.core.config import Settings
from app.core.errors import ErrorEnvelope
from app.db.repositories.kit import KitRepository
from app.db.session import get_session
from app.domain.kit import service

router = APIRouter(prefix="/v1", tags=["kit"])
_NO_STORE = "no-store"


def _errors(*codes: int) -> dict[int | str, dict[str, type[ErrorEnvelope]]]:
    return {code: {"model": ErrorEnvelope} for code in (401, 403, *codes)}


def get_kits(session: Annotated[AsyncSession, Depends(get_session)]) -> KitRepository:
    """The kit repository for this request."""
    return KitRepository(session)


Kits = Annotated[KitRepository, Depends(get_kits)]


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


@router.post(
    "/roles/{role_id}/kit:generate",
    status_code=202,
    response_model=JobAccepted,
    responses=_errors(404, 409),
)
async def generate_kit(
    role_id: uuid.UUID,
    request: Request,
    _: RecruiterUser,
    db: Db,
    kits: Kits,
    response: Response,
) -> JobAccepted:
    """Enqueue `generate_kit` for an approved role."""
    response.headers["Cache-Control"] = _NO_STORE
    return await service.generate_kit(db, kits, _settings(request), role_id)


@router.get("/roles/{role_id}/kit", response_model=KitOut, responses=_errors(404))
async def get_kit(
    role_id: uuid.UUID, user: CurrentUser, roles: Roles, kits: Kits, response: Response
) -> KitOut:
    """The kit; an interviewer reads it only for a role with an assigned candidate."""
    response.headers["Cache-Control"] = _NO_STORE
    return await service.get_kit(roles, kits, user, role_id)


@router.put("/kit/questions/{question_id}", response_model=QuestionOut, responses=_errors(404, 422))
async def update_question(
    question_id: uuid.UUID,
    body: QuestionUpdate,
    _: RecruiterUser,
    db: Db,
    kits: Kits,
    response: Response,
) -> QuestionOut:
    """Edit or reorder a question in place."""
    response.headers["Cache-Control"] = _NO_STORE
    return await service.update_question(db, kits, question_id, body)


@router.delete("/kit/questions/{question_id}", status_code=204, responses=_errors(404))
async def delete_question(question_id: uuid.UUID, _: RecruiterUser, db: Db, kits: Kits) -> Response:
    """Delete a question."""
    await service.delete_question(db, kits, question_id)
    return Response(status_code=204, headers={"Cache-Control": _NO_STORE})


@router.post(
    "/kit/questions/{question_id}:regenerate",
    status_code=202,
    response_model=JobAccepted,
    responses=_errors(404, 409),
)
async def regenerate_question(
    question_id: uuid.UUID,
    request: Request,
    _: RecruiterUser,
    db: Db,
    kits: Kits,
    response: Response,
) -> JobAccepted:
    """Enqueue `regenerate_question` for one question."""
    response.headers["Cache-Control"] = _NO_STORE
    return await service.regenerate_question(db, kits, _settings(request), question_id)
