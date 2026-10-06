"""Override, stage and reveal over HTTP with in-memory repositories (HK-60)."""

import uuid

import pytest
from httpx import AsyncClient

from tests.api.fake_decisions import FakeAudit, FakeDecisions
from tests.api.fakes import FakeSessions, FakeUsers, SignedIn


async def sign_in(
    users: FakeUsers, sessions: FakeSessions, role: str
) -> tuple[SignedIn, uuid.UUID]:
    user = users.add(email=f"{role}@example.com", role=role)
    return await sessions.sign_in(user), user.id


def override_url(candidate: uuid.UUID, criterion: uuid.UUID) -> str:
    return f"/v1/candidates/{candidate}/scores/{criterion}/override"


NOTE = "Led the migration, seen in the interview"


async def test_override_keeps_the_model_value_and_writes_the_audit_row(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    decisions: FakeDecisions,
    audit: FakeAudit,
) -> None:
    _, candidate, criterion = decisions.seed(model_score=2)
    who, user_id = await sign_in(users, sessions, "recruiter")

    response = await client.put(
        override_url(candidate, criterion),
        headers=who.unsafe_headers,
        json={"override_score": 4, "note": NOTE},
    )

    body = response.json()
    assert response.status_code == 200
    assert (body["model_score"], body["override_score"], body["source"]) == (
        2,
        4,
        "recruiter_override",
    )
    assert body["override_note"] == NOTE
    assert audit.events == [
        {
            "kind": "score_override",
            "candidate": candidate,
            "actor": user_id,
            "criterion": "Python",
            "old": 2,
            "new": 4,
            "note": NOTE,
        }
    ]


async def test_a_second_override_audits_the_first_override_as_the_old_value(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    decisions: FakeDecisions,
    audit: FakeAudit,
) -> None:
    _, candidate, criterion = decisions.seed(model_score=2)
    who, _ = await sign_in(users, sessions, "recruiter")
    url = override_url(candidate, criterion)
    await client.put(url, headers=who.unsafe_headers, json={"override_score": 4, "note": NOTE})

    await client.put(url, headers=who.unsafe_headers, json={"override_score": 1, "note": NOTE})

    assert [(e["old"], e["new"]) for e in audit.events] == [(2, 4), (4, 1)]


@pytest.mark.parametrize(
    ("score", "note", "accepted"),
    [(4, "123456789", False), (4, "1234567890", True), (4, "   short   ", False), (5, NOTE, False)],
)
async def test_override_needs_a_score_of_0_to_4_and_a_note_of_ten_characters(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    decisions: FakeDecisions,
    audit: FakeAudit,
    score: int,
    note: str,
    accepted: bool,
) -> None:
    _, candidate, criterion = decisions.seed()
    who, _ = await sign_in(users, sessions, "recruiter")

    response = await client.put(
        override_url(candidate, criterion),
        headers=who.unsafe_headers,
        json={"override_score": score, "note": note},
    )

    assert (response.status_code == 200) is accepted
    assert accepted or response.json()["error"]["code"] == "validation_error"
    assert len(audit.events) == (1 if accepted else 0)


async def test_override_of_a_score_from_an_older_criteria_version_is_409(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    decisions: FakeDecisions,
    audit: FakeAudit,
) -> None:
    role, candidate, criterion = decisions.seed(version=1)
    decisions.role_version[role] = 2
    who, _ = await sign_in(users, sessions, "recruiter")

    response = await client.put(
        override_url(candidate, criterion),
        headers=who.unsafe_headers,
        json={"override_score": 4, "note": NOTE},
    )

    assert (response.status_code, response.json()["error"]["code"]) == (409, "scores_stale")
    assert audit.events == []


async def test_override_of_an_unknown_candidate_or_criterion_is_404(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    decisions: FakeDecisions,
) -> None:
    _, candidate, criterion = decisions.seed()
    who, _ = await sign_in(users, sessions, "recruiter")
    body = {"override_score": 4, "note": NOTE}

    no_candidate = await client.put(
        override_url(uuid.uuid4(), criterion), headers=who.unsafe_headers, json=body
    )
    no_criterion = await client.put(
        override_url(candidate, uuid.uuid4()), headers=who.unsafe_headers, json=body
    )

    assert (no_candidate.status_code, no_criterion.status_code) == (404, 404)


