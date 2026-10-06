"""The role routes against fake repositories (HK-53)."""

import uuid

import pytest
from httpx import AsyncClient, Response

from tests.api.fakes import FakeCriteria, FakeRoles, FakeSessions, FakeUsers


@pytest.fixture
async def recruiter(users: FakeUsers, sessions: FakeSessions) -> dict[str, str]:
    return (
        await sessions.sign_in(users.add(email="r@example.com", role="recruiter"))
    ).unsafe_headers


def level(n: int, text: str | None = None) -> dict[str, object]:
    return {"level": n, "descriptor": text or f"level {n}"}


def crit(name: str = "Python", over: dict[str, object] | None = None) -> dict[str, object]:
    base: dict[str, object] = {
        "name": name,
        "kind": "must_have",
        "weight": 3,
        "rubric": [level(n) for n in range(5)],
    }
    return {**base, **(over or {})}


async def put(
    client: AsyncClient, headers: dict[str, str], role_id: uuid.UUID, items: list[dict[str, object]]
) -> Response:
    return await client.put(
        f"/v1/roles/{role_id}/criteria", json={"criteria": items}, headers=headers
    )


async def test_create_role_is_draft_version_1_and_recruiter_only(
    client: AsyncClient,
    roles: FakeRoles,
    recruiter: dict[str, str],
    users: FakeUsers,
    sessions: FakeSessions,
) -> None:
    body = {"title": "  Backend engineer ", "job_description": "Build."}

    created = await client.post("/v1/roles", json=body, headers=recruiter)
    interviewer = await sessions.sign_in(users.add(email="i@example.com", role="interviewer"))
    refused = await client.post("/v1/roles", json=body, headers=interviewer.unsafe_headers)

    assert created.status_code == 201
    assert created.json() | {"id": "x", "created_at": "x", "updated_at": "x"} == {
        "id": "x",
        "title": "Backend engineer",
        "job_description": "Build.",
        "status": "draft",
        "criteria_version": 1,
        "created_at": "x",
        "updated_at": "x",
    }
    assert refused.status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        {"title": "   ", "job_description": "x"},
        {"title": "x", "job_description": " "},
        {"title": "x" * 201, "job_description": "x"},
        {"title": "x", "job_description": "x" * 20001},
        {"title": "x", "job_description": "x", "status": "approved"},
    ],
)
async def test_create_role_rejects_blank_title_and_extra_fields(
    client: AsyncClient, roles: FakeRoles, recruiter: dict[str, str], body: dict[str, object]
) -> None:
    response = await client.post("/v1/roles", json=body, headers=recruiter)

    assert response.status_code == 422
    assert roles.rows == {}


@pytest.mark.parametrize("count", [0, 9])
async def test_criteria_count_outside_one_to_eight_is_refused(
    client: AsyncClient, roles: FakeRoles, recruiter: dict[str, str], count: int
) -> None:
    role = roles.seed()

    response = await put(client, recruiter, role.id, [crit(f"c{i}") for i in range(count)])

    assert response.status_code == 422


@pytest.mark.parametrize("count", [1, 8])
async def test_criteria_count_one_and_eight_are_accepted(
    client: AsyncClient,
    roles: FakeRoles,
    criteria: FakeCriteria,
    recruiter: dict[str, str],
    count: int,
) -> None:
    role = roles.seed()

    response = await put(client, recruiter, role.id, [crit(f"c{i}") for i in range(count)])

    assert response.status_code == 200
    assert len(response.json()["criteria"]) == count


@pytest.mark.parametrize(
    ("field", "value", "ok"),
    [
        ("weight", 0, False),
        ("weight", 6, False),
        ("weight", 1, True),
        ("weight", 5, True),
        ("weight", 2.5, False),
        ("kind", "maybe", False),
        ("name", "n" * 80, True),
        ("name", "n" * 81, False),
        ("name", "  ", False),
        ("name", "two\nlines", False),
        ("rubric", [level(5)], False),
        ("rubric", [level(-1)], False),
        ("rubric", [level(1), level(1)], False),
        ("rubric", [level(n) for n in range(6)], False),
        ("rubric", [level(1, "d" * 200)], True),
        ("rubric", [level(1, "d" * 201)], False),
        ("rubric", [level(1, "two\nlines")], False),
        ("rubric", [level(1, "  ")], False),
        ("rubric", [], True),
    ],
)
async def test_criterion_field_bounds(
    client: AsyncClient,
    roles: FakeRoles,
    criteria: FakeCriteria,
    recruiter: dict[str, str],
    field: str,
    value: object,
    ok: bool,
) -> None:
    role = roles.seed()

    response = await put(client, recruiter, role.id, [crit(over={field: value})])

    assert (response.status_code == 200) is ok


async def test_duplicate_names_ignoring_case_and_spacing_are_refused(
    client: AsyncClient, roles: FakeRoles, recruiter: dict[str, str]
) -> None:
    role = roles.seed()

    response = await put(client, recruiter, role.id, [crit("Team  Lead"), crit("team lead")])

    assert response.status_code == 422


async def test_replace_on_a_draft_role_still_bumps_the_version(
    client: AsyncClient, roles: FakeRoles, criteria: FakeCriteria, recruiter: dict[str, str]
) -> None:
    role = roles.seed(status="draft", version=4)

    response = await put(client, recruiter, role.id, [crit()])

    assert (response.json()["status"], response.json()["criteria_version"]) == ("draft", 5)


