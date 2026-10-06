"""The feedback routes against fake repositories (HK-63; AC-US-00-014-2 to AC-US-00-014-5)."""

import uuid
from dataclasses import dataclass

import pytest
from httpx import AsyncClient

from app.api.feedback.schemas import FeedbackItem
from app.core.errors import IncompleteFeedbackError
from app.domain.feedback.service import check_complete
from tests.api.fakes import FakeCriteria, FakeFeedback, FakeRoles, FakeSessions, FakeUsers


@dataclass
class Scene:
    candidate_id: uuid.UUID
    criteria_ids: list[uuid.UUID]
    interviewer_id: uuid.UUID
    interviewer: dict[str, str]
    recruiter: dict[str, str]
    stranger: dict[str, str]  # an interviewer with no assignment


@pytest.fixture
async def scene(
    users: FakeUsers,
    sessions: FakeSessions,
    roles: FakeRoles,
    criteria: FakeCriteria,
    feedback: FakeFeedback,
) -> Scene:
    role = roles.seed(status="approved")
    ids = [criteria.seed(role.id, name, position=n).id for n, name in enumerate(["Python", "SQL"])]
    me = users.add(email="i@example.com", role="interviewer")
    candidate_id = feedback.candidate(role.id, me.id)
    return Scene(
        candidate_id,
        ids,
        me.id,
        (await sessions.sign_in(me)).unsafe_headers,
        (await sessions.sign_in(users.add(email="r@example.com", role="recruiter"))).unsafe_headers,
        (
            await sessions.sign_in(users.add(email="s@example.com", role="interviewer"))
        ).unsafe_headers,
    )


def body(scene: Scene, *, score: int = 3, comment: str = "Solid") -> dict[str, object]:
    return {
        "items": [
            {"criterion_id": str(c), "score": score, "comment": comment} for c in scene.criteria_ids
        ]
    }


def url(scene: Scene) -> str:
    return f"/v1/candidates/{scene.candidate_id}/feedback"


def approve_url(scene: Scene) -> str:
    return f"{url(scene)}/{scene.interviewer_id}:approve-edit"


def item(criterion_id: uuid.UUID, comment: str = "ok") -> FeedbackItem:
    return FeedbackItem(criterion_id=criterion_id, score=2, comment=comment)


A, B = uuid.uuid4(), uuid.uuid4()


def test_feedback_needs_every_criterion_scored_and_commented() -> None:
    assert check_complete([item(A), item(B)], {A, B}) == {A: (2, "ok"), B: (2, "ok")}


@pytest.mark.parametrize(
    "items",
    [
        [item(A)],
        [item(A), item(A)],
        [item(A), item(uuid.uuid4())],
        [item(A), item(B, " ")],
    ],
    ids=["missing", "twice", "unknown", "blank-comment"],
)
def test_incomplete_feedback_is_refused(items: list[FeedbackItem]) -> None:
    with pytest.raises(IncompleteFeedbackError):
        check_complete(items, {A, B})


async def test_submit_stores_a_locked_row_per_criterion(client: AsyncClient, scene: Scene) -> None:
    response = await client.post(url(scene), json=body(scene), headers=scene.interviewer)

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert [(r["score"], r["locked"]) for r in response.json()["data"]] == [(3, True), (3, True)]


async def test_submit_with_a_criterion_missing_is_422_incomplete_feedback(
    client: AsyncClient, scene: Scene, feedback: FakeFeedback
) -> None:
    one = {"criterion_id": str(scene.criteria_ids[0]), "score": 3, "comment": "Solid"}
    partial = {"items": [one]}

    response = await client.post(url(scene), json=partial, headers=scene.interviewer)

    assert (response.status_code, response.json()["error"]["code"]) == (422, "incomplete_feedback")
    assert feedback.stored == []


async def test_a_score_outside_0_to_4_is_a_validation_error(
    client: AsyncClient, scene: Scene
) -> None:
    response = await client.post(url(scene), json=body(scene, score=5), headers=scene.interviewer)

    assert (response.status_code, response.json()["error"]["code"]) == (422, "validation_error")


