"""GET /v1/compare against Postgres: real SQL, real visibility predicates."""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import event, text
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
    other_interviewer_id: UUID
    role_id: UUID
    must: UUID
    nice: UUID
    app: FastAPI


async def sign_in(app_client: AsyncClient, email: str) -> None:
    login = await app_client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    app_client.headers["X-CSRF-Token"] = login.json()["csrf_token"]


@pytest.fixture
async def env(engine: AsyncEngine) -> AsyncIterator[Env]:
    tag = f"it64-{uuid4().hex[:12]}"
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory.begin() as setup:
        ids: dict[str, UUID] = {}
        for who in ("recruiter", "interviewer", "other"):
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
        role = await setup.execute(
            text(
                "INSERT INTO roles(title, job_description, status, criteria_version) "
                "VALUES (:t, 'Build.', 'approved', 1) RETURNING id"
            ),
            {"t": tag},
        )
        role_id = role.scalar_one()
        criteria: list[UUID] = []
        for position, (name, kind) in enumerate([("Go", "nice_to_have"), ("Python", "must_have")]):
            row = await setup.execute(
                text(
                    "INSERT INTO criteria(role_id, name, kind, weight, position) "
                    "VALUES (:r, :n, :k, 3, :p) RETURNING id"
                ),
                {"r": role_id, "n": name, "k": kind, "p": position},
            )
            criteria.append(row.scalar_one())
    settings = Settings(
        _env_file=None, env="test", database_url=os.environ["DATABASE_URL"], log_format="console"
    )
    app = create_app(settings)
    try:
        async with (
            LifespanManager(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as recruiter,
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as interviewer,
        ):
            await sign_in(recruiter, f"recruiter-{tag}@example.com")
            await sign_in(interviewer, f"interviewer-{tag}@example.com")
            env = Env(
                engine,
                recruiter,
                interviewer,
                ids["interviewer"],
                ids["other"],
                role_id,
                criteria[1],
                criteria[0],
                app,
            )
            yield env
    finally:
        async with factory.begin() as cleanup:
            await cleanup.execute(text("DELETE FROM candidates WHERE role_id = :r"), {"r": role_id})
            await cleanup.execute(text("DELETE FROM criteria WHERE role_id = :r"), {"r": role_id})
            await cleanup.execute(text("DELETE FROM roles WHERE id = :r"), {"r": role_id})
            await cleanup.execute(text("DELETE FROM users WHERE name = :n"), {"n": tag})


async def candidate(env: Env, *, assign: bool = False, role_id: UUID | None = None) -> UUID:
    async with env.engine.begin() as conn:
        row = await conn.execute(
            text(
                "INSERT INTO candidates(role_id, file_name, content_hash) "
                "VALUES (:r, 'cv.pdf', :h) RETURNING id"
            ),
            {"r": role_id or env.role_id, "h": uuid4().hex + uuid4().hex},
        )
        candidate_id: UUID = row.scalar_one()
        if assign:
            await conn.execute(
                text("INSERT INTO assignments(candidate_id, user_id) VALUES (:c, :u)"),
                {"c": candidate_id, "u": env.interviewer_id},
            )
    return candidate_id


async def score(
    env: Env,
    candidate_id: UUID,
    criterion: UUID,
    model: int,
    *,
    override: int | None = None,
    version: int = 1,
) -> None:
    async with env.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO scores(candidate_id, criterion_id, criteria_version, status, "
                "model_score, quote, override_score, override_note, overridden_by) "
                "VALUES (:c, :k, :v, 'scored', :m, 'SECRET QUOTE', :o, :n, :u)"
            ),
            {
                "c": candidate_id,
                "k": criterion,
                "v": version,
                "m": model,
                "o": override,
                "n": None if override is None else "a long enough override note",
                "u": None if override is None else (await _any_user(env)),
            },
        )


async def _any_user(env: Env) -> UUID:
    async with env.engine.connect() as conn:
        row = await conn.execute(text("SELECT id FROM users WHERE role = 'recruiter' LIMIT 1"))
        return UUID(str(row.scalar_one()))


async def feedback(
    env: Env, candidate_id: UUID, interviewer: UUID, criterion: UUID, n: int
) -> None:
    async with env.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO feedback(candidate_id, interviewer_id, criterion_id, score, comment) "
                "VALUES (:c, :i, :k, :s, 'solid')"
            ),
            {"c": candidate_id, "i": interviewer, "k": criterion, "s": n},
        )


async def compare(client: AsyncClient, *ids: UUID) -> Response:
    return await client.get("/v1/compare", params={"ids": ",".join(map(str, ids))})


