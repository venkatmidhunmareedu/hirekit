"""The kit routes against fake repositories (HK-62)."""

import uuid
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response

from app.db.models import Role
from tests.api.fakes import FakeKit, FakeRoles, FakeSessions, FakeUsers


@pytest.fixture
async def recruiter(users: FakeUsers, sessions: FakeSessions) -> dict[str, str]:
    return (
        await sessions.sign_in(users.add(email="r@example.com", role="recruiter"))
    ).unsafe_headers


@pytest.fixture
def role(roles: FakeRoles) -> Role:
    return roles.seed(status="approved", version=3)


def error_of(response: Response) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


async def test_generate_enqueues_one_job_at_the_roles_version(
    client: AsyncClient, kit: FakeKit, role: Role, recruiter: dict[str, str]
) -> None:
    response = await client.post(f"/v1/roles/{role.id}/kit:generate", headers=recruiter)

    assert (response.status_code, response.json()) == (202, {"job_id": 1})
    assert response.headers["cache-control"] == "no-store"
    assert kit.jobs == [("generate_kit", role.id, None, 3)]


async def test_generate_for_a_draft_role_is_409_role_not_approved(
    client: AsyncClient, kit: FakeKit, roles: FakeRoles, recruiter: dict[str, str]
) -> None:
    draft = roles.seed(status="draft")

    response = await client.post(f"/v1/roles/{draft.id}/kit:generate", headers=recruiter)

    assert error_of(response) == (409, "role_not_approved")
    assert kit.jobs == []


async def test_generate_for_an_unknown_role_is_404(
    client: AsyncClient, kit: FakeKit, recruiter: dict[str, str]
) -> None:
    response = await client.post(f"/v1/roles/{uuid.uuid4()}/kit:generate", headers=recruiter)

    assert error_of(response) == (404, "not_found")


async def test_a_second_generate_while_one_is_open_is_409_job_already_open(
    client: AsyncClient, kit: FakeKit, role: Role, recruiter: dict[str, str]
) -> None:
    url = f"/v1/roles/{role.id}/kit:generate"
    await client.post(url, headers=recruiter)

    response = await client.post(url, headers=recruiter)

    assert error_of(response) == (409, "job_already_open")
    assert len(kit.jobs) == 1


async def test_at_the_budget_cap_in_live_mode_generate_is_refused(
    app: FastAPI, client: AsyncClient, kit: FakeKit, role: Role, recruiter: dict[str, str]
) -> None:
    kit.spent = Decimal(8)
    app.state.settings = app.state.settings.model_copy(update={"model_mode": "live"})

    response = await client.post(f"/v1/roles/{role.id}/kit:generate", headers=recruiter)

    assert error_of(response) == (409, "budget_reached")
    assert kit.jobs == []


async def test_get_kit_derives_stale_from_the_roles_version(
    client: AsyncClient, kit: FakeKit, roles: FakeRoles, role: Role, recruiter: dict[str, str]
) -> None:
    question_id = kit.seed_question(role.id)

    fresh = (await client.get(f"/v1/roles/{role.id}/kit", headers=recruiter)).json()
    roles.rows[role.id].criteria_version = 4
    stale = (await client.get(f"/v1/roles/{role.id}/kit", headers=recruiter)).json()

    assert (fresh["stale"], stale["stale"], stale["criteria_version"]) == (False, True, 3)
    assert [q["id"] for q in fresh["questions"]] == [str(question_id)]


async def test_get_kit_without_a_kit_is_404(
    client: AsyncClient, kit: FakeKit, role: Role, recruiter: dict[str, str]
) -> None:
    response = await client.get(f"/v1/roles/{role.id}/kit", headers=recruiter)

    assert error_of(response) == (404, "not_found")


async def test_an_interviewer_reads_the_kit_only_with_an_assigned_candidate_in_the_role(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    kit: FakeKit,
    roles: FakeRoles,
    role: Role,
) -> None:
    kit.seed_question(role.id)
    user = users.add(email="i@example.com", role="interviewer")
    headers = (await sessions.sign_in(user)).unsafe_headers

    unassigned = await client.get(f"/v1/roles/{role.id}/kit", headers=headers)
    roles.assigned.add((role.id, user.id))
    assigned = await client.get(f"/v1/roles/{role.id}/kit", headers=headers)

    assert error_of(unassigned) == (404, "not_found")
    assert assigned.status_code == 200


