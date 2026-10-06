"""The ranked list, candidate detail and resume text routes against a fake repository (HK-59)."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.candidates.router import get_candidates
from app.db.repositories.candidates import TextRow
from tests.api.fake_candidates import FakeCandidates, cell
from tests.api.fakes import FakeCriteria, FakeRoles, FakeSessions, FakeUsers


@pytest.fixture
def candidates(app: FastAPI) -> FakeCandidates:
    fake = FakeCandidates()
    app.dependency_overrides[get_candidates] = lambda: fake
    return fake


@pytest.fixture
async def recruiter(users: FakeUsers, sessions: FakeSessions) -> dict[str, str]:
    return (await sessions.sign_in(users.add(email="r@example.com", role="recruiter"))).cookie


async def interviewer_headers(
    users: FakeUsers, sessions: FakeSessions
) -> tuple[dict[str, str], uuid.UUID]:
    user = users.add(email="i@example.com", role="interviewer")
    return (await sessions.sign_in(user)).cookie, user.id


async def test_ranked_list_returns_rows_with_cells_page_and_no_names(
    client: AsyncClient,
    candidates: FakeCandidates,
    criteria: FakeCriteria,
    recruiter: dict[str, str],
) -> None:
    role_id = uuid.uuid4()
    candidates.roles.add(role_id)
    candidates.page = type(candidates.page)(
        [
            candidates.ranked_row(14, cell("Python", override=4), cell("Go", status="no_evidence")),
            candidates.ranked_row(15),
        ],
        2,
    )

    response = await client.get(f"/v1/roles/{role_id}/candidates", headers=recruiter)

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == {"limit": 100, "offset": 0, "total": 2}
    first = body["data"][0]
    assert (first["candidate_no"], first["total"], first["must_have_total"]) == (14, 11.5, 2)
    assert [c["source"] for c in first["scores"]] == ["recruiter_override", "no_evidence_found"]
    assert body["data"][1]["scores"] == []  # an unscored candidate is still listed
    assert "file_name" not in first
    assert "identity_name" not in first
    assert response.headers["cache-control"] == "no-store"


async def test_ranked_list_passes_filter_sort_and_paging_to_the_query(
    client: AsyncClient,
    candidates: FakeCandidates,
    criteria: FakeCriteria,
    recruiter: dict[str, str],
) -> None:
    role_id = uuid.uuid4()
    candidates.roles.add(role_id)
    python = criteria.seed(role_id, "Python")

    response = await client.get(
        f"/v1/roles/{role_id}/candidates",
        params={"filter[stage]": "interview", "sort": str(python.id), "limit": 5, "offset": 10},
        headers=recruiter,
    )

    assert response.status_code == 200
    assert candidates.ranked_calls == [("interview", python.id, 5, 10)]


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "not-a-criterion"},
        {"sort": str(uuid.uuid4())},  # a uuid, but not a criterion of this role
        {"limit": 201},
        {"limit": 0},
        {"offset": 1001},
        {"filter[stage]": "promoted"},
    ],
)
async def test_ranked_list_rejects_bad_query_values(
    client: AsyncClient,
    candidates: FakeCandidates,
    criteria: FakeCriteria,
    recruiter: dict[str, str],
    params: dict[str, str | int],
) -> None:
    role_id = uuid.uuid4()
    candidates.roles.add(role_id)

    response = await client.get(f"/v1/roles/{role_id}/candidates", params=params, headers=recruiter)

    assert (response.status_code, response.json()["error"]["code"]) == (422, "validation_error")


async def test_ranked_list_of_an_unknown_role_is_404(
    client: AsyncClient, candidates: FakeCandidates, recruiter: dict[str, str]
) -> None:
    response = await client.get(f"/v1/roles/{uuid.uuid4()}/candidates", headers=recruiter)

    assert (response.status_code, response.json()["error"]["code"]) == (404, "not_found")


async def test_an_interviewer_cannot_read_the_ranked_list(
    client: AsyncClient,
    candidates: FakeCandidates,
    roles: FakeRoles,
    users: FakeUsers,
    sessions: FakeSessions,
) -> None:
    headers, _ = await interviewer_headers(users, sessions)

    response = await client.get(f"/v1/roles/{uuid.uuid4()}/candidates", headers=headers)

    assert (response.status_code, response.json()["error"]["code"]) == (403, "forbidden")


async def test_recruiter_detail_has_quotes_notes_and_audit(
    client: AsyncClient, candidates: FakeCandidates, recruiter: dict[str, str]
) -> None:
    row = candidates.seed(uuid.uuid4())
    candidates.score_cells = [cell("Python", override=4)]

    response = await client.get(f"/v1/candidates/{row.id}", headers=recruiter)

    body = response.json()
    assert response.status_code == 200
    assert (body["stage"], body["processing_status"]) == ("screened", "done")
    assert body["scores"][0]["quote"] == "Built a payments service."
    assert body["scores"][0]["override_note"] == "Strong referee call."
    assert body["audit"][0]["kind"] == "stage_change"
    assert not {"file_name", "identity_name"} & body.keys()


async def test_an_unassigned_interviewer_gets_404_the_same_as_for_a_missing_candidate(
    client: AsyncClient, candidates: FakeCandidates, users: FakeUsers, sessions: FakeSessions
) -> None:
    row = candidates.seed(uuid.uuid4())
    headers, _ = await interviewer_headers(users, sessions)

    unassigned = await client.get(f"/v1/candidates/{row.id}", headers=headers)
    missing = await client.get(f"/v1/candidates/{uuid.uuid4()}", headers=headers)

    assert unassigned.status_code == missing.status_code == 404
    assert unassigned.json()["error"]["code"] == missing.json()["error"]["code"] == "not_found"
    assert unassigned.json()["error"]["message"] == missing.json()["error"]["message"]


async def test_an_assigned_interviewer_sees_the_number_but_no_scores_before_submitting(
    client: AsyncClient, candidates: FakeCandidates, users: FakeUsers, sessions: FakeSessions
) -> None:
    row = candidates.seed(uuid.uuid4())
    candidates.score_cells = [cell("Python")]
    headers, user_id = await interviewer_headers(users, sessions)
    candidates.assigned.add((row.id, user_id))

    response = await client.get(f"/v1/candidates/{row.id}", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "id": str(row.id),
        "candidate_no": 14,
        "role_id": str(row.role_id),
        "has_submitted": False,
    }


async def test_after_submitting_an_interviewer_sees_scores_but_never_evidence_or_audit(
    client: AsyncClient, candidates: FakeCandidates, users: FakeUsers, sessions: FakeSessions
) -> None:
    row = candidates.seed(uuid.uuid4())
    candidates.score_cells = [cell("Python", override=4)]
    headers, user_id = await interviewer_headers(users, sessions)
    candidates.assigned.add((row.id, user_id))
    candidates.submitted.add((row.id, user_id))

    response = await client.get(f"/v1/candidates/{row.id}", headers=headers)

    body = response.json()
    assert response.status_code == 200
    assert body["has_submitted"] is True
    assert (body["scores"][0]["model_score"], body["scores"][0]["override_score"]) == (3, 4)
    assert (
        body["scores"][0]["quote"],
        body["scores"][0]["flag_reason"],
        body["scores"][0]["override_note"],
    ) == (None, None, None)
    assert not {"audit", "stage", "processing_status"} & body.keys()


async def test_text_is_recruiter_only_and_404_until_the_worker_stores_it(
    client: AsyncClient,
    candidates: FakeCandidates,
    recruiter: dict[str, str],
    users: FakeUsers,
    sessions: FakeSessions,
) -> None:
    row = candidates.seed(uuid.uuid4())
    interviewer, user_id = await interviewer_headers(users, sessions)
    candidates.assigned.add((row.id, user_id))

    refused = await client.get(f"/v1/candidates/{row.id}/text", headers=interviewer)
    pending = await client.get(f"/v1/candidates/{row.id}/text", headers=recruiter)
    candidates.texts_by_id[row.id] = TextRow("Jane Doe. Built.", "Built.")
    found = await client.get(f"/v1/candidates/{row.id}/text", headers=recruiter)

    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "forbidden")
    assert pending.status_code == 404
    assert found.json() == {"raw_text": "Jane Doe. Built.", "anonymized_text": "Built."}
    assert found.headers["cache-control"] == "no-store"
