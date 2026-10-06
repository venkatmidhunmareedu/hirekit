"""Assignment routes and GET /v1/me/candidates against a fake repository (HK-61)."""

import uuid

import pytest
from httpx import AsyncClient

from tests.api.fake_assignments import FakeAssignments
from tests.api.fakes import FakeSessions, FakeUsers


@pytest.fixture
async def recruiter(users: FakeUsers, sessions: FakeSessions) -> dict[str, str]:
    return (
        await sessions.sign_in(users.add(email="r@example.com", role="recruiter"))
    ).unsafe_headers


async def sign_in_interviewer(
    users: FakeUsers, sessions: FakeSessions, email: str
) -> tuple[uuid.UUID, dict[str, str]]:
    user = users.add(email=email, role="interviewer")
    return user.id, (await sessions.sign_in(user)).unsafe_headers


async def test_only_a_recruiter_can_assign_and_only_to_an_interviewer(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    assignments: FakeAssignments,
    recruiter: dict[str, str],
) -> None:
    candidate_id = assignments.seed_candidate()
    interviewer_id, interviewer_headers = await sign_in_interviewer(
        users, sessions, "i@example.com"
    )
    other_recruiter = users.add(email="r2@example.com", role="recruiter")
    url = f"/v1/candidates/{candidate_id}/assignments"

    by_interviewer = await client.post(
        url, json={"user_id": str(interviewer_id)}, headers=interviewer_headers
    )
    to_recruiter = await client.post(
        url, json={"user_id": str(other_recruiter.id)}, headers=recruiter
    )
    to_nobody = await client.post(url, json={"user_id": str(uuid.uuid4())}, headers=recruiter)
    ok = await client.post(url, json={"user_id": str(interviewer_id)}, headers=recruiter)

    assert by_interviewer.status_code == 403
    assert (to_recruiter.status_code, to_recruiter.json()["error"]["code"]) == (
        422,
        "validation_error",
    )
    assert to_nobody.status_code == 422
    assert ok.status_code == 201
    assert ok.json() == {"candidate_id": str(candidate_id), "user_id": str(interviewer_id)}
    assert ok.headers["cache-control"] == "no-store"
    assert assignments.pairs == {(candidate_id, interviewer_id)}


async def test_a_repeated_assignment_is_idempotent(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    assignments: FakeAssignments,
    recruiter: dict[str, str],
) -> None:
    candidate_id = assignments.seed_candidate()
    interviewer_id, _ = await sign_in_interviewer(users, sessions, "i@example.com")
    url = f"/v1/candidates/{candidate_id}/assignments"

    first = await client.post(url, json={"user_id": str(interviewer_id)}, headers=recruiter)
    again = await client.post(url, json={"user_id": str(interviewer_id)}, headers=recruiter)

    assert (first.status_code, again.status_code) == (201, 201)
    assert len(assignments.pairs) == 1


async def test_assigning_an_unknown_candidate_is_404_and_extra_fields_are_422(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    assignments: FakeAssignments,
    recruiter: dict[str, str],
) -> None:
    interviewer_id, _ = await sign_in_interviewer(users, sessions, "i@example.com")
    known = assignments.seed_candidate()

    unknown = await client.post(
        f"/v1/candidates/{uuid.uuid4()}/assignments",
        json={"user_id": str(interviewer_id)},
        headers=recruiter,
    )
    extra = await client.post(
        f"/v1/candidates/{known}/assignments",
        json={"user_id": str(interviewer_id), "role": "recruiter"},
        headers=recruiter,
    )

    assert (unknown.status_code, unknown.json()["error"]["code"]) == (404, "not_found")
    assert extra.status_code == 422


async def test_removing_an_assignment_hides_the_candidate_and_a_repeat_is_204(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    assignments: FakeAssignments,
    recruiter: dict[str, str],
) -> None:
    candidate_id = assignments.seed_candidate()
    interviewer_id, interviewer_headers = await sign_in_interviewer(
        users, sessions, "i@example.com"
    )
    await assignments.add(candidate_id, interviewer_id)
    url = f"/v1/candidates/{candidate_id}/assignments/{interviewer_id}"

    before = await client.get("/v1/me/candidates", headers=interviewer_headers)
    removed = await client.delete(url, headers=recruiter)
    repeated = await client.delete(url, headers=recruiter)
    after = await client.get("/v1/me/candidates", headers=interviewer_headers)
    unknown = await client.delete(
        f"/v1/candidates/{uuid.uuid4()}/assignments/{interviewer_id}", headers=recruiter
    )

    assert len(before.json()["data"]) == 1
    assert (removed.status_code, removed.content) == (204, b"")
    assert repeated.status_code == 204
    assert after.json() == {"data": []}
    assert unknown.status_code == 404


