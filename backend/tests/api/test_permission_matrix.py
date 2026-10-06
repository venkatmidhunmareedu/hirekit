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

from app.api.candidates.router import get_candidates
from app.core.auth import CurrentUser, InterviewerUser, RecruiterUser, current_session
from app.core.config import Settings
from app.db.models import UserSession
from app.main import create_app
from tests.api.fake_assignments import FakeAssignments
from tests.api.fake_candidates import FakeCandidates
from tests.api.fake_compare import FakeCompare
from tests.api.fake_decisions import FakeAudit, FakeDecisions
from tests.api.fakes import (
    FakeCost,
    FakeCriteria,
    FakeFeedback,
    FakeJobs,
    FakeKit,
    FakeRoles,
    FakeScoringJobs,
    FakeSessions,
    FakeUploads,
    FakeUsers,
)
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
    ("POST", "/v1/candidates/{candidate_id}/feedback"): frozenset({"interviewer"}),
    ("GET", "/v1/candidates/{candidate_id}/feedback"): frozenset({"recruiter", "interviewer"}),
    ("PUT", "/v1/candidates/{candidate_id}/feedback"): frozenset({"interviewer"}),
    ("POST", "/v1/candidates/{candidate_id}/feedback/{interviewer_id}:approve-edit"): frozenset(
        {"recruiter"}
    ),
    ("POST", "/v1/roles/{role_id}/kit:generate"): frozenset({"recruiter"}),
    ("GET", "/v1/roles/{role_id}/kit"): frozenset({"recruiter", "interviewer"}),
    ("PUT", "/v1/kit/questions/{question_id}"): frozenset({"recruiter"}),
    ("DELETE", "/v1/kit/questions/{question_id}"): frozenset({"recruiter"}),
    ("POST", "/v1/kit/questions/{question_id}:regenerate"): frozenset({"recruiter"}),
    ("POST", "/v1/roles/{role_id}:rescore"): frozenset({"recruiter"}),
    ("POST", "/v1/candidates/{candidate_id}:retry"): frozenset({"recruiter"}),
    ("GET", "/v1/cost-log"): frozenset({"recruiter"}),
    ("PUT", "/v1/candidates/{candidate_id}/scores/{criterion_id}/override"): frozenset(
        {"recruiter"}
    ),
    ("POST", "/v1/candidates/{candidate_id}/stage"): frozenset({"recruiter"}),
    ("POST", "/v1/candidates/{candidate_id}:reveal-identity"): frozenset({"recruiter"}),
    ("GET", "/v1/roles/{role_id}/candidates"): frozenset({"recruiter"}),
    ("GET", "/v1/candidates/{candidate_id}"): frozenset({"recruiter", "interviewer"}),
    ("GET", "/v1/candidates/{candidate_id}/text"): frozenset({"recruiter"}),
    ("GET", "/v1/compare"): frozenset({"recruiter", "interviewer"}),
    ("GET", "/v1/me/candidates"): frozenset({"interviewer"}),
    ("GET", "/v1/users"): frozenset({"recruiter"}),
    ("GET", "/v1/candidates/{candidate_id}/assignments"): frozenset({"recruiter"}),
    ("POST", "/v1/candidates/{candidate_id}/assignments"): frozenset({"recruiter"}),
    ("DELETE", "/v1/candidates/{candidate_id}/assignments/{user_id}"): frozenset({"recruiter"}),
    ("POST", "/v1/roles/{role_id}/criteria:propose"): frozenset({"recruiter"}),
    ("GET", "/v1/roles/{role_id}/queue"): frozenset({"recruiter"}),
    ("GET", "/v1/jobs/{job_id}"): frozenset({"recruiter"}),
    ("POST", "/v1/jobs/{job_id}:cancel"): frozenset({"recruiter"}),
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
    fake = FakeCandidates(
        permissive=True
    )  # the matrix checks roles; row visibility has its own tests
    app.dependency_overrides[get_candidates] = lambda: fake


