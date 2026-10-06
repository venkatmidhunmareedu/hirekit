"""The permission matrix: one table of route to allowed roles, every cell a test.

Later items add a row per route. The routes below exist only here, to prove the
dependencies; they are not part of the app.
"""

from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, _EffectiveRouteContext, _IncludedRouter
from httpx import AsyncClient
from starlette.routing import BaseRoute

from app.core.auth import CurrentUser, InterviewerUser, RecruiterUser, current_session
from app.core.config import Settings
from app.db.models import UserSession
from app.main import create_app
from tests.api.fakes import FakeCriteria, FakeKit, FakeRoles, FakeSessions, FakeUploads, FakeUsers
from tests.files import pdf_bytes

# (method, path) -> roles allowed. An absent role gets 403; no sign-in gets 401.
MATRIX: dict[tuple[str, str], frozenset[str]] = {
    ("GET", "/t/recruiter"): frozenset({"recruiter"}),
    ("POST", "/t/recruiter"): frozenset({"recruiter"}),
    ("GET", "/t/interviewer"): frozenset({"interviewer"}),
    ("GET", "/t/anyone"): frozenset({"recruiter", "interviewer"}),
    ("GET", "/v1/auth/me"): frozenset({"recruiter", "interviewer"}),
    ("POST", "/v1/auth/logout"): frozenset({"recruiter", "interviewer"}),
    ("POST", "/v1/roles"): frozenset({"recruiter"}),
    ("GET", "/v1/roles"): frozenset({"recruiter"}),
    ("GET", "/v1/roles/{role_id}"): frozenset({"recruiter", "interviewer"}),
    ("PUT", "/v1/roles/{role_id}/criteria"): frozenset({"recruiter"}),
    ("POST", "/v1/roles/{role_id}/approve"): frozenset({"recruiter"}),
    ("POST", "/v1/roles/{role_id}/resumes"): frozenset({"recruiter"}),
    ("POST", "/v1/roles/{role_id}/kit:generate"): frozenset({"recruiter"}),
    ("GET", "/v1/roles/{role_id}/kit"): frozenset({"recruiter", "interviewer"}),
    ("PUT", "/v1/kit/questions/{question_id}"): frozenset({"recruiter"}),
    ("DELETE", "/v1/kit/questions/{question_id}"): frozenset({"recruiter"}),
    ("POST", "/v1/kit/questions/{question_id}:regenerate"): frozenset({"recruiter"}),
}
# Routes that need no session. Docs and openapi routes are not APIRoutes and never reach the check.
PUBLIC = frozenset({("POST", "/v1/auth/login"), ("GET", "/healthz"), ("GET", "/readyz")})
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


FULL_RUBRIC = [{"level": n, "descriptor": f"level {n}"} for n in range(5)]
BODIES: dict[tuple[str, str], dict[str, object]] = {
    ("POST", "/v1/roles"): {"title": "Engineer", "job_description": "Build."},
    ("PUT", "/v1/roles/{role_id}/criteria"): {
        "criteria": [{"name": "Python", "kind": "must_have", "weight": 3, "rubric": FULL_RUBRIC}]
    },
    ("POST", "/v1/roles/{role_id}/approve"): {"criteria_version": 1},
    ("PUT", "/v1/kit/questions/{question_id}"): {"question_text": "Why Python?"},
}
# Routes whose body is multipart: a JSON body would be a 422 for them.
FILES: dict[tuple[str, str], list[tuple[str, tuple[str, bytes, str]]]] = {
    ("POST", "/v1/roles/{role_id}/resumes"): [
        ("files", ("cv.pdf", pdf_bytes(), "application/pdf"))
    ],
}


@pytest.mark.parametrize(("method", "path", "who"), CELLS)
async def test_matrix_cell(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    roles: FakeRoles,
    criteria: FakeCriteria,
    uploads: FakeUploads,
    kit: FakeKit,
    method: str,
    path: str,
    who: str,
) -> None:
    role = roles.seed(status="approved")
    criteria.seed(role.id, "Python")
    question_id = kit.seed_question(role.id)
    url = path.replace("{role_id}", str(role.id)).replace("{question_id}", str(question_id))
    headers: dict[str, str] = {}
    if who != "anonymous":
        user = users.add(email=f"{who}@example.com", role=who)
        headers = (await sessions.sign_in(user)).unsafe_headers
        roles.assigned.add((role.id, user.id))  # lets an interviewer read the role

    response = await client.request(
        method,
        url,
        headers=headers,
        json=BODIES.get((method, path)),
        files=FILES.get((method, path)),
    )

    if who == "anonymous":
        assert (response.status_code, response.json()["error"]["code"]) == (401, "unauthenticated")
    elif who in MATRIX[(method, path)]:
        assert response.is_success
    else:
        assert (response.status_code, response.json()["error"]["code"]) == (403, "forbidden")


DB = "postgresql+asyncpg://postgres:postgres@localhost:5432/test"


def api_routes(routes: list[BaseRoute]) -> Iterator[tuple[str, APIRoute]]:
    """(path with prefixes, route) for every APIRoute, through nested includes.

    FastAPI keeps included routers as private `_IncludedRouter` branches; this walks them.
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield route.path, route
        elif isinstance(route, _IncludedRouter):
            for candidate in _flatten(route):
                if isinstance(candidate.original_route, APIRoute):
                    yield candidate.path, candidate.original_route


def _flatten(branch: _IncludedRouter) -> Iterator[_EffectiveRouteContext]:
    for candidate in branch.effective_candidates():
        if isinstance(candidate, _IncludedRouter):
            yield from _flatten(candidate)
        else:
            yield candidate


def calls(dependant: Dependant) -> Iterator[object]:
    for dep in dependant.dependencies:
        yield dep.call
        yield from calls(dep)


def unguarded(app: FastAPI) -> set[tuple[str, str]]:
    """Non-public routes with no MATRIX row or no `current_session` in their dependencies."""
    bad: set[tuple[str, str]] = set()
    for path, route in api_routes(app.routes):
        for method in route.methods or ():
            key = (method, path)
            if key in PUBLIC:
                continue
            if key not in MATRIX or current_session not in set(calls(route.dependant)):
                bad.add(key)
    return bad


def test_every_route_declares_a_role_and_the_matrix_matches_the_table() -> None:
    app = create_app(Settings(_env_file=None, env="test", database_url=DB))

    assert unguarded(app) == set()
    served = len([key for key in MATRIX if key[1].startswith("/v1/")]) + len(PUBLIC)
    assert len(list(api_routes(app.routes))) == served


def test_the_guard_flags_a_route_without_a_session_dependency() -> None:
    app = create_app(Settings(_env_file=None, env="test", database_url=DB))

    @app.get("/v1/open")
    async def open_route() -> dict[str, str]:
        return {}

    assert unguarded(app) == {("GET", "/v1/open")}
