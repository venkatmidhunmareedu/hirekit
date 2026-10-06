"""Retry, rescore and the cost log end to end against Postgres (HK-65)."""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal
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
    client: AsyncClient
    tag: str


@pytest.fixture
async def env(engine: AsyncEngine) -> AsyncIterator[Env]:
    tag = f"it65-{uuid4().hex[:12]}"
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory.begin() as setup:
        await setup.execute(
            text(
                "INSERT INTO users(name, email, role, password_hash) "
                "VALUES (:n, :e, 'recruiter', :h)"
            ),
            {"n": tag, "e": f"r-{tag}@example.com", "h": hash_password(PASSWORD)},
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
            yield Env(engine, client, tag)
    finally:
        async with factory.begin() as cleanup:
            like = {"t": f"{tag}%"}
            # candidates cascade to jobs and scores; criteria cascade from the role
            await cleanup.execute(
                text(
                    "DELETE FROM candidates WHERE role_id IN "
                    "(SELECT id FROM roles WHERE title LIKE :t)"
                ),
                like,
            )
            await cleanup.execute(text("DELETE FROM roles WHERE title LIKE :t"), like)
            await cleanup.execute(text("DELETE FROM call_log WHERE model = :m"), {"m": tag})
            await cleanup.execute(text("DELETE FROM users WHERE name = :n"), {"n": tag})


async def make_role(env: Env, *, version: int = 2) -> tuple[UUID, UUID]:
    """An approved role at `version` with one criterion: (role_id, criterion_id)."""
    async with env.engine.begin() as conn:
        role = await conn.execute(
            text(
                "INSERT INTO roles(title, job_description, status, criteria_version) "
                "VALUES (:t, 'Build.', 'approved', :v) RETURNING id"
            ),
            {"t": f"{env.tag} {uuid4().hex[:6]}", "v": version},
        )
        role_id = UUID(str(role.scalar_one()))
        criterion = await conn.execute(
            text(
                "INSERT INTO criteria(role_id, name, kind, weight, position) "
                "VALUES (:r, 'Python', 'must_have', 3, 0) RETURNING id"
            ),
            {"r": role_id},
        )
        return role_id, UUID(str(criterion.scalar_one()))


async def make_candidate(
    env: Env,
    role_id: UUID,
    criterion_id: UUID,
    *,
    status: str = "done",
    score: str | None = None,
    score_version: int = 2,
    job: str | None = None,
) -> UUID:
    """A candidate with an optional score row ('scored' or 'failed') and an optional open job."""
    reason = "Could not read the file." if status == "failed" else None
    async with env.engine.begin() as conn:
        row = await conn.execute(
            text(
                "INSERT INTO candidates(role_id, file_name, content_hash, processing_status, "
                "failure_reason) VALUES (:r, 'cv.pdf', :h, :s, :f) RETURNING id"
            ),
            {"r": role_id, "h": uuid4().hex + uuid4().hex, "s": status, "f": reason},
        )
        candidate_id = UUID(str(row.scalar_one()))
        if score == "scored":
            await conn.execute(
                text(
                    "INSERT INTO scores(candidate_id, criterion_id, criteria_version, status, "
                    "model_score, quote) VALUES (:c, :k, :v, 'scored', 3, 'a quote')"
                ),
                {"c": candidate_id, "k": criterion_id, "v": score_version},
            )
        elif score == "failed":
            await conn.execute(
                text(
                    "INSERT INTO scores(candidate_id, criterion_id, criteria_version, status) "
                    "VALUES (:c, :k, :v, 'failed')"
                ),
                {"c": candidate_id, "k": criterion_id, "v": score_version},
            )
        if job:
            await conn.execute(
                text(
                    "INSERT INTO jobs(type, role_id, candidate_id, criteria_version) "
                    "VALUES (:t, :r, :c, 2)"
                ),
                {"t": job, "r": role_id, "c": candidate_id},
            )
    return candidate_id


async def jobs_of(env: Env, candidate_id: UUID) -> list[tuple[str, str, int]]:
    async with env.engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT type, status, criteria_version FROM jobs "
                "WHERE candidate_id = :c ORDER BY id"
            ),
            {"c": candidate_id},
        )
        return [tuple(r) for r in result]


async def candidate_row(env: Env, candidate_id: UUID) -> tuple[str, str | None]:
    async with env.engine.connect() as conn:
        row = await conn.execute(
            text("SELECT processing_status, failure_reason FROM candidates WHERE id = :c"),
            {"c": candidate_id},
        )
        status, reason = row.one()
        return str(status), reason


async def test_retry_of_a_failed_file_creates_a_job_at_the_current_version_and_requeues_it(
    env: Env,
) -> None:
    role_id, criterion_id = await make_role(env, version=2)
    candidate_id = await make_candidate(env, role_id, criterion_id, status="failed")

    response = await env.client.post(f"/v1/candidates/{candidate_id}:retry")

    assert response.status_code == 202, response.text
    assert await jobs_of(env, candidate_id) == [("process_resume", "queued", 2)]
    assert await candidate_row(env, candidate_id) == ("queued", None)


async def test_retry_is_offered_for_a_failed_score_row_at_the_current_version(env: Env) -> None:
    role_id, criterion_id = await make_role(env, version=2)
    candidate_id = await make_candidate(env, role_id, criterion_id, score="failed")

    response = await env.client.post(f"/v1/candidates/{candidate_id}:retry")

    assert response.status_code == 202, response.text


