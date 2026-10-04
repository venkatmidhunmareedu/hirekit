"""POST /v1/auth/login, POST /v1/auth/logout, GET /v1/auth/me."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.api.auth.schemas import LoginRequest, SessionOut, UserOut
from app.core.auth import (
    COOKIE_NAME,
    CurrentUser,
    current_session,
    get_sessions,
    get_users,
)
from app.core.config import Settings
from app.core.errors import ErrorEnvelope
from app.db.models import UserSession
from app.db.repositories.sessions import SessionRepository
from app.db.repositories.users import UserRepository
from app.domain.auth.service import login as sign_in

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def get_app_settings(request: Request) -> Settings:
    """The settings the lifespan stored on the app."""
    settings: Settings = request.app.state.settings
    return settings


@router.post("/login", response_model=SessionOut, responses={401: {"model": ErrorEnvelope}})
async def login(
    body: LoginRequest,
    response: Response,
    settings: Annotated[Settings, Depends(get_app_settings)],
    users: Annotated[UserRepository, Depends(get_users)],
    sessions: Annotated[SessionRepository, Depends(get_sessions)],
) -> SessionOut:
    """Check the credentials, open a session, set the cookie."""
    ttl = timedelta(hours=settings.session_ttl_hours)
    token, csrf_token, user = await sign_in(
        users, sessions, email=body.email, password=body.password, ttl=ttl
    )
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf_token)


@router.post(
    "/logout",
    status_code=204,
    responses={401: {"model": ErrorEnvelope}, 403: {"model": ErrorEnvelope}},
)
async def logout(
    request: Request,
    response: Response,
    _: Annotated[UserSession, Depends(current_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    sessions: Annotated[SessionRepository, Depends(get_sessions)],
) -> None:
    """Delete the session row and clear the cookie."""
    await sessions.delete(request.cookies[COOKIE_NAME])
    response.delete_cookie(
        COOKIE_NAME, httponly=True, samesite="lax", secure=settings.cookie_secure
    )


@router.get("/me", response_model=SessionOut, responses={401: {"model": ErrorEnvelope}})
async def me(
    user: CurrentUser, row: Annotated[UserSession, Depends(current_session)]
) -> SessionOut:
    """The signed-in user and the session's CSRF token."""
    return SessionOut(user=UserOut.model_validate(user), csrf_token=row.csrf_token)
