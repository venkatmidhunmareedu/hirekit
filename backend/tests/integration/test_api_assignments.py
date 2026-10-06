"""Assignments and interviewer visibility end to end against Postgres (HK-61)."""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import Settings
from app.core.passwords import hash_password
from app.main import create_app

pytestmark = pytest.mark.integration

PASSWORD = f"pw-{uuid4().hex}"


@dataclass
class Env:
    engine: AsyncEngine
    recruiter: AsyncClient
    interviewer: AsyncClient
    other: AsyncClient
    interviewer_id: UUID
    other_id: UUID
    tag: str


async def sign_in(app_transport: ASGITransport, email: str) -> AsyncClient:
    client = AsyncClient(transport=app_transport, base_url="http://test")
    login = await client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    return client


@pytest.fixture
async def env(engine: AsyncEngine) -> AsyncIterator[Env]:
    tag = f"it61-{uuid4().hex[:12]}"
    factory = async_sessionmaker(engine, expire_on_commit=False)
    ids: dict[str, UUID] = {}
    async with factory.begin() as setup:
        for kind in ("recruiter", "interviewer", "other"):
            row = await setup.execute(
                text(
                    "INSERT INTO users(name, email, role, password_hash) "
                    "VALUES (:n, :e, :r, :h) RETURNING id"
                ),
                {
                    "n": tag,
                    "e": f"{kind}-{tag}@example.com",
                    "r": "recruiter" if kind == "recruiter" else "interviewer",
                    "h": hash_password(PASSWORD),
                },
            )
            ids[kind] = UUID(str(row.scalar_one()))
    settings = Settings(
        _env_file=None, env="test", database_url=os.environ["DATABASE_URL"], log_format="console"
    )
    app = create_app(settings)
    transport = ASGITransport(app=app)
    clients: list[AsyncClient] = []
    try:
        async with LifespanManager(app):
            for kind in ("recruiter", "interviewer", "other"):
                clients.append(await sign_in(transport, f"{kind}-{tag}@example.com"))
            yield Env(
                engine, clients[0], clients[1], clients[2], ids["interviewer"], ids["other"], tag
            )
    finally:
        for client in clients:
            await client.aclose()
        async with factory.begin() as cleanup:
            await cleanup.execute(
                text(
                    "DELETE FROM candidates WHERE role_id IN "
                    "(SELECT id FROM roles WHERE title LIKE :t)"
                ),
                {"t": f"{tag}%"},
            )
            await cleanup.execute(text("DELETE FROM roles WHERE title LIKE :t"), {"t": f"{tag}%"})
            await cleanup.execute(text("DELETE FROM users WHERE name = :n"), {"n": tag})


async def make_candidate(env: Env, label: str = "a") -> tuple[UUID, UUID]:
    """A role (approved) and one candidate in it; returns (role_id, candidate_id)."""
    async with env.engine.begin() as conn:
        role = await conn.execute(
            text(
                "INSERT INTO roles(title, job_description, status) "
                "VALUES (:t, 'Build.', 'approved') RETURNING id"
            ),
            {"t": f"{env.tag} {label}"},
        )
        role_id = UUID(str(role.scalar_one()))
        candidate = await conn.execute(
            text(
                "INSERT INTO candidates(role_id, file_name, content_hash) "
                "VALUES (:r, 'cv.pdf', :h) RETURNING id"
            ),
            {"r": role_id, "h": uuid4().hex * 2},
        )
        return role_id, UUID(str(candidate.scalar_one()))


async def assign(env: Env, candidate_id: UUID, user_id: UUID) -> int:
    response = await env.recruiter.post(
        f"/v1/candidates/{candidate_id}/assignments", json={"user_id": str(user_id)}
    )
    return response.status_code


async def mine(client: AsyncClient) -> list[dict[str, object]]:
    response = await client.get("/v1/me/candidates")
    assert response.status_code == 200
    data: list[dict[str, object]] = response.json()["data"]
    return data


async def pair_count(env: Env, candidate_id: UUID) -> int:
    async with env.engine.connect() as conn:
        result = await conn.execute(
            text("SELECT count(*) FROM assignments WHERE candidate_id = :c"), {"c": candidate_id}
        )
        return int(result.scalar_one())


async def test_assignment_makes_the_candidate_visible_to_that_interviewer_only(env: Env) -> None:
    role_id, candidate_id = await make_candidate(env)

    status = await assign(env, candidate_id, env.interviewer_id)

    assert status == 201
    assert await mine(env.other) == []
    listed = await mine(env.interviewer)
    assert [(c["candidate_id"], c["role_id"], c["has_submitted"]) for c in listed] == [
        (str(candidate_id), str(role_id), False)
    ]
    assert listed[0]["role_title"] == f"{env.tag} a"


async def test_removing_an_assignment_hides_the_candidate_and_the_role(env: Env) -> None:
    role_id, candidate_id = await make_candidate(env)
    await assign(env, candidate_id, env.interviewer_id)
    role_url = f"/v1/roles/{role_id}"
    assigned_read = await env.interviewer.get(role_url)

    removed = await env.recruiter.delete(
        f"/v1/candidates/{candidate_id}/assignments/{env.interviewer_id}"
    )
    again = await env.recruiter.delete(
        f"/v1/candidates/{candidate_id}/assignments/{env.interviewer_id}"
    )

    assert assigned_read.status_code == 200
    assert (removed.status_code, again.status_code) == (204, 204)
    assert await mine(env.interviewer) == []
    hidden = await env.interviewer.get(role_url)
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "not_found")


