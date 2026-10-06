"""Propose, get, cancel and the queue view against fake repositories (HK-57)."""

import uuid
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.config import Settings
from app.db.repositories.jobs_api import QueueRow
from tests.api.fakes import FakeJobs, FakeRoles, FakeSessions, FakeUsers

CAP_MESSAGE = "The model budget of $8.00 has been reached. No new model calls can be made."


@pytest.fixture
async def recruiter(users: FakeUsers, sessions: FakeSessions) -> dict[str, str]:
    return (
        await sessions.sign_in(users.add(email="r@example.com", role="recruiter"))
    ).unsafe_headers


async def test_propose_enqueues_one_job_and_returns_its_id(
    client: AsyncClient, recruiter: dict[str, str], roles: FakeRoles, jobs: FakeJobs
) -> None:
    role = roles.seed()

    response = await client.post(f"/v1/roles/{role.id}/criteria:propose", headers=recruiter)

    assert response.status_code == 202
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"job_id": 1}
    assert [(j.type, j.role_id) for j in jobs.rows.values()] == [("propose_criteria", role.id)]


async def test_propose_for_an_unknown_role_is_404(
    client: AsyncClient, recruiter: dict[str, str], roles: FakeRoles, jobs: FakeJobs
) -> None:
    response = await client.post(f"/v1/roles/{uuid.uuid4()}/criteria:propose", headers=recruiter)

    assert (response.status_code, response.json()["error"]["code"]) == (404, "not_found")


async def test_a_second_proposal_while_one_is_open_is_409(
    client: AsyncClient, recruiter: dict[str, str], roles: FakeRoles, jobs: FakeJobs
) -> None:
    role = roles.seed()
    jobs.seed(role.id, status="running")

    response = await client.post(f"/v1/roles/{role.id}/criteria:propose", headers=recruiter)

    assert (response.status_code, response.json()["error"]["code"]) == (409, "job_already_open")


async def test_propose_on_an_approved_role_is_409_role_not_draft(
    client: AsyncClient, recruiter: dict[str, str], roles: FakeRoles, jobs: FakeJobs
) -> None:
    role = roles.seed(status="approved")

    response = await client.post(f"/v1/roles/{role.id}/criteria:propose", headers=recruiter)

    assert (response.status_code, response.json()["error"]["code"]) == (409, "role_not_draft")
    assert jobs.rows == {}


async def test_live_mode_at_the_cap_is_409_budget_reached(
    app: FastAPI,
    settings: Settings,
    client: AsyncClient,
    recruiter: dict[str, str],
    roles: FakeRoles,
    jobs: FakeJobs,
) -> None:
    app.state.settings = settings.model_copy(update={"model_mode": "live"})
    role = roles.seed()
    jobs.spent_usd = Decimal(8)

    response = await client.post(f"/v1/roles/{role.id}/criteria:propose", headers=recruiter)

    error = response.json()["error"]
    assert (response.status_code, error["code"], error["message"]) == (
        409,
        "budget_reached",
        CAP_MESSAGE,
    )
    assert jobs.rows == {}


async def test_replay_mode_ignores_recorded_spend(
    client: AsyncClient, recruiter: dict[str, str], roles: FakeRoles, jobs: FakeJobs
) -> None:
    role = roles.seed()
    jobs.spent_usd = Decimal(8)

    response = await client.post(f"/v1/roles/{role.id}/criteria:propose", headers=recruiter)

    assert response.status_code == 202


async def test_get_job_and_unknown_job(
    client: AsyncClient, recruiter: dict[str, str], roles: FakeRoles, jobs: FakeJobs
) -> None:
    job = jobs.seed(roles.seed().id, status="running")

    found = await client.get(f"/v1/jobs/{job.id}", headers=recruiter)
    missing = await client.get("/v1/jobs/999", headers=recruiter)

    assert found.status_code == 200
    assert found.json()["status"] == "running"
    assert found.json()["candidate_no"] is None
    assert missing.status_code == 404


