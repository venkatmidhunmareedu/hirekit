"""The feedback routes end to end against Postgres: real sessions and rows (HK-63)."""

import hashlib
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
    stranger: AsyncClient
    interviewer_id: UUID
    candidate_id: UUID
    criteria: list[UUID]


async def sign_in(app_client: AsyncClient, email: str) -> None:
    login = await app_client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    app_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]


@pytest.fixture
async def env(engine: AsyncEngine) -> AsyncIterator[Env]:
    tag = f"it63-{uuid4().hex[:12]}"
    factory = async_sessionmaker(engine, expire_on_commit=False)
    ids: dict[str, UUID] = {}
    async with factory.begin() as setup:
        for who in ("recruiter", "interviewer", "stranger"):
            row = await setup.execute(
                text(
                    "INSERT INTO users(name, email, role, password_hash) "
                    "VALUES (:n, :e, :r, :h) RETURNING id"
                ),
                {
                    "n": tag,
                    "e": f"{who}-{tag}@example.com",
                    "r": "recruiter" if who == "recruiter" else "interviewer",
                    "h": hash_password(PASSWORD),
                },
            )
            ids[who] = row.scalar_one()
        role_id = (
            await setup.execute(
                text(
                    "INSERT INTO roles(title, job_description, status) "
                    "VALUES (:t, 'Build.', 'approved') RETURNING id"
                ),
                {"t": tag},
            )
        ).scalar_one()
        criteria: list[UUID] = []
        for position, name in enumerate(["Python", "SQL"]):
            criterion = await setup.execute(
                text(
                    "INSERT INTO criteria(role_id, name, kind, weight, position) "
                    "VALUES (:r, :n, 'must_have', 3, :p) RETURNING id"
                ),
                {"r": role_id, "n": name, "p": position},
            )
            criteria.append(criterion.scalar_one())
        candidate_id = (
            await setup.execute(
                text(
                    "INSERT INTO candidates(role_id, file_name, content_hash) "
                    "VALUES (:r, 'cv.pdf', :h) RETURNING id"
                ),
                {"r": role_id, "h": hashlib.sha256(tag.encode()).hexdigest()},
            )
        ).scalar_one()
        await setup.execute(
            text("INSERT INTO assignments(candidate_id, user_id) VALUES (:c, :u)"),
            {"c": candidate_id, "u": ids["interviewer"]},
        )
    app = create_app(
        Settings(
            _env_file=None,
            env="test",
            database_url=os.environ["DATABASE_URL"],
            log_format="console",
        )
    )
    try:
        async with LifespanManager(app):
            transport = ASGITransport(app=app)
            async with (
                AsyncClient(transport=transport, base_url="http://test") as recruiter,
                AsyncClient(transport=transport, base_url="http://test") as interviewer,
                AsyncClient(transport=transport, base_url="http://test") as stranger,
            ):
                await sign_in(recruiter, f"recruiter-{tag}@example.com")
                await sign_in(interviewer, f"interviewer-{tag}@example.com")
                await sign_in(stranger, f"stranger-{tag}@example.com")
                yield Env(
                    engine,
                    recruiter,
                    interviewer,
                    stranger,
                    ids["interviewer"],
                    candidate_id,
                    criteria,
                )
    finally:
        async with factory.begin() as cleanup:
            names = {"t": tag}
            await cleanup.execute(
                text(
                    "DELETE FROM audit_events WHERE candidate_id IN "
                    "(SELECT c.id FROM candidates c JOIN roles r ON r.id = c.role_id "
                    "WHERE r.title = :t)"
                ),
                names,
            )
            await cleanup.execute(
                text(
                    "DELETE FROM candidates WHERE role_id IN "
                    "(SELECT id FROM roles WHERE title = :t)"
                ),
                names,
            )
            await cleanup.execute(text("DELETE FROM roles WHERE title = :t"), names)
            await cleanup.execute(text("DELETE FROM users WHERE name = :t"), names)


def payload(env: Env, *, score: int = 3, comment: str = "Solid") -> dict[str, object]:
    return {
        "items": [
            {"criterion_id": str(c), "score": score, "comment": comment} for c in env.criteria
        ]
    }


def url(env: Env) -> str:
    return f"/v1/candidates/{env.candidate_id}/feedback"


async def test_submit_lock_approve_edit_and_audit_round_trip(env: Env) -> None:
    submitted = await env.interviewer.post(url(env), json=payload(env, comment="first"))
    again = await env.interviewer.post(url(env), json=payload(env))
    locked_put = await env.interviewer.put(url(env), json=payload(env))
    approved = await env.recruiter.post(f"{url(env)}/{env.interviewer_id}:approve-edit")
    edited = await env.interviewer.put(url(env), json=payload(env, score=4, comment="second"))
    async with env.engine.connect() as conn:
        audit = (
            await conn.execute(
                text(
                    "SELECT kind, old_score, new_score, old_comment, subject_user_id "
                    "FROM audit_events WHERE candidate_id = :c ORDER BY id"
                ),
                {"c": env.candidate_id},
            )
        ).all()

    assert submitted.status_code == 201
    assert [r["criterion_id"] for r in submitted.json()["data"]] == [str(c) for c in env.criteria]
    assert (again.status_code, again.json()["error"]["code"]) == (409, "feedback_locked")
    assert locked_put.status_code == 409
    assert [r["locked"] for r in approved.json()["data"]] == [False, False]
    assert [(r["score"], r["comment"], r["locked"]) for r in edited.json()["data"]] == [
        (4, "second", True)
    ] * 2
    assert [(a.kind, a.old_score, a.new_score, a.old_comment) for a in audit] == [
        ("feedback_edit_approved", None, None, None),
        ("feedback_edited", 3, 4, "first"),
        ("feedback_edited", 3, 4, "first"),
    ]
    assert {a.subject_user_id for a in audit} == {env.interviewer_id}


async def test_an_incomplete_submit_writes_nothing(env: Env) -> None:
    one = {"criterion_id": str(env.criteria[0]), "score": 3, "comment": "Solid"}

    response = await env.interviewer.post(url(env), json={"items": [one]})
    read = await env.recruiter.get(url(env))

    assert (response.status_code, response.json()["error"]["code"]) == (422, "incomplete_feedback")
    assert read.json() == {"data": []}


async def test_an_unassigned_interviewer_is_404_and_leaves_no_row(env: Env) -> None:
    posted = await env.stranger.post(url(env), json=payload(env))
    read = await env.stranger.get(url(env))
    read_all = await env.recruiter.get(url(env))

    assert (posted.status_code, read.status_code) == (404, 404)
    assert read_all.json() == {"data": []}


async def test_an_interviewer_reads_only_their_own_feedback(env: Env) -> None:
    await env.interviewer.post(url(env), json=payload(env))
    other = uuid4()
    async with env.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users(id, name, email, role, password_hash) "
                "SELECT :i, name, :e, 'interviewer', password_hash FROM users WHERE id = :u"
            ),
            {"i": other, "e": f"{other}@example.com", "u": env.interviewer_id},
        )
        await conn.execute(
            text(
                "INSERT INTO feedback(candidate_id, interviewer_id, criterion_id, score, comment) "
                "VALUES (:c, :i, :k, 1, 'theirs')"
            ),
            {"c": env.candidate_id, "i": other, "k": env.criteria[0]},
        )

    own = await env.interviewer.get(url(env))
    every = await env.recruiter.get(url(env))

    assert {r["interviewer_id"] for r in own.json()["data"]} == {str(env.interviewer_id)}
    assert {r["comment"] for r in every.json()["data"]} == {"Solid", "theirs"}