async def test_replace_with_foreign_criterion_id_is_422(
    client: AsyncClient, roles: FakeRoles, criteria: FakeCriteria, recruiter: dict[str, str]
) -> None:
    role, other = roles.seed(), roles.seed()
    foreign = criteria.seed(other.id, "Theirs")

    response = await put(client, recruiter, role.id, [crit(over={"id": str(foreign.id)})])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert criteria.rows[foreign.id].retired_at is None


async def test_replace_unknown_role_is_404(
    client: AsyncClient, roles: FakeRoles, criteria: FakeCriteria, recruiter: dict[str, str]
) -> None:
    response = await put(client, recruiter, uuid.uuid4(), [crit()])

    assert response.status_code == 404


async def approve(
    client: AsyncClient, headers: dict[str, str], role_id: uuid.UUID, version: int
) -> Response:
    return await client.post(
        f"/v1/roles/{role_id}/approve", json={"criteria_version": version}, headers=headers
    )


async def test_approve_sets_approved_with_matching_version(
    client: AsyncClient, roles: FakeRoles, criteria: FakeCriteria, recruiter: dict[str, str]
) -> None:
    role = roles.seed(version=2)
    criteria.seed(role.id, "Python")

    response = await approve(client, recruiter, role.id, 2)

    assert (response.status_code, response.json()["status"]) == (200, "approved")
    assert response.json()["criteria_version"] == 2


async def test_approve_twice_is_idempotent(
    client: AsyncClient, roles: FakeRoles, criteria: FakeCriteria, recruiter: dict[str, str]
) -> None:
    role = roles.seed()
    criteria.seed(role.id, "Python")

    first = await approve(client, recruiter, role.id, 1)
    second = await approve(client, recruiter, role.id, 1)

    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json() == first.json()


async def test_approve_with_a_stale_version_is_409_criteria_changed(
    client: AsyncClient, roles: FakeRoles, criteria: FakeCriteria, recruiter: dict[str, str]
) -> None:
    role = roles.seed(version=3)
    criteria.seed(role.id, "Python")

    response = await approve(client, recruiter, role.id, 2)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "criteria_changed"
    assert response.json()["error"]["details"] == {"current_version": 3}
    assert role.status == "draft"


async def test_approve_of_a_role_with_no_criteria_is_422(
    client: AsyncClient, roles: FakeRoles, criteria: FakeCriteria, recruiter: dict[str, str]
) -> None:
    role = roles.seed()

    response = await approve(client, recruiter, role.id, 1)

    assert (response.status_code, response.json()["error"]["code"]) == (422, "no_criteria")


async def test_approve_needs_five_rubric_levels_per_criterion(
    client: AsyncClient, roles: FakeRoles, criteria: FakeCriteria, recruiter: dict[str, str]
) -> None:
    role = roles.seed()
    criteria.seed(role.id, "Complete")
    short = criteria.seed(role.id, "Short", levels=4, position=1)

    response = await approve(client, recruiter, role.id, 1)

    assert (response.status_code, response.json()["error"]["code"]) == (422, "incomplete_rubric")
    assert response.json()["error"]["details"] == {"criterion_ids": [str(short.id)]}
    assert role.status == "draft"


async def test_approve_unknown_role_is_404_and_bad_body_422(
    client: AsyncClient, roles: FakeRoles, recruiter: dict[str, str]
) -> None:
    missing = await approve(client, recruiter, uuid.uuid4(), 1)
    zero = await approve(client, recruiter, uuid.uuid4(), 0)

    assert (missing.status_code, zero.status_code) == (404, 422)


async def test_get_role_returns_live_criteria_in_order_with_numeric_weight(
    client: AsyncClient, roles: FakeRoles, criteria: FakeCriteria, recruiter: dict[str, str]
) -> None:
    role = roles.seed()
    criteria.seed(role.id, "Second", position=1)
    criteria.seed(role.id, "First", position=0)
    retired = criteria.seed(role.id, "Gone", position=2)
    await criteria.retire([retired.id])

    response = await client.get(f"/v1/roles/{role.id}", headers=recruiter)

    body = response.json()
    assert [c["name"] for c in body["criteria"]] == ["First", "Second"]
    assert body["criteria"][0]["weight"] == 3.0
    assert [r["level"] for r in body["criteria"][0]["rubric"]] == [0, 1, 2, 3, 4]


async def test_list_roles_returns_data_envelope(
    client: AsyncClient, roles: FakeRoles, recruiter: dict[str, str]
) -> None:
    roles.seed()

    response = await client.get("/v1/roles", headers=recruiter)

    assert len(response.json()["data"]) == 1


async def test_interviewer_reads_only_a_role_with_an_assigned_candidate(
    client: AsyncClient,
    roles: FakeRoles,
    criteria: FakeCriteria,
    users: FakeUsers,
    sessions: FakeSessions,
) -> None:
    user = users.add(email="i@example.com", role="interviewer")
    headers = (await sessions.sign_in(user)).unsafe_headers
    mine, other = roles.seed(), roles.seed()
    roles.assigned.add((mine.id, user.id))

    allowed = await client.get(f"/v1/roles/{mine.id}", headers=headers)
    hidden = await client.get(f"/v1/roles/{other.id}", headers=headers)
    absent = await client.get(f"/v1/roles/{uuid.uuid4()}", headers=headers)

    assert (allowed.status_code, hidden.status_code, absent.status_code) == (200, 404, 404)