async def test_cancel_a_queued_job_returns_it_cancelled(
    client: AsyncClient, recruiter: dict[str, str], roles: FakeRoles, jobs: FakeJobs
) -> None:
    job = jobs.seed(roles.seed().id)

    response = await client.post(f"/v1/jobs/{job.id}:cancel", headers=recruiter)

    assert (response.status_code, response.json()["status"]) == (200, "cancelled")
    assert jobs.rows[job.id].status == "cancelled"


async def test_cancel_a_finished_job_is_409(
    client: AsyncClient, recruiter: dict[str, str], roles: FakeRoles, jobs: FakeJobs
) -> None:
    job = jobs.seed(roles.seed().id, status="succeeded")

    response = await client.post(f"/v1/jobs/{job.id}:cancel", headers=recruiter)

    assert (response.status_code, response.json()["error"]["code"]) == (409, "job_not_cancellable")


async def test_cancel_an_unknown_job_is_404(
    client: AsyncClient, recruiter: dict[str, str], jobs: FakeJobs
) -> None:
    response = await client.post("/v1/jobs/999:cancel", headers=recruiter)

    assert response.status_code == 404


async def test_cancelling_a_process_resume_job_fails_its_candidate(
    client: AsyncClient, recruiter: dict[str, str], roles: FakeRoles, jobs: FakeJobs
) -> None:
    candidate = uuid.uuid4()
    job = jobs.seed(roles.seed().id, kind="process_resume", candidate_id=candidate)

    await client.post(f"/v1/jobs/{job.id}:cancel", headers=recruiter)

    assert jobs.candidate_failures == {candidate: "Cancelled by a recruiter"}


async def test_cancelling_a_rescore_job_leaves_the_candidate_alone(
    client: AsyncClient, recruiter: dict[str, str], roles: FakeRoles, jobs: FakeJobs
) -> None:
    job = jobs.seed(roles.seed().id, kind="rescore", candidate_id=uuid.uuid4())

    await client.post(f"/v1/jobs/{job.id}:cancel", headers=recruiter)

    assert jobs.candidate_failures == {}


def queue_row(number: int) -> QueueRow:
    return QueueRow(
        candidate_id=uuid.uuid4(),
        candidate_no=number,
        processing_status="queued",
        failure_reason=None,
        job=None,
    )


async def test_queue_lists_candidate_status_and_job_and_never_a_file_name(
    client: AsyncClient, recruiter: dict[str, str], roles: FakeRoles, jobs: FakeJobs
) -> None:
    role = roles.seed()
    running = jobs.seed(role.id, kind="process_resume", status="running")
    jobs.queue_rows = [
        QueueRow(uuid.uuid4(), 2, "scoring", None, running),
        queue_row(1),
    ]
    jobs.counts = (1, 1)

    response = await client.get(f"/v1/roles/{role.id}/queue", headers=recruiter)

    body = response.json()
    assert response.status_code == 200
    assert (body["waiting"], body["running"]) == (1, 1)
    assert [i["candidate_no"] for i in body["data"]] == [2, 1]
    assert body["data"][0]["job"]["status"] == "running"
    assert body["data"][1]["job"] is None
    assert "file_name" not in response.text


async def test_queue_of_an_unknown_role_is_404(
    client: AsyncClient, recruiter: dict[str, str], roles: FakeRoles, jobs: FakeJobs
) -> None:
    response = await client.get(f"/v1/roles/{uuid.uuid4()}/queue", headers=recruiter)

    assert response.status_code == 404


@pytest.mark.parametrize(("limit", "status"), [(0, 422), (1, 200), (200, 200), (201, 422)])
async def test_queue_limit_bounds(
    client: AsyncClient,
    recruiter: dict[str, str],
    roles: FakeRoles,
    jobs: FakeJobs,
    limit: int,
    status: int,
) -> None:
    role = roles.seed()

    response = await client.get(f"/v1/roles/{role.id}/queue?limit={limit}", headers=recruiter)

    assert response.status_code == status
