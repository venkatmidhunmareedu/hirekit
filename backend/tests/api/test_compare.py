"""GET /v1/compare against fake repositories (HK-64)."""

import uuid
from collections.abc import Sequence

import pytest
from httpx import AsyncClient, Response

from app.db.models import Role, User
from app.db.repositories.compare import FeedbackCell, ScoreCell
from app.domain.compare.service import disagrees
from tests.api.fake_compare import FakeCompare
from tests.api.fakes import FakeCriteria, FakeRoles, FakeSessions, FakeUsers


@pytest.fixture
async def recruiter(users: FakeUsers, sessions: FakeSessions) -> dict[str, str]:
    return (
        await sessions.sign_in(users.add(email="r@example.com", role="recruiter"))
    ).unsafe_headers


@pytest.fixture
def role(roles: FakeRoles) -> Role:
    return roles.seed(status="approved")


async def get(
    client: AsyncClient, ids: Sequence[uuid.UUID | str], headers: dict[str, str]
) -> Response:
    return await client.get("/v1/compare", params={"ids": ",".join(map(str, ids))}, headers=headers)


def error_of(response: Response) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


async def test_compare_needs_two_to_four_candidates(
    client: AsyncClient,
    compare: FakeCompare,
    criteria: FakeCriteria,
    role: Role,
    recruiter: dict[str, str],
) -> None:
    criteria.seed(role.id, "Python")
    five = [compare.seed(role.id) for _ in range(5)]

    results = [
        error_of(await get(client, five[:1], recruiter)),
        error_of(await get(client, five, recruiter)),
        error_of(await get(client, [five[0], five[0]], recruiter)),
        error_of(await get(client, ["not-a-uuid", five[0]], recruiter)),
    ]
    bounds = [(await get(client, five[:n], recruiter)).status_code for n in (2, 4)]

    assert results == [(422, "validation_error")] * 4
    assert bounds == [200, 200]


async def test_compare_without_ids_is_a_validation_error(
    client: AsyncClient, recruiter: dict[str, str]
) -> None:
    response = await client.get("/v1/compare", headers=recruiter)

    assert error_of(response) == (422, "validation_error")


async def test_compare_groups_criteria_by_kind_and_keeps_the_order_asked(
    client: AsyncClient,
    compare: FakeCompare,
    criteria: FakeCriteria,
    role: Role,
    recruiter: dict[str, str],
) -> None:
    nice = criteria.seed(role.id, "Go", position=0)
    nice.kind = "nice_to_have"
    must = criteria.seed(role.id, "Python", position=1)
    a, b = compare.seed(role.id), compare.seed(role.id)
    compare.score_rows.append(ScoreCell(b, must.id, 3, 4))

    body = (await get(client, [b, a], recruiter)).json()

    assert [c["name"] for c in body["criteria"]] == ["Python", "Go"]
    assert [c["candidate_id"] for c in body["candidates"]] == [str(b), str(a)]
    first = body["candidates"][0]["cells"]
    assert [c["criterion_id"] for c in first] == [str(must.id), str(nice.id)]
    assert (first[0]["model_score"], first[0]["override_score"]) == (3, 4)
    assert (first[1]["model_score"], first[1]["override_score"]) == (None, None)


async def test_compare_marks_interviewer_disagreement(
    client: AsyncClient,
    compare: FakeCompare,
    criteria: FakeCriteria,
    role: Role,
    recruiter: dict[str, str],
) -> None:
    must = criteria.seed(role.id, "Python")
    a, b = compare.seed(role.id), compare.seed(role.id)
    one, two = uuid.uuid4(), uuid.uuid4()
    compare.feedback_rows += [
        FeedbackCell(a, one, must.id, 1, "weak", True),
        FeedbackCell(a, two, must.id, 4, "strong", True),
        FeedbackCell(b, one, must.id, 3, "ok", True),
        FeedbackCell(b, two, must.id, 3, "ok", True),
    ]

    cells = [c["cells"][0] for c in (await get(client, [a, b], recruiter)).json()["candidates"]]

    assert [c["disagreement"] for c in cells] == [True, False]
    assert len(cells[0]["feedback"]) == 2


def test_disagreement_is_any_two_different_scores() -> None:
    assert (disagrees([]), disagrees([3]), disagrees([3, 3]), disagrees([3, 4])) == (
        False,
        False,
        False,
        True,
    )


async def test_compare_with_one_unassigned_id_is_404_for_the_whole_request(
    client: AsyncClient,
    compare: FakeCompare,
    criteria: FakeCriteria,
    role: Role,
    users: FakeUsers,
    sessions: FakeSessions,
) -> None:
    criteria.seed(role.id, "Python")
    mine, theirs = compare.seed(role.id), compare.seed(role.id)
    interviewer: User = users.add(email="i@example.com", role="interviewer")
    compare.assigned.add((mine, interviewer.id))
    headers = (await sessions.sign_in(interviewer)).unsafe_headers

    refused = await get(client, [mine, theirs], headers)

    assert error_of(refused) == (404, "not_found")


async def test_an_unknown_id_is_404_for_a_recruiter(
    client: AsyncClient,
    compare: FakeCompare,
    criteria: FakeCriteria,
    role: Role,
    recruiter: dict[str, str],
) -> None:
    criteria.seed(role.id, "Python")

    response = await get(client, [compare.seed(role.id), uuid.uuid4()], recruiter)

    assert error_of(response) == (404, "not_found")


async def test_candidates_of_two_roles_cannot_be_compared(
    client: AsyncClient,
    compare: FakeCompare,
    criteria: FakeCriteria,
    roles: FakeRoles,
    role: Role,
    recruiter: dict[str, str],
) -> None:
    other = roles.seed(status="approved")
    criteria.seed(role.id, "Python")

    response = await get(client, [compare.seed(role.id), compare.seed(other.id)], recruiter)

    assert error_of(response) == (422, "validation_error")


async def test_a_role_without_criteria_is_no_criteria(
    client: AsyncClient,
    compare: FakeCompare,
    criteria: FakeCriteria,
    role: Role,
    recruiter: dict[str, str],
) -> None:
    response = await get(client, [compare.seed(role.id), compare.seed(role.id)], recruiter)

    assert error_of(response) == (422, "no_criteria")


async def test_the_response_is_not_cached(
    client: AsyncClient,
    compare: FakeCompare,
    criteria: FakeCriteria,
    role: Role,
    recruiter: dict[str, str],
) -> None:
    criteria.seed(role.id, "Python")

    response = await get(client, [compare.seed(role.id), compare.seed(role.id)], recruiter)

    assert response.headers["cache-control"] == "no-store"