async def test_an_interviewer_reads_a_role_only_when_assigned_a_candidate_in_it(env: Env) -> None:
    role_id, candidate_id = await make_candidate(env)

    before = await env.interviewer.get(f"/v1/roles/{role_id}")
    await assign(env, candidate_id, env.interviewer_id)
    after = await env.interviewer.get(f"/v1/roles/{role_id}")
    other = await env.other.get(f"/v1/roles/{role_id}")

    assert (before.status_code, after.status_code, other.status_code) == (404, 200, 404)


async def test_a_repeated_assignment_is_one_row_and_not_a_500(env: Env) -> None:
    _, candidate_id = await make_candidate(env)

    statuses = [await assign(env, candidate_id, env.interviewer_id) for _ in range(2)]

    assert statuses == [201, 201]
    assert await pair_count(env, candidate_id) == 1


async def test_assigning_a_recruiter_or_unknown_user_or_candidate_is_refused_and_writes_nothing(
    env: Env,
) -> None:
    _, candidate_id = await make_candidate(env)
    recruiter_id = UUID(str((await env.recruiter.get("/v1/auth/me")).json()["user"]["id"]))

    to_recruiter = await assign(env, candidate_id, recruiter_id)
    to_unknown = await assign(env, candidate_id, uuid4())
    unknown_candidate = await assign(env, uuid4(), env.interviewer_id)

    assert (to_recruiter, to_unknown, unknown_candidate) == (422, 422, 404)
    assert await pair_count(env, candidate_id) == 0


async def test_an_interviewer_cannot_assign_or_unassign_and_sees_no_other_candidates(
    env: Env,
) -> None:
    _, candidate_id = await make_candidate(env)
    await assign(env, candidate_id, env.other_id)

    assigned = await env.interviewer.post(
        f"/v1/candidates/{candidate_id}/assignments", json={"user_id": str(env.interviewer_id)}
    )
    removed = await env.interviewer.delete(
        f"/v1/candidates/{candidate_id}/assignments/{env.other_id}"
    )
    recruiter_list = await env.recruiter.get("/v1/me/candidates")

    assert (assigned.status_code, removed.status_code, recruiter_list.status_code) == (
        403,
        403,
        403,
    )
    assert await mine(env.interviewer) == []
    assert await pair_count(env, candidate_id) == 1


async def test_has_submitted_is_true_once_the_interviewer_has_feedback_on_the_candidate(
    env: Env,
) -> None:
    role_id, candidate_id = await make_candidate(env)
    await assign(env, candidate_id, env.interviewer_id)
    await assign(env, candidate_id, env.other_id)
    async with env.engine.begin() as conn:
        criterion = await conn.execute(
            text(
                "INSERT INTO criteria(role_id, name, kind, weight, position) "
                "VALUES (:r, 'Python', 'must_have', 3, 0) RETURNING id"
            ),
            {"r": role_id},
        )
        await conn.execute(
            text(
                "INSERT INTO feedback(candidate_id, interviewer_id, criterion_id, score, comment) "
                "VALUES (:c, :i, :k, 3, 'solid')"
            ),
            {"c": candidate_id, "i": env.interviewer_id, "k": criterion.scalar_one()},
        )

    assert [c["has_submitted"] for c in await mine(env.interviewer)] == [True]
    assert [c["has_submitted"] for c in await mine(env.other)] == [False]


async def test_a_recruiter_lists_interviewers_without_email_and_not_recruiters(env: Env) -> None:
    response = await env.recruiter.get("/v1/users", params={"role": "interviewer", "limit": 200})

    assert response.status_code == 200
    data = response.json()["data"]
    mine_listed = [u for u in data if u["name"] == env.tag]
    assert sorted(u["id"] for u in mine_listed) == sorted(
        [str(env.interviewer_id), str(env.other_id)]
    )
    assert all(set(u) == {"id", "name"} for u in data)
    assert (await env.recruiter.get("/v1/users", params={"role": "recruiter"})).status_code == 422
    assert (await env.interviewer.get("/v1/users?role=interviewer")).status_code == 403


async def test_assignments_persist_and_list_by_name_for_the_candidate(env: Env) -> None:
    _, candidate_id = await make_candidate(env)
    _, other_candidate = await make_candidate(env, "b")
    await assign(env, candidate_id, env.interviewer_id)
    await assign(env, other_candidate, env.other_id)
    url = f"/v1/candidates/{candidate_id}/assignments"

    listed = await env.recruiter.get(url)
    await env.recruiter.delete(f"{url}/{env.interviewer_id}")
    emptied = await env.recruiter.get(url)
    unknown = await env.recruiter.get(f"/v1/candidates/{uuid4()}/assignments")
    forbidden = await env.interviewer.get(url)

    assert listed.json() == {"data": [{"user_id": str(env.interviewer_id), "name": env.tag}]}
    assert emptied.json() == {"data": []}
    assert (unknown.status_code, forbidden.status_code) == (404, 403)