async def test_retry_reaches_a_stale_candidate_with_no_score_rows_at_the_current_version(
    env: Env,
) -> None:
    role_id, criterion_id = await make_role(env, version=3)
    candidate_id = await make_candidate(env, role_id, criterion_id, score="scored", score_version=2)

    response = await env.client.post(f"/v1/candidates/{candidate_id}:retry")

    assert response.status_code == 202, response.text
    assert await jobs_of(env, candidate_id) == [("process_resume", "queued", 3)]


async def test_retry_of_a_fully_scored_candidate_is_409_not_retryable(env: Env) -> None:
    role_id, criterion_id = await make_role(env, version=2)
    candidate_id = await make_candidate(env, role_id, criterion_id, score="scored")

    response = await env.client.post(f"/v1/candidates/{candidate_id}:retry")

    assert (response.status_code, response.json()["error"]["code"]) == (409, "not_retryable")
    assert await jobs_of(env, candidate_id) == []


@pytest.mark.parametrize("open_type", ["process_resume", "rescore"])
async def test_retry_with_any_scoring_job_open_is_409_and_adds_no_job(
    env: Env, open_type: str
) -> None:
    role_id, criterion_id = await make_role(env)
    candidate_id = await make_candidate(env, role_id, criterion_id, status="failed", job=open_type)

    response = await env.client.post(f"/v1/candidates/{candidate_id}:retry")

    assert (response.status_code, response.json()["error"]["code"]) == (409, "job_already_open")
    assert await jobs_of(env, candidate_id) == [(open_type, "queued", 2)]
    assert await candidate_row(env, candidate_id) == ("failed", "Could not read the file.")


async def test_rescore_skips_a_candidate_with_an_open_job_and_leaves_scored_ones_alone(
    env: Env,
) -> None:
    role_id, criterion_id = await make_role(env, version=2)
    needs = await make_candidate(env, role_id, criterion_id, score="failed")
    busy = await make_candidate(env, role_id, criterion_id, status="queued", job="process_resume")
    done = await make_candidate(env, role_id, criterion_id, score="scored")

    response = await env.client.post(f"/v1/roles/{role_id}:rescore")

    assert response.status_code == 202, response.text
    body = response.json()
    assert len(body["job_ids"]) == 1
    assert len(body["skipped_candidate_nos"]) == 1
    assert await jobs_of(env, needs) == [("rescore", "queued", 2)]
    assert await jobs_of(env, busy) == [("process_resume", "queued", 2)]
    assert await jobs_of(env, done) == []


async def test_rescore_twice_does_not_stack_jobs(env: Env) -> None:
    role_id, criterion_id = await make_role(env)
    candidate_id = await make_candidate(env, role_id, criterion_id, status="failed")

    first = await env.client.post(f"/v1/roles/{role_id}:rescore")
    second = await env.client.post(f"/v1/roles/{role_id}:rescore")

    assert len(first.json()["job_ids"]) == 1
    assert second.json()["job_ids"] == []
    assert len(second.json()["skipped_candidate_nos"]) == 1
    assert await jobs_of(env, candidate_id) == [("rescore", "queued", 2)]


async def test_cost_log_shows_budget_and_calls_to_a_recruiter(env: Env) -> None:
    async with env.engine.begin() as conn:
        for n in range(3):
            await conn.execute(
                text(
                    "INSERT INTO call_log(purpose, status, model, request_key, input_tokens, "
                    "output_tokens, cost_usd) VALUES ('eval', 'settled', :m, :k, 10, 5, 0.001)"
                ),
                {"m": env.tag, "k": f"{n:064x}"},
            )
        spent = (await conn.execute(text("SELECT spent_usd FROM budget WHERE id = 1"))).scalar()

    response = await env.client.get("/v1/cost-log?limit=100")

    body = response.json()
    assert response.status_code == 200
    assert Decimal(body["budget"]["spent_usd"]) == (spent or 0)
    assert body["budget"]["limit_usd"] == "8"
    mine = [c for c in body["data"] if c["model"] == env.tag]
    assert [c["cost_usd"] for c in mine] == ["0.001000"] * 3
    assert [c["id"] for c in mine] == sorted((c["id"] for c in mine), reverse=True)


async def test_cost_log_pages_with_the_cursor(env: Env) -> None:
    async with env.engine.begin() as conn:
        for n in range(3):
            await conn.execute(
                text(
                    "INSERT INTO call_log(purpose, status, model, request_key) "
                    "VALUES ('eval', 'replayed', :m, :k)"
                ),
                {"m": env.tag, "k": f"{n:064x}"},
            )

    ids: list[int] = []
    mine: list[int] = []
    cursor = ""
    has_more = True
    while has_more:
        page = (await env.client.get(f"/v1/cost-log?limit=2&cursor={cursor}")).json()
        ids += [c["id"] for c in page["data"]]
        mine += [c["id"] for c in page["data"] if c["model"] == env.tag]
        has_more, cursor = page["page"]["has_more"], page["page"]["next_cursor"] or ""

    assert len(mine) == 3
    assert ids == sorted(set(ids), reverse=True)  # no repeats, newest first
