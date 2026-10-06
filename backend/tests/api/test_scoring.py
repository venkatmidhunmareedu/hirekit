"""POST /v1/candidates/{id}:retry and POST /v1/roles/{id}:rescore against fakes (HK-65)."""

import uuid
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response

from app.db.models import Role
from tests.api.fakes import FakeRoles, FakeScoringJobs, FakeSessions, FakeUsers


@pytest.fixture
async def recruiter(users: FakeUsers, sessions: FakeSessions) -> dict[str, str]:
    return (
        await sessions.sign_in(users.add(email="r@example.com", role="recruiter"))
    ).unsafe_headers


@pytest.fixture
async def interviewer(users: FakeUsers, sessions: FakeSessions) -> dict[str, str]:
    return (
        await sessions.sign_in(users.add(email="i@example.com", role="interviewer"))
    ).unsafe_headers


@pytest.fixture
def role(roles: FakeRoles) -> Role:
    return roles.seed(status="approved", version=3)


def error_of(response: Response) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def live_at_the_cap(app: FastAPI, jobs: FakeScoringJobs) -> None:
    app.state.settings = app.state.settings.model_copy(update={"model_mode": "live"})
    jobs.spent = Decimal("7.99")


async def retry(client: AsyncClient, candidate_id: uuid.UUID, headers: dict[str, str]) -> Response:
    return await client.post(f"/v1/candidates/{candidate_id}:retry", headers=headers)


async def rescore(client: AsyncClient, role_id: uuid.UUID, headers: dict[str, str]) -> Response:
    return await client.post(f"/v1/roles/{role_id}:rescore", headers=headers)


async def test_retry_enqueues_a_process_resume_job_at_the_current_version(
    client: AsyncClient, scoring_jobs: FakeScoringJobs, role: Role, recruiter: dict[str, str]
) -> None:
    candidate_id, _ = scoring_jobs.add(role.id)

    response = await retry(client, candidate_id, recruiter)

    assert (response.status_code, response.json()) == (202, {"job_id": 101})
    assert response.headers["cache-control"] == "no-store"
    assert scoring_jobs.enqueued == [("process_resume", role.id, candidate_id, 3)]
    assert scoring_jobs.reset == [candidate_id]


async def test_retry_of_a_candidate_that_does_not_need_scoring_is_409(
    client: AsyncClient, scoring_jobs: FakeScoringJobs, role: Role, recruiter: dict[str, str]
) -> None:
    candidate_id, _ = scoring_jobs.add(role.id, needs=False)

    response = await retry(client, candidate_id, recruiter)

    assert error_of(response) == (409, "not_retryable")
    assert scoring_jobs.enqueued == []


async def test_retry_with_a_scoring_job_already_open_is_409(
    client: AsyncClient, scoring_jobs: FakeScoringJobs, role: Role, recruiter: dict[str, str]
) -> None:
    candidate_id, _ = scoring_jobs.add(role.id, open_job=True)

    response = await retry(client, candidate_id, recruiter)

    assert error_of(response) == (409, "job_already_open")
    assert scoring_jobs.enqueued == []
    assert scoring_jobs.reset == []


async def test_retry_of_an_unknown_candidate_is_404(
    client: AsyncClient, scoring_jobs: FakeScoringJobs, recruiter: dict[str, str]
) -> None:
    assert error_of(await retry(client, uuid.uuid4(), recruiter)) == (404, "not_found")


async def test_retry_at_the_budget_cap_in_live_mode_is_409_and_in_replay_is_not(
    client: AsyncClient,
    app: FastAPI,
    scoring_jobs: FakeScoringJobs,
    role: Role,
    recruiter: dict[str, str],
) -> None:
    candidate_id, _ = scoring_jobs.add(role.id)
    scoring_jobs.spent = Decimal(8)
    assert (await retry(client, candidate_id, recruiter)).status_code == 202  # replay
    other, _ = scoring_jobs.add(role.id)
    live_at_the_cap(app, scoring_jobs)

    response = await retry(client, other, recruiter)

    assert error_of(response) == (409, "budget_reached")
    assert "$8.00" in response.json()["error"]["message"]
    assert len(scoring_jobs.enqueued) == 1


async def test_rescore_enqueues_one_job_per_candidate_that_needs_scoring(
    client: AsyncClient, scoring_jobs: FakeScoringJobs, role: Role, recruiter: dict[str, str]
) -> None:
    first, _ = scoring_jobs.add(role.id)
    scoring_jobs.add(role.id, needs=False)
    second, _ = scoring_jobs.add(role.id)
    scoring_jobs.add(uuid.uuid4())  # another role's candidate is left alone

    response = await rescore(client, role.id, recruiter)

    assert response.status_code == 202
    assert response.json() == {"job_ids": [101, 102], "skipped_candidate_nos": []}
    assert scoring_jobs.enqueued == [
        ("rescore", role.id, first, 3),
        ("rescore", role.id, second, 3),
    ]


async def test_rescore_skips_a_candidate_with_an_open_job_instead_of_failing_the_batch(
    client: AsyncClient, scoring_jobs: FakeScoringJobs, role: Role, recruiter: dict[str, str]
) -> None:
    scoring_jobs.add(role.id, open_job=True)
    scoring_jobs.add(role.id)

    response = await rescore(client, role.id, recruiter)

    assert response.status_code == 202
    assert response.json() == {"job_ids": [101], "skipped_candidate_nos": [1]}


async def test_rescore_with_nothing_to_do_is_an_empty_202(
    client: AsyncClient, scoring_jobs: FakeScoringJobs, role: Role, recruiter: dict[str, str]
) -> None:
    scoring_jobs.add(role.id, needs=False)

    response = await rescore(client, role.id, recruiter)

    assert (response.status_code, response.json()) == (
        202,
        {"job_ids": [], "skipped_candidate_nos": []},
    )


async def test_rescore_of_a_draft_role_is_409(
    client: AsyncClient,
    scoring_jobs: FakeScoringJobs,
    roles: FakeRoles,
    recruiter: dict[str, str],
) -> None:
    draft = roles.seed(status="draft")
    scoring_jobs.add(draft.id)

    response = await rescore(client, draft.id, recruiter)

    assert error_of(response) == (409, "role_not_approved")
    assert scoring_jobs.enqueued == []


async def test_rescore_at_the_budget_cap_in_live_mode_is_409(
    client: AsyncClient,
    app: FastAPI,
    scoring_jobs: FakeScoringJobs,
    role: Role,
    recruiter: dict[str, str],
) -> None:
    scoring_jobs.add(role.id)
    live_at_the_cap(app, scoring_jobs)

    response = await rescore(client, role.id, recruiter)

    assert error_of(response) == (409, "budget_reached")
    assert scoring_jobs.enqueued == []


async def test_rescore_of_an_unknown_role_is_404(
    client: AsyncClient, scoring_jobs: FakeScoringJobs, recruiter: dict[str, str]
) -> None:
    assert error_of(await rescore(client, uuid.uuid4(), recruiter)) == (404, "not_found")


async def test_an_interviewer_can_do_neither(
    client: AsyncClient, scoring_jobs: FakeScoringJobs, role: Role, interviewer: dict[str, str]
) -> None:
    candidate_id, _ = scoring_jobs.add(role.id)

    assert error_of(await retry(client, candidate_id, interviewer)) == (403, "forbidden")
    assert error_of(await rescore(client, role.id, interviewer)) == (403, "forbidden")
    assert scoring_jobs.enqueued == []