FULL_RUBRIC = [{"level": n, "descriptor": f"level {n}"} for n in range(5)]
BODIES: dict[tuple[str, str], dict[str, object]] = {
    ("POST", "/v1/roles"): {"title": "Engineer", "job_description": "Build."},
    ("PUT", "/v1/roles/{role_id}/criteria"): {
        "criteria": [{"name": "Python", "kind": "must_have", "weight": 3, "rubric": FULL_RUBRIC}]
    },
    ("POST", "/v1/roles/{role_id}/approve"): {"criteria_version": 1},
    ("PUT", "/v1/kit/questions/{question_id}"): {"question_text": "Why Python?"},
    ("PUT", "/v1/candidates/{candidate_id}/scores/{criterion_id}/override"): {
        "override_score": 4,
        "note": "Seen in the interview notes",
    },
    ("POST", "/v1/candidates/{candidate_id}/stage"): {"stage": "screened"},
    ("POST", "/v1/candidates/{candidate_id}/assignments"): {"user_id": "{user_id}"},
}
# Required query parameters, by path.
QUERY: dict[str, dict[str, str]] = {"/v1/users": {"role": "interviewer"}}
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
    feedback: FakeFeedback,
    kit: FakeKit,
    scoring_jobs: FakeScoringJobs,
    costs: FakeCost,
    decisions: FakeDecisions,
    audit: FakeAudit,
    compare: FakeCompare,
    assignments: FakeAssignments,
    jobs: FakeJobs,
    method: str,
    path: str,
    who: str,
) -> None:
    role = roles.seed(status="approved")
    draft = roles.seed(status="draft")  # criteria:propose accepts only a Draft role
    criterion = criteria.seed(role.id, "Python")
    job = jobs.seed(role.id, kind="generate_kit")
    question_id = kit.seed_question(role.id)
    _, candidate_id, criterion_id = decisions.seed()
    # One candidate id that the decisions, scoring and assignments fakes all know.
    scoring_jobs.candidates[candidate_id] = (role.id, 1)
    scoring_jobs.needs.add(candidate_id)
    assignments.seed_candidate(candidate_id=candidate_id)
    target = users.add(email="target@example.com", role="interviewer")
    url = (
        path.replace("{role_id}", str(draft.id if path.endswith(":propose") else role.id))
        .replace("{job_id}", str(job.id))
        .replace("{question_id}", str(question_id))
        .replace("{candidate_id}", str(candidate_id))
        .replace("{criterion_id}", str(criterion_id))
        .replace("{user_id}", str(target.id))
    )
    two = [compare.seed(role.id), compare.seed(role.id)]
    body = BODIES.get((method, path))
    if body:
        body = {k: str(target.id) if v == "{user_id}" else v for k, v in body.items()}
    headers: dict[str, str] = {}
    if who != "anonymous":
        user = users.add(email=f"{who}@example.com", role=who)
        headers = (await sessions.sign_in(user)).unsafe_headers
        roles.assigned.add((role.id, user.id))  # lets an interviewer read the role
        for compared in two:
            compare.assigned.add((compared, user.id))
    # Feedback routes: the same candidate, assigned to the caller, and the rows each route expects.
    feedback.role_of[candidate_id] = role.id
    feedback.assigned |= {(candidate_id, u.id) for u in users.rows}
    submitted_by = users.add(email="submitted@example.com", role="interviewer")
    caller = next((u for u in users.rows if u.email == f"{who}@example.com"), submitted_by)
    feedback.assigned.add((candidate_id, submitted_by.id))
    feedback_owner = submitted_by.id if "approve-edit" in path else caller.id
    if method != "POST" or "approve-edit" in path:
        feedback.seed(candidate_id, feedback_owner, criterion.id, locked="approve-edit" in path)
    url = url.replace("{interviewer_id}", str(submitted_by.id))
    item = {"criterion_id": str(criterion.id), "score": 3, "comment": "Solid"}

    response = await client.request(
        method,
        url,
        headers=headers,
        json={"items": [item]} if "/feedback" in path else body,
        files=FILES.get((method, path)),
        params=QUERY.get(path)
        or ({"ids": ",".join(map(str, two))} if path == "/v1/compare" else None),
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
