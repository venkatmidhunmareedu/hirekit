"""The role routes end to end against Postgres: real sessions, real transactions, real rows."""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import Settings
from app.core.passwords import hash_password
from app.main import create_app

pytestmark = pytest.mark.integration

PASSWORD = f"pw-{uuid4().hex}"
RUBRIC = [{"level": n, "descriptor": f"level {n}"} for n in range(5)]


@dataclass
class Env:
    engine: AsyncEngine
    recruiter: AsyncClient
    interviewer: AsyncClient
    interviewer_id: UUID
    tag: str


def crit(name: str, **over: object) -> dict[str, object]:
    return {"name": name, "kind": "must_have", "weight": 3, "rubric": RUBRIC, **over}


async def _sign_in(app_client: AsyncClient, email: str) -> AsyncClient:
    login = await app_client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    app_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    return app_client


@pytest.fixture
async def env(engine: AsyncEngine) -> AsyncIterator[Env]:
    tag = f"it53-{uuid4().hex[:12]}"
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
                    "DELETE FROM candidates WHERE role_id IN "
                    "(SELECT id FROM roles WHERE title LIKE :t)"
                ),
                like,
            )
            await cleanup.execute(text("DELETE FROM roles WHERE title LIKE :t"), like)
            await cleanup.execute(text("DELETE FROM users WHERE name = :n"), {"n": tag})


async def make_role(env: Env, suffix: str = "") -> UUID:
    response = await env.recruiter.post(
        "/v1/roles", json={"title": f"{env.tag} {suffix}", "job_description": "Build."}
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


async def replace(env: Env, role_id: UUID, items: list[dict[str, object]]) -> Response:
    return await env.recruiter.put(f"/v1/roles/{role_id}/criteria", json={"criteria": items})


async def approve(env: Env, role_id: UUID, version: int) -> Response:
    return await env.recruiter.post(
        f"/v1/roles/{role_id}/approve", json={"criteria_version": version}
    )


async def test_list_roles_newest_first_capped_at_50(env: Env) -> None:
    first, second, third = [await make_role(env, str(n)) for n in range(3)]

    ordered = [r["id"] for r in (await env.recruiter.get("/v1/roles")).json()["data"]]

    mine = [i for i in ordered if i in {str(first), str(second), str(third)}]
    assert mine == [str(third), str(second), str(first)]
    async with env.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO roles(title, job_description) "
                "SELECT :t || ' bulk ' || n, 'x' FROM generate_series(1, 52) n"
            ),
            {"t": env.tag},
        )
    assert len((await env.recruiter.get("/v1/roles")).json()["data"]) == 50


async def test_replace_criteria_saves_reorder_edit_and_delete_by_retiring(env: Env) -> None:
    role_id = await make_role(env)
    body = (await replace(env, role_id, [crit("A"), crit("B"), crit("C")])).json()
    a, b, c = [x["id"] for x in body["criteria"]]
    assert [x["position"] for x in body["criteria"]] == [0, 1, 2]

    after = (
        await replace(
            env,
            role_id,
            [crit("C", id=c), crit("A edited", id=a, weight=5, rubric=RUBRIC[:2]), crit("New")],
        )
    ).json()

    live = after["criteria"]
    assert [x["name"] for x in live] == ["C", "A edited", "New"]
    assert [x["id"] for x in live][:2] == [c, a]
    assert live[1]["weight"] == 5.0
    assert len(live[1]["rubric"]) == 2
    async with env.engine.connect() as conn:
        retired = (
            await conn.execute(
                text("SELECT retired_at IS NOT NULL FROM criteria WHERE id = :i"), {"i": b}
            )
        ).scalar_one()
    assert retired is True


async def test_replace_with_foreign_criterion_id_is_422(env: Env) -> None:
    mine, theirs = await make_role(env, "mine"), await make_role(env, "theirs")
    foreign = (await replace(env, theirs, [crit("Theirs")])).json()["criteria"][0]["id"]

    response = await env.recruiter.put(
        f"/v1/roles/{mine}/criteria", json={"criteria": [crit("Mine", id=foreign)]}
    )

    assert (response.status_code, response.json()["error"]["code"]) == (422, "validation_error")
    still = await env.recruiter.get(f"/v1/roles/{theirs}")
    assert len(still.json()["criteria"]) == 1


