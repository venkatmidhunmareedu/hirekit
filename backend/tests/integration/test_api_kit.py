"""The kit routes end to end against Postgres: real sessions, real rows, real job indexes."""

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
    interviewer_id: UUID
    tag: str


async def _sign_in(client: AsyncClient, email: str) -> AsyncClient:
    login = await client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    return client


@pytest.fixture
async def env(engine: AsyncEngine) -> AsyncIterator[Env]:
    tag = f"it62-{uuid4().hex[:12]}"
    factory = async_sessionmaker(engine, expire_on_commit=False)
    ids: dict[str, UUID] = {}
    async with factory.begin() as setup:
        for who in ("recruiter", "interviewer"):
            row = await setup.execute(
                text(
                    "INSERT INTO users(name, email, role, password_hash) "
                    "VALUES (:n, :e, :r, :h) RETURNING id"
                ),
                {"n": tag, "e": f"{who}-{tag}@example.com", "r": who, "h": hash_password(PASSWORD)},
            )
            ids[who] = row.scalar_one()
    settings = Settings(
        _env_file=None, env="test", database_url=os.environ["DATABASE_URL"], log_format="console"
    )
    app = create_app(settings)
    try:
        async with LifespanManager(app):
            transport = ASGITransport(app=app)
            async with (
                AsyncClient(transport=transport, base_url="http://test") as rec,
                AsyncClient(transport=transport, base_url="http://test") as inter,
            ):
                yield Env(
                    engine,
                    await _sign_in(rec, f"recruiter-{tag}@example.com"),
                    await _sign_in(inter, f"interviewer-{tag}@example.com"),
                    ids["interviewer"],
                    tag,
                )
    finally:
        async with factory.begin() as cleanup:
            like = {"t": f"{tag}%"}
            await cleanup.execute(
                text(
                    "DELETE FROM jobs WHERE role_id IN (SELECT id FROM roles WHERE title LIKE :t)"
                ),
                like,
            )
            await cleanup.execute(
                text(
                    "DELETE FROM candidates WHERE role_id IN "
                    "(SELECT id FROM roles WHERE title LIKE :t)"
                ),
                like,
            )
            await cleanup.execute(text("DELETE FROM roles WHERE title LIKE :t"), like)
            await cleanup.execute(text("DELETE FROM users WHERE name = :n"), {"n": tag})


async def make_role(env: Env, *, status: str = "approved", version: int = 3) -> UUID:
    async with env.engine.begin() as conn:
        row = await conn.execute(
            text(
                "INSERT INTO roles(title, job_description, status, criteria_version) "
                "VALUES (:t, 'Build.', :s, :v) RETURNING id"
            ),
            {"t": f"{env.tag} {uuid4().hex[:6]}", "s": status, "v": version},
        )
        return UUID(str(row.scalar_one()))


async def make_kit(env: Env, role_id: UUID, *, questions: int = 2, version: int = 3) -> list[UUID]:
    """A kit with one criterion and `questions` questions at positions 0, 1, ..."""
    async with env.engine.begin() as conn:
        criterion = (
            await conn.execute(
                text(
                    "INSERT INTO criteria(role_id, name, kind, weight, position) "
                    "VALUES (:r, 'Python', 'must_have', 3, 0) RETURNING id"
                ),
                {"r": role_id},
            )
        ).scalar_one()
        await conn.execute(
            text("INSERT INTO interview_kits(role_id, criteria_version) VALUES (:r, :v)"),
            {"r": role_id, "v": version},
        )
        ids = []
        for position in range(questions):
            row = await conn.execute(
                text(
                    "INSERT INTO questions(role_id, criterion_id, question_text, strong_answer, "
                    "weak_answer, position) VALUES (:r, :c, :q, 'strong', 'weak', :p) RETURNING id"
                ),
                {"r": role_id, "c": criterion, "q": f"Question {position}", "p": position},
            )
            ids.append(UUID(str(row.scalar_one())))
        return ids


async def assign_interviewer(env: Env, role_id: UUID) -> None:
    async with env.engine.begin() as conn:
        candidate = (
            await conn.execute(
                text(
                    "INSERT INTO candidates(role_id, file_name, content_hash) "
                    "VALUES (:r, 'cv.pdf', :h) RETURNING id"
                ),
                {"r": role_id, "h": uuid4().hex * 2},
            )
        ).scalar_one()
        await conn.execute(
            text("INSERT INTO assignments(candidate_id, user_id) VALUES (:c, :u)"),
            {"c": candidate, "u": env.interviewer_id},
        )


async def jobs_of(env: Env, role_id: UUID) -> list[tuple[object, ...]]:
    async with env.engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT type, status, criteria_version, question_id FROM jobs "
                "WHERE role_id = :r ORDER BY id"
            ),
            {"r": role_id},
        )
        return [tuple(r) for r in result]


async def test_generate_kit_enqueues_a_job_and_is_blocked_for_a_draft_role(env: Env) -> None:
    approved = await make_role(env, version=3)
    draft = await make_role(env, status="draft")

    ok = await env.recruiter.post(f"/v1/roles/{approved}/kit:generate")
    blocked = await env.recruiter.post(f"/v1/roles/{draft}/kit:generate")

    assert ok.status_code == 202
    assert await jobs_of(env, approved) == [("generate_kit", "queued", 3, None)]
    assert (blocked.status_code, blocked.json()["error"]["code"]) == (409, "role_not_approved")
    assert await jobs_of(env, draft) == []