async def test_compare_groups_criteria_by_kind_with_score_override_and_feedback(env: Env) -> None:
    a, b = await candidate(env), await candidate(env)
    await score(env, a, env.must, 3, override=4)
    await score(env, a, env.nice, 1)
    await score(env, b, env.must, 2)
    await feedback(env, a, env.interviewer_id, env.must, 1)
    await feedback(env, a, env.other_interviewer_id, env.must, 4)

    response = await compare(env.recruiter, a, b)

    body = response.json()
    assert response.status_code == 200, response.text
    assert [c["name"] for c in body["criteria"]] == ["Python", "Go"]
    first, second = body["candidates"]
    must_a, nice_a = first["cells"]
    assert (must_a["model_score"], must_a["override_score"]) == (3, 4)
    assert (nice_a["model_score"], nice_a["override_score"]) == (1, None)
    assert [f["score"] for f in must_a["feedback"]] == sorted(
        [1, 4], key=lambda s: str(env.interviewer_id if s == 1 else env.other_interviewer_id)
    )
    assert must_a["disagreement"] is True
    assert second["cells"][0]["model_score"] == 2
    assert second["cells"][1]["model_score"] is None
    assert "SECRET QUOTE" not in response.text


async def test_compare_uses_the_latest_scoring_version_of_each_candidate(env: Env) -> None:
    a, b = await candidate(env), await candidate(env)
    await score(env, a, env.must, 1, version=1)
    await score(env, a, env.must, 4, version=2)
    await score(env, b, env.must, 2)

    body = (await compare(env.recruiter, a, b)).json()

    assert body["candidates"][0]["cells"][0]["model_score"] == 4


async def test_compare_with_one_unassigned_id_is_404_for_the_whole_request(env: Env) -> None:
    mine, theirs = await candidate(env, assign=True), await candidate(env)
    await score(env, mine, env.must, 3)

    response = await compare(env.interviewer, mine, theirs)

    assert (response.status_code, response.json()["error"]["code"]) == (404, "not_found")
    assert "3" not in response.json()["error"]["message"]


async def test_compare_hides_scores_and_overrides_until_the_interviewer_has_submitted(
    env: Env,
) -> None:
    done, todo = await candidate(env, assign=True), await candidate(env, assign=True)
    for c in (done, todo):
        await score(env, c, env.must, 3, override=4)
    await feedback(env, done, env.interviewer_id, env.must, 2)
    await feedback(env, done, env.other_interviewer_id, env.must, 4)
    await feedback(env, todo, env.other_interviewer_id, env.must, 4)

    response = await compare(env.interviewer, done, todo)

    first, second = response.json()["candidates"]
    assert (first["cells"][0]["model_score"], first["cells"][0]["override_score"]) == (3, 4)
    assert (second["cells"][0]["model_score"], second["cells"][0]["override_score"]) == (None, None)
    assert [f["interviewer_id"] for f in first["cells"][0]["feedback"]] == [str(env.interviewer_id)]
    assert second["cells"][0]["feedback"] == []
    assert first["cells"][0]["disagreement"] is False
    assert "SECRET QUOTE" not in response.text


async def test_compare_never_selects_the_quote_column_for_an_interviewer(env: Env) -> None:
    a, b = await candidate(env, assign=True), await candidate(env, assign=True)
    await score(env, a, env.must, 3)
    captured: list[str] = []

    def capture(conn: object, cursor: object, statement: str, *rest: object) -> None:
        captured.append(statement)

    event.listen(env.app.state.engine.sync_engine, "before_cursor_execute", capture)
    try:
        response = await compare(env.interviewer, a, b)
    finally:
        event.remove(env.app.state.engine.sync_engine, "before_cursor_execute", capture)

    scores_sql = [s for s in captured if "FROM scores" in s]
    assert response.status_code == 200
    assert scores_sql
    assert not any(
        column in s for s in captured for column in ("quote", "override_note", "flag_reason")
    )


async def test_an_unknown_id_is_404_and_a_second_role_is_422(env: Env) -> None:
    other_role = await _make_role(env)
    a, b = await candidate(env), await candidate(env, role_id=other_role)

    unknown = await compare(env.recruiter, a, uuid4())
    mixed = await compare(env.recruiter, a, b)

    assert unknown.status_code == 404
    assert (mixed.status_code, mixed.json()["error"]["code"]) == (422, "validation_error")


async def _make_role(env: Env) -> UUID:
    async with env.engine.begin() as conn:
        row = await conn.execute(
            text(
                "INSERT INTO roles(title, job_description) VALUES ('it64 other', 'x') RETURNING id"
            )
        )
        role_id: UUID = row.scalar_one()
    return role_id