async def test_an_interviewer_lists_only_their_own_candidates(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    assignments: FakeAssignments,
) -> None:
    mine, mine_headers = await sign_in_interviewer(users, sessions, "a@example.com")
    theirs, _ = await sign_in_interviewer(users, sessions, "b@example.com")
    second, first, hidden = (assignments.seed_candidate(n) for n in (2, 1, 3))
    for candidate_id in (second, first):
        await assignments.add(candidate_id, mine)
    await assignments.add(hidden, theirs)
    assignments.submitted.add((first, mine))

    response = await client.get("/v1/me/candidates", headers=mine_headers)

    body = response.json()["data"]
    assert [(c["candidate_no"], c["has_submitted"]) for c in body] == [(1, True), (2, False)]
    assert set(body[0]) == {
        "candidate_id",
        "candidate_no",
        "role_id",
        "role_title",
        "has_submitted",
    }
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(("query", "status", "passed"), [("", 200, 100), ("?limit=200", 200, 200)])
async def test_the_list_limit_defaults_to_100_and_caps_at_200(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    assignments: FakeAssignments,
    query: str,
    status: int,
    passed: int,
) -> None:
    _, headers = await sign_in_interviewer(users, sessions, "a@example.com")

    response = await client.get(f"/v1/me/candidates{query}", headers=headers)

    assert response.status_code == status
    assert assignments.limits == [passed]


@pytest.mark.parametrize("query", ["?limit=0", "?limit=201"])
async def test_a_list_limit_outside_1_to_200_is_422(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    assignments: FakeAssignments,
    query: str,
) -> None:
    _, headers = await sign_in_interviewer(users, sessions, "a@example.com")

    response = await client.get(f"/v1/me/candidates{query}", headers=headers)

    assert response.status_code == 422
    assert assignments.limits == []


async def test_a_recruiter_lists_interviewers_with_id_and_name_only(
    client: AsyncClient, users: FakeUsers, recruiter: dict[str, str]
) -> None:
    zed = users.add(email="z@example.com", role="interviewer", name="Zed")
    ann = users.add(email="a@example.com", role="interviewer", name="Ann")
    users.add(email="r9@example.com", role="recruiter", name="Boss")

    response = await client.get("/v1/users?role=interviewer", headers=recruiter)

    assert response.status_code == 200
    assert response.json() == {
        "data": [{"id": str(ann.id), "name": "Ann"}, {"id": str(zed.id), "name": "Zed"}]
    }
    assert response.headers["cache-control"] == "no-store"


async def test_listing_interviewers_is_for_a_recruiter_with_a_session(
    client: AsyncClient, users: FakeUsers, sessions: FakeSessions
) -> None:
    _, headers = await sign_in_interviewer(users, sessions, "i@example.com")

    anonymous = await client.get("/v1/users?role=interviewer")
    by_interviewer = await client.get("/v1/users?role=interviewer", headers=headers)

    assert (anonymous.status_code, by_interviewer.status_code) == (401, 403)


@pytest.mark.parametrize("query", ["", "?role=recruiter", "?role=interviewer&limit=201"])
async def test_listing_users_needs_role_interviewer_and_a_bounded_limit(
    client: AsyncClient, recruiter: dict[str, str], query: str
) -> None:
    response = await client.get(f"/v1/users{query}", headers=recruiter)

    assert response.status_code == 422


async def test_a_recruiter_lists_a_candidates_assigned_interviewers_by_name(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    assignments: FakeAssignments,
    recruiter: dict[str, str],
) -> None:
    candidate_id = assignments.seed_candidate()
    other_id = assignments.seed_candidate(2)
    ann = users.add(email="a@example.com", role="interviewer", name="Ann")
    bob = users.add(email="b@example.com", role="interviewer", name="Bob")
    await assignments.add(candidate_id, ann.id)
    await assignments.add(other_id, bob.id)

    response = await client.get(f"/v1/candidates/{candidate_id}/assignments", headers=recruiter)

    assert response.status_code == 200
    assert response.json() == {"data": [{"user_id": str(ann.id), "name": "Ann"}]}
    assert response.headers["cache-control"] == "no-store"


async def test_listing_assignments_is_404_for_an_unknown_candidate_and_403_for_an_interviewer(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    assignments: FakeAssignments,
    recruiter: dict[str, str],
) -> None:
    known = assignments.seed_candidate()
    _, headers = await sign_in_interviewer(users, sessions, "i@example.com")

    unknown = await client.get(f"/v1/candidates/{uuid.uuid4()}/assignments", headers=recruiter)
    forbidden = await client.get(f"/v1/candidates/{known}/assignments", headers=headers)
    anonymous = await client.get(f"/v1/candidates/{known}/assignments")

    assert (unknown.status_code, unknown.json()["error"]["code"]) == (404, "not_found")
    assert (forbidden.status_code, anonymous.status_code) == (403, 401)