async def test_submitted_feedback_is_locked(client: AsyncClient, scene: Scene) -> None:
    await client.post(url(scene), json=body(scene), headers=scene.interviewer)

    again = await client.post(url(scene), json=body(scene, score=1), headers=scene.interviewer)
    put = await client.put(url(scene), json=body(scene, score=1), headers=scene.interviewer)

    assert (again.status_code, again.json()["error"]["code"]) == (409, "feedback_locked")
    assert (put.status_code, put.json()["error"]["code"]) == (409, "feedback_locked")


async def test_an_unassigned_interviewer_gets_404_on_every_route(
    client: AsyncClient, scene: Scene, feedback: FakeFeedback
) -> None:
    other = uuid.uuid4()
    feedback.seed(scene.candidate_id, scene.interviewer_id, scene.criteria_ids[0])

    responses = [
        await client.post(url(scene), json=body(scene), headers=scene.stranger),
        await client.get(url(scene), headers=scene.stranger),
        await client.put(url(scene), json=body(scene), headers=scene.stranger),
        await client.post(
            f"/v1/candidates/{other}/feedback", json=body(scene), headers=scene.interviewer
        ),
    ]

    assert [r.status_code for r in responses] == [404, 404, 404, 404]
    assert len(feedback.stored) == 1


async def test_an_interviewer_reads_only_their_own_and_a_recruiter_reads_all(
    client: AsyncClient, scene: Scene, feedback: FakeFeedback
) -> None:
    colleague = uuid.uuid4()
    feedback.assigned.add((scene.candidate_id, colleague))
    feedback.seed(scene.candidate_id, colleague, scene.criteria_ids[0], comment="theirs")
    await client.post(url(scene), json=body(scene, comment="mine"), headers=scene.interviewer)

    own = await client.get(url(scene), headers=scene.interviewer)
    every = await client.get(url(scene), headers=scene.recruiter)
    missing = await client.get(f"/v1/candidates/{uuid.uuid4()}/feedback", headers=scene.recruiter)

    assert {r["comment"] for r in own.json()["data"]} == {"mine"}
    assert {r["comment"] for r in every.json()["data"]} == {"mine", "theirs"}
    assert missing.status_code == 404


async def test_approved_edit_unlocks_saves_relocks_and_audits_the_old_comment(
    client: AsyncClient, scene: Scene, feedback: FakeFeedback
) -> None:
    await client.post(url(scene), json=body(scene, comment="first"), headers=scene.interviewer)

    approved = await client.post(approve_url(scene), headers=scene.recruiter)
    edited = await client.put(
        url(scene), json=body(scene, score=4, comment="second"), headers=scene.interviewer
    )
    locked_again = await client.put(url(scene), json=body(scene), headers=scene.interviewer)

    assert [r["locked"] for r in approved.json()["data"]] == [False, False]
    assert edited.status_code == 200
    assert [(r["score"], r["comment"], r["locked"]) for r in edited.json()["data"]] == [
        (4, "second", True)
    ] * 2
    assert locked_again.status_code == 409
    assert [a["kind"] for a in feedback.audit] == [
        "feedback_edit_approved",
        "feedback_edited",
        "feedback_edited",
    ]
    assert feedback.audit[1]["old_comment"] == "first"


async def test_approving_twice_audits_once_and_an_unknown_submission_is_404(
    client: AsyncClient, scene: Scene, feedback: FakeFeedback
) -> None:
    nothing = await client.post(approve_url(scene), headers=scene.recruiter)
    await client.post(url(scene), json=body(scene), headers=scene.interviewer)

    await client.post(approve_url(scene), headers=scene.recruiter)
    await client.post(approve_url(scene), headers=scene.recruiter)

    assert nothing.status_code == 404
    assert [a["kind"] for a in feedback.audit] == ["feedback_edit_approved"]


async def test_an_interviewer_cannot_approve_their_own_edit(
    client: AsyncClient, scene: Scene
) -> None:
    await client.post(url(scene), json=body(scene), headers=scene.interviewer)

    response = await client.post(approve_url(scene), headers=scene.interviewer)

    assert (response.status_code, response.json()["error"]["code"]) == (403, "forbidden")