async def test_stage_change_writes_from_to_user_and_the_reason(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    decisions: FakeDecisions,
    audit: FakeAudit,
) -> None:
    _, candidate, _ = decisions.seed(stage="new")
    who, user_id = await sign_in(users, sessions, "recruiter")

    response = await client.post(
        f"/v1/candidates/{candidate}/stage",
        headers=who.unsafe_headers,
        json={"stage": "rejected", "reason": "  Missing a must-have  "},
    )

    assert response.status_code == 200
    assert response.json() == {
        "candidate_id": str(candidate),
        "from_stage": "new",
        "to_stage": "rejected",
    }
    assert audit.events == [
        {
            "kind": "stage_change",
            "candidate": candidate,
            "actor": user_id,
            "from": "new",
            "to": "rejected",
            "note": "Missing a must-have",
        }
    ]


async def test_stage_to_the_same_stage_is_409_and_writes_nothing(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    decisions: FakeDecisions,
    audit: FakeAudit,
) -> None:
    _, candidate, _ = decisions.seed(stage="screened")
    who, _ = await sign_in(users, sessions, "recruiter")

    response = await client.post(
        f"/v1/candidates/{candidate}/stage", headers=who.unsafe_headers, json={"stage": "screened"}
    )

    assert (response.status_code, response.json()["error"]["code"]) == (409, "same_stage")
    assert (audit.events, decisions.stage_writes) == ([], [])


async def test_an_unknown_stage_is_422_and_an_unknown_candidate_is_404(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    decisions: FakeDecisions,
) -> None:
    _, candidate, _ = decisions.seed()
    who, _ = await sign_in(users, sessions, "recruiter")

    bad_stage = await client.post(
        f"/v1/candidates/{candidate}/stage", headers=who.unsafe_headers, json={"stage": "maybe"}
    )
    missing = await client.post(
        f"/v1/candidates/{uuid.uuid4()}/stage", headers=who.unsafe_headers, json={"stage": "offer"}
    )

    assert (bad_stage.status_code, missing.status_code) == (422, 404)


async def test_nothing_changes_stage_but_the_stage_route(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    decisions: FakeDecisions,
) -> None:
    _, candidate, criterion = decisions.seed(stage="new")
    who, _ = await sign_in(users, sessions, "recruiter")

    await client.put(
        override_url(candidate, criterion),
        headers=who.unsafe_headers,
        json={"override_score": 0, "note": NOTE},
    )
    await client.post(f"/v1/candidates/{candidate}:reveal-identity", headers=who.unsafe_headers)

    assert decisions.stage_writes == []


async def test_reveal_audits_and_returns_the_identity_without_caching(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    decisions: FakeDecisions,
    audit: FakeAudit,
) -> None:
    _, candidate, _ = decisions.seed()
    who, user_id = await sign_in(users, sessions, "recruiter")

    response = await client.post(
        f"/v1/candidates/{candidate}:reveal-identity", headers=who.unsafe_headers
    )

    assert response.status_code == 200
    assert response.json() == {"identity_name": "Jane Doe", "file_name": "Jane_Doe_CV.pdf"}
    assert response.headers["cache-control"] == "no-store"
    assert audit.events == [{"kind": "identity_reveal", "candidate": candidate, "actor": user_id}]


async def test_reveal_of_an_unknown_candidate_is_404_and_leaves_no_audit_row(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    decisions: FakeDecisions,
    audit: FakeAudit,
) -> None:
    who, _ = await sign_in(users, sessions, "recruiter")

    response = await client.post(
        f"/v1/candidates/{uuid.uuid4()}:reveal-identity", headers=who.unsafe_headers
    )

    assert response.status_code == 404
    assert audit.events == []


async def test_an_interviewer_cannot_override_move_or_reveal(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    decisions: FakeDecisions,
    audit: FakeAudit,
) -> None:
    _, candidate, criterion = decisions.seed()
    who, _ = await sign_in(users, sessions, "interviewer")
    base = f"/v1/candidates/{candidate}"

    responses = [
        await client.put(
            override_url(candidate, criterion),
            headers=who.unsafe_headers,
            json={"override_score": 4, "note": NOTE},
        ),
        await client.post(f"{base}/stage", headers=who.unsafe_headers, json={"stage": "rejected"}),
        await client.post(f"{base}:reveal-identity", headers=who.unsafe_headers),
    ]

    assert [r.status_code for r in responses] == [403, 403, 403]
    assert (audit.events, decisions.stage_writes) == ([], [])


async def test_a_decision_without_the_csrf_token_is_403(
    client: AsyncClient,
    users: FakeUsers,
    sessions: FakeSessions,
    decisions: FakeDecisions,
    audit: FakeAudit,
) -> None:
    _, candidate, _ = decisions.seed()
    who, _ = await sign_in(users, sessions, "recruiter")

    response = await client.post(f"/v1/candidates/{candidate}:reveal-identity", headers=who.cookie)

    assert (response.status_code, response.json()["error"]["code"]) == (403, "csrf_failed")
    assert audit.events == []