async def test_a_second_generate_while_one_is_open_is_409_job_already_open(env: Env) -> None:
    role_id = await make_role(env)
    first = await env.recruiter.post(f"/v1/roles/{role_id}/kit:generate")

    second = await env.recruiter.post(f"/v1/roles/{role_id}/kit:generate")

    assert first.status_code == 202
    assert (second.status_code, second.json()["error"]["code"]) == (409, "job_already_open")
    assert len(await jobs_of(env, role_id)) == 1


async def test_generate_for_an_unknown_role_is_404(env: Env) -> None:
    response = await env.recruiter.post(f"/v1/roles/{uuid4()}/kit:generate")

    assert response.status_code == 404


async def test_after_an_edit_the_kit_reads_as_stale(env: Env) -> None:
    role_id = await make_role(env, version=3)
    await make_kit(env, role_id, version=3)
    fresh = (await env.recruiter.get(f"/v1/roles/{role_id}/kit")).json()

    async with env.engine.begin() as conn:
        await conn.execute(
            text("UPDATE roles SET criteria_version = 4 WHERE id = :r"), {"r": role_id}
        )
    stale = (await env.recruiter.get(f"/v1/roles/{role_id}/kit")).json()

    assert (fresh["stale"], stale["stale"], stale["criteria_version"]) == (False, True, 3)
    assert [q["position"] for q in stale["questions"]] == [0, 1]


async def test_a_role_with_no_kit_yet_is_404(env: Env) -> None:
    role_id = await make_role(env)

    response = await env.recruiter.get(f"/v1/roles/{role_id}/kit")

    assert response.status_code == 404


async def test_an_interviewer_reads_a_kit_only_when_assigned_a_candidate_in_it(env: Env) -> None:
    role_id = await make_role(env)
    await make_kit(env, role_id)
    other = await make_role(env)
    await make_kit(env, other)
    await assign_interviewer(env, role_id)

    allowed = await env.interviewer.get(f"/v1/roles/{role_id}/kit")
    refused = await env.interviewer.get(f"/v1/roles/{other}/kit")

    assert allowed.status_code == 200
    assert (refused.status_code, refused.json()["error"]["code"]) == (404, "not_found")


async def test_an_interviewer_cannot_write_the_kit(env: Env) -> None:
    role_id = await make_role(env)
    (question_id, _) = await make_kit(env, role_id)
    await assign_interviewer(env, role_id)

    calls = [
        await env.interviewer.post(f"/v1/roles/{role_id}/kit:generate"),
        await env.interviewer.put(f"/v1/kit/questions/{question_id}", json={"position": 5}),
        await env.interviewer.delete(f"/v1/kit/questions/{question_id}"),
        await env.interviewer.post(f"/v1/kit/questions/{question_id}:regenerate"),
    ]

    assert [c.status_code for c in calls] == [403, 403, 403, 403]
    assert await jobs_of(env, role_id) == []


async def test_editing_a_question_is_saved_and_the_interviewer_sees_the_edit(env: Env) -> None:
    role_id = await make_role(env)
    (question_id, _) = await make_kit(env, role_id)
    await assign_interviewer(env, role_id)

    edited = await env.recruiter.put(
        f"/v1/kit/questions/{question_id}", json={"question_text": "Rewritten", "position": 7}
    )

    seen = (await env.interviewer.get(f"/v1/roles/{role_id}/kit")).json()["questions"]
    assert edited.status_code == 200
    assert edited.json()["strong_answer"] == "strong"
    assert {(q["question_text"], q["position"]) for q in seen} == {
        ("Rewritten", 7),
        ("Question 1", 1),
    }


async def test_a_question_can_be_deleted_reordered_and_regenerated(env: Env) -> None:
    role_id = await make_role(env, version=3)
    (first, second) = await make_kit(env, role_id)

    reorder = await env.recruiter.put(f"/v1/kit/questions/{first}", json={"position": 9})
    delete = await env.recruiter.delete(f"/v1/kit/questions/{second}")
    again = await env.recruiter.delete(f"/v1/kit/questions/{second}")
    regenerate = await env.recruiter.post(f"/v1/kit/questions/{first}:regenerate")
    repeat = await env.recruiter.post(f"/v1/kit/questions/{first}:regenerate")

    assert (reorder.status_code, delete.status_code, again.status_code) == (200, 204, 404)
    assert regenerate.status_code == 202
    assert (repeat.status_code, repeat.json()["error"]["code"]) == (409, "job_already_open")
    assert await jobs_of(env, role_id) == [("regenerate_question", "queued", 3, first)]
    kit = (await env.recruiter.get(f"/v1/roles/{role_id}/kit")).json()
    assert [(q["id"], q["position"]) for q in kit["questions"]] == [(str(first), 9)]


async def test_regenerate_for_a_draft_role_or_unknown_question_enqueues_nothing(env: Env) -> None:
    role_id = await make_role(env)
    (question_id, _) = await make_kit(env, role_id)
    async with env.engine.begin() as conn:
        await conn.execute(text("UPDATE roles SET status = 'draft' WHERE id = :r"), {"r": role_id})

    draft = await env.recruiter.post(f"/v1/kit/questions/{question_id}:regenerate")
    unknown = await env.recruiter.post(f"/v1/kit/questions/{uuid4()}:regenerate")

    assert (draft.status_code, draft.json()["error"]["code"]) == (409, "role_not_approved")
    assert unknown.status_code == 404
    assert await jobs_of(env, role_id) == []