async def test_update_changes_only_the_fields_sent(
    client: AsyncClient, kit: FakeKit, role: Role, recruiter: dict[str, str]
) -> None:
    question_id = kit.seed_question(role.id)

    response = await client.put(
        f"/v1/kit/questions/{question_id}",
        headers=recruiter,
        json={"question_text": "  New text ", "position": 2},
    )

    body = response.json()
    assert response.status_code == 200
    assert (body["question_text"], body["position"], body["strong_answer"]) == ("New text", 2, "S")


@pytest.mark.parametrize(
    "body",
    [{}, {"question_text": ""}, {"question_text": None}, {"position": -1}, {"other": "x"}],
)
async def test_update_rejects_an_empty_blank_null_or_unknown_field(
    client: AsyncClient,
    kit: FakeKit,
    role: Role,
    recruiter: dict[str, str],
    body: dict[str, object],
) -> None:
    question_id = kit.seed_question(role.id)

    response = await client.put(f"/v1/kit/questions/{question_id}", headers=recruiter, json=body)

    assert error_of(response) == (422, "validation_error")


async def test_update_and_delete_of_an_unknown_question_are_404(
    client: AsyncClient, kit: FakeKit, recruiter: dict[str, str]
) -> None:
    url = f"/v1/kit/questions/{uuid.uuid4()}"

    put = await client.put(url, headers=recruiter, json={"position": 1})
    delete = await client.delete(url, headers=recruiter)

    assert (error_of(put), error_of(delete)) == ((404, "not_found"), (404, "not_found"))


async def test_delete_removes_the_question_and_a_repeat_is_404(
    client: AsyncClient, kit: FakeKit, role: Role, recruiter: dict[str, str]
) -> None:
    question_id = kit.seed_question(role.id)
    url = f"/v1/kit/questions/{question_id}"

    first = await client.delete(url, headers=recruiter)
    second = await client.delete(url, headers=recruiter)

    assert (first.status_code, first.content, second.status_code) == (204, b"", 404)
    assert question_id not in kit.rows


async def test_regenerate_enqueues_a_job_for_the_question_then_refuses_a_second(
    client: AsyncClient, kit: FakeKit, role: Role, recruiter: dict[str, str]
) -> None:
    question_id = kit.seed_question(role.id)
    url = f"/v1/kit/questions/{question_id}:regenerate"

    first = await client.post(url, headers=recruiter)
    second = await client.post(url, headers=recruiter)

    assert (first.status_code, first.json()) == (202, {"job_id": 1})
    assert error_of(second) == (409, "job_already_open")
    assert kit.jobs == [("regenerate_question", role.id, question_id, 3)]


async def test_regenerate_for_a_draft_role_or_unknown_question(
    client: AsyncClient, kit: FakeKit, roles: FakeRoles, role: Role, recruiter: dict[str, str]
) -> None:
    question_id = kit.seed_question(role.id)
    roles.rows[role.id].status = "draft"

    draft = await client.post(f"/v1/kit/questions/{question_id}:regenerate", headers=recruiter)
    unknown = await client.post(f"/v1/kit/questions/{uuid.uuid4()}:regenerate", headers=recruiter)

    assert (error_of(draft), error_of(unknown)) == ((409, "role_not_approved"), (404, "not_found"))
    assert kit.jobs == []


async def test_a_write_without_the_csrf_header_is_403(
    client: AsyncClient, kit: FakeKit, role: Role, users: FakeUsers, sessions: FakeSessions
) -> None:
    user = users.add(email="r2@example.com", role="recruiter")
    cookie_only = (await sessions.sign_in(user)).cookie

    response = await client.post(f"/v1/roles/{role.id}/kit:generate", headers=cookie_only)

    assert error_of(response) == (403, "csrf_failed")
