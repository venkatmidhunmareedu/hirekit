"""The job routes end to end against Postgres: real sessions, real rows, real grants."""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.passwords import hash_password
from app.db.repositories import jobs
from app.db.repositories.jobs_api import JobsApiRepository
from app.main import create_app
from app.worker.errors import LeaseLostError
from tests.integration.test_jobs_repository import seed_job, seed_role
from tests.integration.test_roles_and_grants import become

pytestmark = pytest.mark.integration

PASSWORD = f"pw-{uuid4().hex}"
DELETE = {
    "jobs": "DELETE FROM jobs WHERE role_id IN (SELECT id FROM roles WHERE title LIKE :t)",
    "candidates": (
        "DELETE FROM candidates WHERE role_id IN (SELECT id FROM roles WHERE title LIKE :t)"
    ),
}


@dataclass
class Env:
    engine: AsyncEngine
    client: AsyncClient
    tag: str


@pytest.fixture
async def env(engine: AsyncEngine) -> AsyncIterator[Env]:
    tag = f"it57-{uuid4().hex[:12]}"
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
            for table in ("jobs", "candidates"):
                await cleanup.execute(
                    text(DELETE[table]),
                    like,
                )
            await cleanup.execute(text("DELETE FROM roles WHERE title LIKE :t"), like)
            await cleanup.execute(text("DELETE FROM users WHERE name = :n"), {"n": tag})


async def make_role(env: Env, suffix: str = "") -> UUID:
    response = await env.client.post(
        "/v1/roles", json={"title": f"{env.tag} {suffix}", "job_description": "Build."}
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


async def seed_candidate_job(
    env: Env, role_id: UUID, *, kind: str = "process_resume", status: str = "queued", n: int = 0
) -> tuple[int, UUID]:
    """A candidate with one job; a running job gets a lease by hand."""
    candidate_id = uuid4()
    async with env.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO candidates(id, role_id, file_name, content_hash) "
                "VALUES (:id, :role, :file, :hash)"
            ),
            {
                "id": candidate_id,
                "role": role_id,
                "file": f"Jane_Doe_{n}.pdf",
                "hash": candidate_id.hex * 2,
            },
        )
        job_id = await conn.scalar(
            text(
                "INSERT INTO jobs(type, role_id, candidate_id, criteria_version, status, "
                "lease_token, lease_expires_at) VALUES (:kind, :role, :cand, 1, :status, "
                "CASE WHEN :status = 'running' THEN gen_random_uuid() END, "
                "CASE WHEN :status = 'running' THEN now() + interval '3 minutes' END) "
                "RETURNING id"
            ),
            {"kind": kind, "role": role_id, "cand": candidate_id, "status": status},
        )
    assert job_id is not None
    return job_id, candidate_id


async def job_row(env: Env, job_id: int) -> tuple[str, UUID | None, object]:
    async with env.engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT status, lease_token, lease_expires_at FROM jobs WHERE id = :id"),
                {"id": job_id},
            )
        ).one()
    return row.status, row.lease_token, row.lease_expires_at


async def candidate_row(env: Env, candidate_id: UUID) -> tuple[str, str | None]:
    async with env.engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT processing_status::text, failure_reason FROM candidates WHERE id = :i"
                ),
                {"i": candidate_id},
            )
        ).one()
    return row[0], row[1]


async def test_propose_criteria_enqueues_one_job_and_returns_its_id(env: Env) -> None:
    role_id = await make_role(env)

    response = await env.client.post(f"/v1/roles/{role_id}/criteria:propose")

    assert response.status_code == 202, response.text
    job = (await env.client.get(f"/v1/jobs/{response.json()['job_id']}")).json()
    assert (job["type"], job["status"], job["role_id"], job["criteria_version"]) == (
        "propose_criteria",
        "queued",
        str(role_id),
        1,
    )
    assert job["candidate_no"] is None


async def test_second_proposal_while_one_is_open_is_409_job_already_open(env: Env) -> None:
    role_id = await make_role(env)
    first = await env.client.post(f"/v1/roles/{role_id}/criteria:propose")

    second = await env.client.post(f"/v1/roles/{role_id}/criteria:propose")

    assert (second.status_code, second.json()["error"]["code"]) == (409, "job_already_open")
    async with env.engine.connect() as conn:
        count = await conn.scalar(
            text("SELECT count(*) FROM jobs WHERE role_id = :r"), {"r": role_id}
        )
    assert (first.status_code, count) == (202, 1)


