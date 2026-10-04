"""POST/GET /v1/roles, GET /v1/roles/{id}, PUT .../criteria, POST .../approve."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth.router import get_app_settings
from app.api.jobs.deps import Jobs
from app.api.jobs.schemas import JobAccepted
from app.api.roles.schemas import (
    ApproveRequest,
    CriteriaReplace,
    RoleCreate,
    RoleDetail,
    RoleList,
    RoleOut,
)
from app.core.auth import CurrentUser, RecruiterUser
from app.core.config import Settings
from app.core.errors import ErrorEnvelope
from app.db.repositories.criteria import CriteriaRepository
from app.db.repositories.roles import RoleRepository
from app.db.session import get_session
from app.domain.jobs import service as jobs_service
from app.domain.roles import service

router = APIRouter(prefix="/v1/roles", tags=["roles"])


def errors(*codes: int) -> dict[int | str, dict[str, type[ErrorEnvelope]]]:
    """The error responses a route documents, each in the one envelope."""
    return {code: {"model": ErrorEnvelope} for code in (401, 403, *codes)}


_NO_STORE = "no-store"


def get_roles(session: Annotated[AsyncSession, Depends(get_session)]) -> RoleRepository:
    """The role repository for this request."""
    return RoleRepository(session)


def get_criteria(session: Annotated[AsyncSession, Depends(get_session)]) -> CriteriaRepository:
    """The criteria repository for this request."""
    return CriteriaRepository(session)


Db = Annotated[AsyncSession, Depends(get_session)]
Roles = Annotated[RoleRepository, Depends(get_roles)]
Criteria = Annotated[CriteriaRepository, Depends(get_criteria)]


@router.post("", status_code=201, response_model=RoleOut, responses=errors(422))
async def create_role(
    body: RoleCreate, _: RecruiterUser, db: Db, roles: Roles, response: Response
) -> RoleOut:
    """Create a Draft role."""
    response.headers["Cache-Control"] = _NO_STORE
    return await service.create_role(db, roles, body)


@router.get("", response_model=RoleList, responses=errors())
async def list_roles(_: RecruiterUser, roles: Roles, response: Response) -> RoleList:
    """The newest 50 roles."""
    response.headers["Cache-Control"] = _NO_STORE
    return RoleList(data=await service.list_roles(roles))


@router.get("/{role_id}", response_model=RoleDetail, responses=errors(404))
async def get_role(
    role_id: uuid.UUID,
    user: CurrentUser,
    roles: Roles,
    criteria: Criteria,
    response: Response,
) -> RoleDetail:
    """A role with its live criteria; an interviewer sees it only with an assigned candidate."""
    response.headers["Cache-Control"] = _NO_STORE
    return await service.get_role(roles, criteria, user, role_id)


@router.put(
    "/{role_id}/criteria",
    response_model=RoleDetail,
    responses=errors(404, 422),
)
async def replace_criteria(
    role_id: uuid.UUID,
    body: CriteriaReplace,
    _: RecruiterUser,
    db: Db,
    roles: Roles,
    criteria: Criteria,
    response: Response,
) -> RoleDetail:
    """Replace the criteria set; the role returns to Draft."""
    response.headers["Cache-Control"] = _NO_STORE
    return await service.replace_criteria(db, roles, criteria, role_id, body)


@router.post(
    "/{role_id}/approve",
    response_model=RoleOut,
    responses=errors(404, 409, 422),
)
async def approve_role(
    role_id: uuid.UUID,
    body: ApproveRequest,
    _: RecruiterUser,
    db: Db,
    roles: Roles,
    criteria: Criteria,
    response: Response,
) -> RoleOut:
    """Approve the criteria version the recruiter saw."""
    response.headers["Cache-Control"] = _NO_STORE
    return await service.approve_role(db, roles, criteria, role_id, body.criteria_version)


@router.post(
    "/{role_id}/criteria:propose",
    status_code=202,
    response_model=JobAccepted,
    responses=errors(404, 409),
)
async def propose_criteria(
    role_id: uuid.UUID,
    _: RecruiterUser,
    db: Db,
    roles: Roles,
    jobs: Jobs,
    settings: Annotated[Settings, Depends(get_app_settings)],
    response: Response,
) -> JobAccepted:
    """Queue a model proposal of criteria for a Draft role."""
    response.headers["Cache-Control"] = _NO_STORE
    return await jobs_service.propose_criteria(db, roles, jobs, settings, role_id)
