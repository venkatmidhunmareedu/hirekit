"""Who is calling: the session cookie, the CSRF check and the role dependencies.

Every protected route depends on `CurrentUser`, `RecruiterUser` or `InterviewerUser`.
The cookie holds a random token; the database holds only its SHA-256 (ADR-0005).
"""

import hmac
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import CsrfError, ForbiddenError, UnauthenticatedError
from app.db.models import User, UserSession
from app.db.repositories.sessions import SessionRepository
from app.db.repositories.users import UserRepository
from app.db.session import get_session

COOKIE_NAME = "hirekit_session"
CSRF_HEADER = "X-CSRF-Token"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def get_users(session: Annotated[AsyncSession, Depends(get_session)]) -> UserRepository:
    """The user repository for this request."""
    return UserRepository(session)


def get_sessions(session: Annotated[AsyncSession, Depends(get_session)]) -> SessionRepository:
    """The session repository for this request."""
    return SessionRepository(session)


async def current_session(
    request: Request, sessions: Annotated[SessionRepository, Depends(get_sessions)]
) -> UserSession:
    """The live session for the cookie; on a state-changing request, its CSRF token too."""
    token = request.cookies.get(COOKIE_NAME)
    row = await sessions.read_valid(token) if token else None
    if row is None:
        raise UnauthenticatedError("sign in required")
    if request.method not in _SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not hmac.compare_digest(sent.encode(), row.csrf_token.encode()):
            raise CsrfError("csrf token missing or wrong")
    return row


async def current_user(
    row: Annotated[UserSession, Depends(current_session)],
    users: Annotated[UserRepository, Depends(get_users)],
) -> User:
    """The signed-in user; a session whose user is gone is no session."""
    user = await users.by_id(row.user_id)
    if user is None:
        raise UnauthenticatedError("sign in required")
    return user


Role = Literal["recruiter", "interviewer"]


def require_role(role: Role) -> Callable[[User], Awaitable[User]]:
    """A dependency that admits only users with this role."""

    async def check(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role != role:
            raise ForbiddenError("this role cannot do that")
        return user

    return check


CurrentUser = Annotated[User, Depends(current_user)]
RecruiterUser = Annotated[User, Depends(require_role("recruiter"))]
InterviewerUser = Annotated[User, Depends(require_role("interviewer"))]