async def test_propose_again_after_the_first_finished(env: Env) -> None:
    role_id = await make_role(env)
    first = (await env.client.post(f"/v1/roles/{role_id}/criteria:propose")).json()["job_id"]
    async with env.engine.begin() as conn:
        await conn.execute(text("UPDATE jobs SET status = 'succeeded' WHERE id = :i"), {"i": first})

    again = await env.client.post(f"/v1/roles/{role_id}/criteria:propose")

    assert again.status_code == 202
    assert again.json()["job_id"] != first


async def test_propose_on_an_approved_role_is_409_role_not_draft(env: Env) -> None:
    role_id = await make_role(env)
    async with env.engine.begin() as conn:
        await conn.execute(
            text("UPDATE roles SET status = 'approved' WHERE id = :i"), {"i": role_id}
        )

    response = await env.client.post(f"/v1/roles/{role_id}/criteria:propose")

    assert (response.status_code, response.json()["error"]["code"]) == (409, "role_not_draft")


async def test_cancel_a_running_job_makes_the_workers_next_write_fail(env: Env) -> None:
    role_id = await make_role(env)
    job_id, _ = await seed_candidate_job(env, role_id, kind="rescore", status="running")
    _, old_token, _ = await job_row(env, job_id)
    assert old_token is not None

    response = await env.client.post(f"/v1/jobs/{job_id}:cancel")

    assert (response.status_code, response.json()["status"]) == (200, "cancelled")
    assert await job_row(env, job_id) == ("cancelled", None, None)
    async with AsyncSession(env.engine) as worker:
        with pytest.raises(LeaseLostError):
            await jobs.fence(worker, job_id, old_token)


async def test_cancelling_a_process_resume_job_fails_its_candidate_with_the_reason(
    env: Env,
) -> None:
    role_id = await make_role(env)
    job_id, candidate_id = await seed_candidate_job(env, role_id)

    response = await env.client.post(f"/v1/jobs/{job_id}:cancel")

    assert response.status_code == 200
    assert await candidate_row(env, candidate_id) == ("failed", "Cancelled by a recruiter")


async def test_cancelling_a_rescore_job_leaves_the_candidate_unchanged(env: Env) -> None:
    role_id = await make_role(env)
    job_id, candidate_id = await seed_candidate_job(env, role_id, kind="rescore")

    await env.client.post(f"/v1/jobs/{job_id}:cancel")

    assert await candidate_row(env, candidate_id) == ("queued", None)


async def test_cancel_a_finished_job_is_409_and_an_unknown_job_is_404(env: Env) -> None:
    role_id = await make_role(env)
    job_id, _ = await seed_candidate_job(env, role_id, status="succeeded")

    finished = await env.client.post(f"/v1/jobs/{job_id}:cancel")
    unknown = await env.client.post("/v1/jobs/999999999:cancel")

    assert (finished.status_code, finished.json()["error"]["code"]) == (409, "job_not_cancellable")
    assert unknown.status_code == 404


async def test_cancel_runs_with_only_the_hirekit_api_grants(session: AsyncSession) -> None:
    role = await seed_role(session)
    job_id, candidate_id = await seed_job(session, role, running_lease_in=timedelta(minutes=3))
    await become(session, "hirekit_api")

    cancelled = await JobsApiRepository(session).cancel(job_id)

    assert cancelled is True
    status = await session.scalar(
        text("SELECT processing_status::text FROM candidates WHERE id = :i"), {"i": candidate_id}
    )
    assert status == "failed"


async def test_queue_view_lists_each_file_status_and_the_running_job(env: Env) -> None:
    role_id = await make_role(env)
    _, waiting = await seed_candidate_job(env, role_id, n=1)
    running_job, running = await seed_candidate_job(env, role_id, status="running", n=2)
    async with env.engine.begin() as conn:
        await conn.execute(
            text("UPDATE candidates SET processing_status = 'scoring' WHERE id = :i"),
            {"i": running},
        )

    response = await env.client.get(f"/v1/roles/{role_id}/queue")

    body = response.json()
    assert response.status_code == 200
    assert (body["waiting"], body["running"]) == (1, 1)
    items = {i["candidate_id"]: i for i in body["data"]}
    assert items[str(running)]["processing_status"] == "scoring"
    assert items[str(running)]["job"]["id"] == running_job
    assert items[str(running)]["job"]["candidate_no"] == items[str(running)]["candidate_no"]
    assert items[str(waiting)]["job"]["status"] == "queued"
    assert "Jane_Doe" not in response.text
    assert "file_name" not in response.text


async def test_an_empty_role_has_an_empty_queue(env: Env) -> None:
    role_id = await make_role(env)

    response = await env.client.get(f"/v1/roles/{role_id}/queue")

    assert response.json() == {"data": [], "waiting": 0, "running": 0}
