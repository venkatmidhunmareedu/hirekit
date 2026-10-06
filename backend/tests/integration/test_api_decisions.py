"""Override, stage and reveal against Postgres: real sessions, locks, audit rows and checks."""

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
NOTE = "Led the migration, seen in the interview"


@dataclass
class Env:
    engine: AsyncEngine
    client: AsyncClient
    tag: str
    role_id: UUID
    candidate_id: UUID
    criterion_id: UUID
    user_id: UUID


@pytest.fixture
async def env(engine: AsyncEngine) -> AsyncIterator[Env]:
    tag = f"it60-{uuid4().hex[:12]}"
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory.begin() as setup:
        user_id = (
            await setup.execute(
                text(
                    "INSERT INTO users(name, email, role, password_hash) "
                    "VALUES (:n, :e, 'recruiter', :h) RETURNING id"
                ),
                {"n": tag, "e": f"r-{tag}@example.com", "h": hash_password(PASSWORD)},
            )
        ).scalar_one()
        role_id = (
            await setup.execute(
                text(
                    "INSERT INTO roles(title, job_description, status, criteria_version) "
                    "VALUES (:t, 'Build.', 'approved', 2) RETURNING id"
                ),
                {"t": tag},
            )
        ).scalar_one()
        criterion_id = (
            await setup.execute(
                text(
                    "INSERT INTO criteria(role_id, name, kind, weight, position) "
                    "VALUES (:r, 'Python', 'must_have', 3, 0) RETURNING id"
                ),
                {"r": role_id},
            )
        ).scalar_one()
        candidate_id = (
            await setup.execute(
                text(
                    "INSERT INTO candidates(role_id, file_name, content_hash, identity_name) "
                    "VALUES (:r, 'Jane_Doe_CV.pdf', :h, 'Jane Doe') RETURNING id"
                ),
                {"r": role_id, "h": uuid4().hex + uuid4().hex},
            )
        ).scalar_one()
        for version, score in ((1, 1), (2, 2)):
            await setup.execute(
                text(
                    "INSERT INTO scores(candidate_id, criterion_id, criteria_version, status, "
                    "model_score, quote) VALUES (:c, :k, :v, 'scored', :s, 'Built a service')"
                ),
                {"c": candidate_id, "k": criterion_id, "v": version, "s": score},
            )
    settings = Settings(
        _env_file=None, env="test", database_url=os.environ["DATABASE_URL"], log_format="console"
    )
    app = create_app(settings)
    try:
        async with (
            LifespanManager(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            login = await client.post(
                "/v1/auth/login", json={"email": f"r-{tag}@example.com", "password": PASSWORD}
            )
            assert login.status_code == 200, login.text
            client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
            yield Env(engine, client, tag, role_id, candidate_id, criterion_id, user_id)
    finally:
        async with factory.begin() as cleanup:
            await cleanup.execute(
                text("DELETE FROM audit_events WHERE candidate_id = :c"), {"c": candidate_id}
            )
            await cleanup.execute(text("DELETE FROM candidates WHERE id = :c"), {"c": candidate_id})
            await cleanup.execute(text("DELETE FROM criteria WHERE role_id = :r"), {"r": role_id})
            await cleanup.execute(text("DELETE FROM roles WHERE id = :r"), {"r": role_id})
            await cleanup.execute(text("DELETE FROM users WHERE name = :n"), {"n": tag})


async def query(env: Env, sql: str, **params: object) -> list[tuple[object, ...]]:
    async with env.engine.connect() as conn:
        return [tuple(r) for r in await conn.execute(text(sql), params)]


def override_url(env: Env, criterion: UUID | None = None) -> str:
    return f"/v1/candidates/{env.candidate_id}/scores/{criterion or env.criterion_id}/override"


async def test_override_keeps_the_model_value_and_writes_the_audit_row(env: Env) -> None:
    response = await env.client.put(override_url(env), json={"override_score": 4, "note": NOTE})

    assert response.status_code == 200, response.text
    assert await query(
        env,
        "SELECT model_score, override_score, override_note, overridden_by FROM scores "
        "WHERE candidate_id = :c AND criteria_version = 2",
        c=env.candidate_id,
    ) == [(2, 4, NOTE, env.user_id)]
    assert await query(
        env,
        "SELECT kind, actor_id, criterion_name, old_score, new_score, note FROM audit_events "
        "WHERE candidate_id = :c",
        c=env.candidate_id,
    ) == [("score_override", env.user_id, "Python", 2, 4, NOTE)]


async def test_override_touches_only_the_current_criteria_version(env: Env) -> None:
    await env.client.put(override_url(env), json={"override_score": 4, "note": NOTE})

    assert await query(
        env,
        "SELECT override_score FROM scores WHERE candidate_id = :c AND criteria_version = 1",
        c=env.candidate_id,
    ) == [(None,)]


async def test_override_of_a_stale_score_is_409(env: Env) -> None:
    async with env.engine.begin() as conn:
        await conn.execute(
            text("UPDATE roles SET criteria_version = 3 WHERE id = :r"), {"r": env.role_id}
        )

    response = await env.client.put(override_url(env), json={"override_score": 4, "note": NOTE})

    assert (response.status_code, response.json()["error"]["code"]) == (409, "scores_stale")
    assert (
        await query(env, "SELECT 1 FROM audit_events WHERE candidate_id = :c", c=env.candidate_id)
        == []
    )


async def test_override_of_a_criterion_from_another_role_is_404(env: Env) -> None:
    response = await env.client.put(
        override_url(env, uuid4()), json={"override_score": 4, "note": NOTE}
    )

    assert response.status_code == 404


async def test_stage_change_writes_from_to_user_and_reason(env: Env) -> None:
    response = await env.client.post(
        f"/v1/candidates/{env.candidate_id}/stage",
        json={"stage": "rejected", "reason": "Missing a must-have"},
    )

    assert response.status_code == 200, response.text
    assert await query(
        env, "SELECT CAST(stage AS text) FROM candidates WHERE id = :c", c=env.candidate_id
    ) == [("rejected",)]
    assert await query(
        env,
        "SELECT kind, actor_id, CAST(from_stage AS text), CAST(to_stage AS text), note "
        "FROM audit_events WHERE candidate_id = :c",
        c=env.candidate_id,
    ) == [("stage_change", env.user_id, "new", "rejected", "Missing a must-have")]


async def test_stage_to_the_same_stage_is_409_and_writes_no_audit_row(env: Env) -> None:
    response = await env.client.post(
        f"/v1/candidates/{env.candidate_id}/stage", json={"stage": "new"}
    )

    assert (response.status_code, response.json()["error"]["code"]) == (409, "same_stage")
    assert (
        await query(env, "SELECT 1 FROM audit_events WHERE candidate_id = :c", c=env.candidate_id)
        == []
    )


async def test_reveal_returns_the_identity_after_the_audit_row_is_stored(env: Env) -> None:
    response = await env.client.post(f"/v1/candidates/{env.candidate_id}:reveal-identity")

    assert response.json() == {"identity_name": "Jane Doe", "file_name": "Jane_Doe_CV.pdf"}
    assert await query(
        env,
        "SELECT kind, actor_id FROM audit_events WHERE candidate_id = :c",
        c=env.candidate_id,
    ) == [("identity_reveal", env.user_id)]


async def test_a_reveal_is_audited_each_time(env: Env) -> None:
    for _ in range(2):
        await env.client.post(f"/v1/candidates/{env.candidate_id}:reveal-identity")

    assert await query(
        env, "SELECT count(*) FROM audit_events WHERE candidate_id = :c", c=env.candidate_id
    ) == [(2,)]


async def test_an_unknown_candidate_is_404_for_all_three(env: Env) -> None:
    ghost = uuid4()

    responses = [
        await env.client.put(
            f"/v1/candidates/{ghost}/scores/{env.criterion_id}/override",
            json={"override_score": 4, "note": NOTE},
        ),
        await env.client.post(f"/v1/candidates/{ghost}/stage", json={"stage": "offer"}),
        await env.client.post(f"/v1/candidates/{ghost}:reveal-identity"),
    ]

    assert [r.status_code for r in responses] == [404, 404, 404]
