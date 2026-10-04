"""The permission matrix: one table of route to allowed roles, every cell a test.

Later items add a row per route. The routes below exist only here, to prove the
dependencies; they are not part of the app.
"""

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient

from app.core.auth import CurrentUser, InterviewerUser, RecruiterUser, current_session
from app.db.models import UserSession
from tests.api.fakes import FakeSessions, FakeUsers

# (method, path) -> roles allowed. An absent role gets 403; no sign-in gets 401.
MATRIX: dict[tuple[str, str], frozenset[str]] = {
    ("GET", "/t/recruiter"): frozenset({"recruiter"}),
    ("POST", "/t/recruiter"): frozenset({"recruiter"}),
    ("GET", "/t/interviewer"): frozenset({"interviewer"}),
    ("GET", "/t/anyone"): frozenset({"recruiter", "interviewer"}),
}
CELLS = [(m, p, who) for (m, p) in MATRIX for who in ("anonymous", "recruiter", "interviewer")]


def register_test_routes(app: FastAPI) -> None:
    @app.get("/t/recruiter")
    @app.post("/t/recruiter")
    async def recruiter_only(user: RecruiterUser) -> dict[str, str]:
        return {"role": user.role}

    @app.get("/t/interviewer")
    async def interviewer_only(user: InterviewerUser) -> dict[str, str]:
        return {"role": user.role}

    @app.get("/t/anyone")
    async def any_user(user: CurrentUser) -> dict[str, str]:
        return {"role": user.role}

    @app.get("/t/session")
    async def the_session(row: Annotated[UserSession, Depends(current_session)]) -> dict[str, str]:
        return {"csrf": row.csrf_token}


@pytest.fixture(autouse=True)
def _routes(app: FastAPI) -> None:
    register_test_routes(app)


@pytest.mark.parametrize(("method", "path", "who"), CELLS)
async def test_matrix_cell(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    method: str,
    path: str,
    who: str,
) -> None:
    headers: dict[str, str] = {}
    if who != "anonymous":
        signed_in = await sessions.sign_in(users.add(email=f"{who}@example.com", role=who))
        headers = signed_in.unsafe_headers

    response = await client.request(method, path, headers=headers)

    if who == "anonymous":
        assert (response.status_code, response.json()["error"]["code"]) == (401, "unauthenticated")
    elif who in MATRIX[(method, path)]:
        assert response.status_code == 200
    else:
        assert (response.status_code, response.json()["error"]["code"]) == (403, "forbidden")