async def test_editing_an_approved_role_returns_it_to_draft_and_bumps_the_version(env: Env) -> None:
    role_id = await make_role(env)
    done = (await replace(env, role_id, [crit("A")])).json()
    assert (await approve(env, role_id, done["criteria_version"])).status_code == 200

    edited = (await replace(env, role_id, [crit("A")])).json()

    assert (edited["status"], edited["criteria_version"]) == ("draft", 3)


async def test_replace_leaves_score_rows_untouched(env: Env) -> None:
    role_id = await make_role(env)
    body = (await replace(env, role_id, [crit("A"), crit("B")])).json()
    a, b = [x["id"] for x in body["criteria"]]
    async with env.engine.begin() as conn:
        candidate = (
            await conn.execute(
                text(
                    "INSERT INTO candidates(role_id, file_name, content_hash) "
                    "VALUES (:r, 'cv.pdf', :h) RETURNING id"
                ),
                {"r": role_id, "h": "a" * 64},
            )
        ).scalar_one()
        for criterion in (a, b):
            await conn.execute(
                text(
                    "INSERT INTO scores(candidate_id, criterion_id, criteria_version, status, "
                    "model_score, quote) VALUES (:c, :k, 2, 'scored', 3, 'q')"
                ),
                {"c": candidate, "k": criterion},
            )

    await replace(env, role_id, [crit("A", id=a)])  # B is retired, A edited

    async with env.engine.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT criterion_id::text, model_score FROM scores WHERE candidate_id = :c"),
                {"c": candidate},
            )
        ).all()
    assert sorted(rows) == sorted([(a, 3), (b, 3)])


async def test_approve_with_changed_version_is_409_criteria_changed(env: Env) -> None:
    role_id = await make_role(env)
    await replace(env, role_id, [crit("A")])  # version is now 2

    response = await approve(env, role_id, 1)

    assert (response.status_code, response.json()["error"]["code"]) == (409, "criteria_changed")
    assert response.json()["error"]["details"] == {"current_version": 2}


async def test_approve_checks_rubric_and_is_idempotent(env: Env) -> None:
    role_id = await make_role(env)
    assert (await approve(env, role_id, 1)).status_code == 422  # no criteria
    short = (await replace(env, role_id, [crit("A", rubric=RUBRIC[:3])])).json()
    incomplete = await approve(env, role_id, 2)
    assert incomplete.json()["error"]["code"] == "incomplete_rubric"
    await replace(env, role_id, [crit("A", id=short["criteria"][0]["id"])])

    first = await approve(env, role_id, 3)
    second = await approve(env, role_id, 3)

    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json() == first.json()
    assert first.json()["status"] == "approved"


async def test_interviewer_reads_role_only_with_assigned_candidate_else_404(env: Env) -> None:
    role_id = await make_role(env, "assigned")
    other = await make_role(env, "other")
    before = await env.interviewer.get(f"/v1/roles/{role_id}")
    async with env.engine.begin() as conn:
        candidate = (
            await conn.execute(
                text(
                    "INSERT INTO candidates(role_id, file_name, content_hash) "
                    "VALUES (:r, 'cv.pdf', :h) RETURNING id"
                ),
                {"r": role_id, "h": "b" * 64},
            )
        ).scalar_one()
        await conn.execute(
            text("INSERT INTO assignments(candidate_id, user_id) VALUES (:c, :u)"),
            {"c": candidate, "u": env.interviewer_id},
        )

    after = await env.interviewer.get(f"/v1/roles/{role_id}")
    elsewhere = await env.interviewer.get(f"/v1/roles/{other}")

    assert (before.status_code, after.status_code, elsewhere.status_code) == (404, 200, 404)
