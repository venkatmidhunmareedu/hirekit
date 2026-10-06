"""The ranked list, detail and text routes against Postgres: the SQL, the ranking and the grants."""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import Settings
from app.core.passwords import hash_password
from app.main import create_app

pytestmark = pytest.mark.integration

PASSWORD = f"pw-{uuid4().hex}"


@dataclass
class World:
    engine: AsyncEngine
    recruiter: AsyncClient
    interviewer: AsyncClient
    interviewer_id: UUID
    recruiter_id: UUID
    role_id: UUID
    python: UUID
    go: UUID
    a: UUID  # scored now: Python 3, Go no_evidence; total 9
    b: UUID  # scored one version ago (stale): Python 2, Go 3; total 9, ties with a
    c: UUID  # nothing scored yet; total 0
    d: UUID  # Python model 1 overridden to 4; total 12


async def sql(engine: AsyncEngine, statement: str, **params: object) -> UUID:
    async with engine.begin() as conn:
        return UUID(str((await conn.execute(text(statement), params)).scalar_one()))


async def login(app_client: AsyncClient, email: str) -> None:
    response = await app_client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text


@pytest.fixture
async def world(engine: AsyncEngine) -> AsyncIterator[World]:
    tag = f"it59-{uuid4().hex[:12]}"
    password_hash = hash_password(PASSWORD)
    user = (
        "INSERT INTO users(name, email, role, password_hash) VALUES (:n, :e, :r, :h) RETURNING id"
    )
    recruiter_id = await sql(
        engine, user, n=tag, e=f"r-{tag}@example.com", r="recruiter", h=password_hash
    )
    interviewer_id = await sql(
        engine, user, n=tag, e=f"i-{tag}@example.com", r="interviewer", h=password_hash
    )
    role_id = await sql(
        engine,
        "INSERT INTO roles(title, job_description, status, criteria_version) "
        "VALUES (:t, 'Build.', 'approved', 2) RETURNING id",
        t=tag,
    )
    criterion = (
        "INSERT INTO criteria(role_id, name, kind, weight, position) "
        "VALUES (:r, :n, :k, :w, :p) RETURNING id"
    )
    python = await sql(engine, criterion, r=role_id, n="Python", k="must_have", w=3, p=0)
    go = await sql(engine, criterion, r=role_id, n="Go", k="nice_to_have", w=1, p=1)
    candidate = (
        "INSERT INTO candidates(role_id, file_name, content_hash) VALUES (:r, :f, :h) RETURNING id"
    )
    ids = [
        await sql(engine, candidate, r=role_id, f=f"{name}-{tag}.pdf", h=f"{n}" * 64)
        for n, name in enumerate("abcd")
    ]
    a, b, c, d = ids
    score = (
        "INSERT INTO scores(candidate_id, criterion_id, criteria_version, status, model_score, "
        "quote, override_score, override_note, overridden_by) "
        "VALUES (:c, :k, :v, :s, :m, :q, :o, :note, :by) RETURNING candidate_id"
    )

    async def put(
        cand: UUID,
        crit: UUID,
        version: int,
        status: str,
        model: int,
        *,
        override: int | None = None,
    ) -> None:
        await sql(
            engine,
            score,
            c=cand,
            k=crit,
            v=version,
            s=status,
            m=model,
            q=None if status == "no_evidence" else "Built a payments service in Python.",
            o=override,
            note=None if override is None else "Referee confirmed the depth.",
            by=None if override is None else recruiter_id,
        )

    await put(a, python, 2, "scored", 3)
    await put(a, go, 2, "no_evidence", 0)
    await put(b, python, 1, "scored", 2)
    await put(b, go, 1, "scored", 3)
    await put(d, python, 2, "scored", 1, override=4)
    await sql(
        engine,
        "INSERT INTO resume_raw_texts(candidate_id, raw_text) VALUES (:c, 'Jane Doe. Built.') "
        "RETURNING candidate_id",
        c=a,
    )
    await sql(
        engine,
        "INSERT INTO resume_texts(candidate_id, anonymized_text) VALUES (:c, 'Built.') "
        "RETURNING candidate_id",
        c=a,
    )
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO audit_events(candidate_id, actor_id, kind, from_stage, to_stage) "
                "VALUES (:c, :u, 'stage_change', 'new', 'screened')"
            ),
            {"c": a, "u": recruiter_id},
        )
    settings = Settings(
        _env_file=None, env="test", database_url=os.environ["DATABASE_URL"], log_format="console"
    )
    app = create_app(settings)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with (
            LifespanManager(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as rec,
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as inter,
        ):
            await login(rec, f"r-{tag}@example.com")
            await login(inter, f"i-{tag}@example.com")
            yield World(
                engine, rec, inter, interviewer_id, recruiter_id, role_id, python, go, a, b, c, d
            )
    finally:
        async with factory.begin() as cleanup:
            await cleanup.execute(
                text(
                    "DELETE FROM audit_events WHERE candidate_id IN "
                    "(SELECT id FROM candidates WHERE role_id = :r)"
                ),
                {"r": role_id},
            )
            await cleanup.execute(text("DELETE FROM candidates WHERE role_id = :r"), {"r": role_id})
            await cleanup.execute(text("DELETE FROM roles WHERE id = :r"), {"r": role_id})
            await cleanup.execute(text("DELETE FROM users WHERE name = :n"), {"n": tag})


def numbers(body: dict[str, list[dict[str, int]]]) -> list[int]:
    return [row["candidate_no"] for row in body["data"]]


async def ids_by_no(w: World) -> dict[UUID, int]:
    async with w.engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT id, candidate_no FROM candidates WHERE role_id = :r"), {"r": w.role_id}
        )
        return {r.id: r.candidate_no for r in rows}


async def test_ranked_list_orders_by_weighted_total_with_overrides_and_keeps_every_candidate(
    world: World,
) -> None:
    no = await ids_by_no(world)

    response = await world.recruiter.get(f"/v1/roles/{world.role_id}/candidates")

    body = response.json()
    assert response.status_code == 200
    assert numbers(body) == [no[world.d], no[world.a], no[world.b], no[world.c]]
    assert [row["total"] for row in body["data"]] == [12, 9, 9, 0]
    assert body["page"] == {"limit": 100, "offset": 0, "total": 4}
    top = body["data"][0]
    assert (top["scores"][0]["source"], top["scores"][0]["override_score"]) == (
        "recruiter_override",
        4,
    )


async def test_scores_of_an_older_criteria_version_are_returned_and_marked_stale(
    world: World,
) -> None:
    body = (await world.recruiter.get(f"/v1/roles/{world.role_id}/candidates")).json()

    by_stale = {row["id"]: row["stale"] for row in body["data"]}

    assert by_stale == {
        str(world.d): False,
        str(world.a): False,
        str(world.b): True,
        str(world.c): False,  # nothing scored, nothing stale: it only needs scoring
    }
    stale_row = next(row for row in body["data"] if row["id"] == str(world.b))
    assert [c["stale"] for c in stale_row["scores"]] == [True, True]


async def test_must_have_coverage_counts_scored_must_haves_of_the_live_criteria(
    world: World,
) -> None:
    body = (await world.recruiter.get(f"/v1/roles/{world.role_id}/candidates")).json()

    coverage = {
        row["id"]: (row["must_have_covered"], row["must_have_total"]) for row in body["data"]
    }

    assert coverage[str(world.a)] == (1, 1)
    assert coverage[str(world.c)] == (0, 1)


async def test_stage_filter_and_paging_use_the_same_count(world: World) -> None:
    await sql(
        world.engine,
        "UPDATE candidates SET stage = 'interview' WHERE id = :c RETURNING id",
        c=world.d,
    )
    base = f"/v1/roles/{world.role_id}/candidates"

    filtered = (await world.recruiter.get(base, params={"filter[stage]": "interview"})).json()
    page = (await world.recruiter.get(base, params={"limit": 2, "offset": 2})).json()
    past_the_end = (await world.recruiter.get(base, params={"offset": 10})).json()

    assert [row["id"] for row in filtered["data"]] == [str(world.d)]
    assert filtered["page"]["total"] == 1
    assert [row["id"] for row in page["data"]] == [str(world.b), str(world.c)]
    assert page["page"] == {"limit": 2, "offset": 2, "total": 4}
    assert (past_the_end["data"], past_the_end["page"]["total"]) == ([], 4)


async def test_sort_by_one_criterion_puts_candidates_without_that_score_last(
    world: World,
) -> None:
    response = await world.recruiter.get(
        f"/v1/roles/{world.role_id}/candidates", params={"sort": str(world.go)}
    )

    assert [row["id"] for row in response.json()["data"]] == [
        str(world.b),  # Go 3
        str(world.a),  # Go no evidence, 0
        str(world.d),  # no Go score, by total
        str(world.c),
    ]


async def test_recruiter_detail_has_quotes_notes_and_audit(world: World) -> None:
    response = await world.recruiter.get(f"/v1/candidates/{world.d}")
    audited = await world.recruiter.get(f"/v1/candidates/{world.a}")

    body = response.json()
    assert response.status_code == 200
    assert (body["stage"], body["processing_status"]) == ("new", "queued")
    assert body["scores"][0]["quote"] == "Built a payments service in Python."
    assert body["scores"][0]["override_note"] == "Referee confirmed the depth."
    assert [e["kind"] for e in audited.json()["audit"]] == ["stage_change"]


async def test_interviewer_detail_is_404_until_assigned_then_a_bare_view_until_they_submit(
    world: World,
) -> None:
    url = f"/v1/candidates/{world.a}"

    unassigned = await world.interviewer.get(url)
    await sql(
        world.engine,
        "INSERT INTO assignments(candidate_id, user_id) VALUES (:c, :u) RETURNING user_id",
        c=world.a,
        u=world.interviewer_id,
    )
    assigned = await world.interviewer.get(url)
    other = await world.interviewer.get(f"/v1/candidates/{world.b}")

    assert (unassigned.status_code, unassigned.json()["error"]["code"]) == (404, "not_found")
    assert assigned.status_code == 200
    assert set(assigned.json()) == {"id", "candidate_no", "role_id", "has_submitted"}
    assert other.status_code == 404


async def test_after_feedback_an_interviewer_sees_scores_without_quote_note_or_flag(
    world: World,
) -> None:
    await sql(
        world.engine,
        "INSERT INTO assignments(candidate_id, user_id) VALUES (:c, :u) RETURNING user_id",
        c=world.d,
        u=world.interviewer_id,
    )
    for criterion in (world.python, world.go):
        await sql(
            world.engine,
            "INSERT INTO feedback(candidate_id, interviewer_id, criterion_id, score, comment) "
            "VALUES (:c, :u, :k, 3, 'Solid.') RETURNING candidate_id",
            c=world.d,
            u=world.interviewer_id,
            k=criterion,
        )

    body = (await world.interviewer.get(f"/v1/candidates/{world.d}")).json()

    assert body["has_submitted"] is True
    python = body["scores"][0]
    assert (python["model_score"], python["override_score"]) == (1, 4)
    assert (python["quote"], python["flag_reason"], python["override_note"]) == (None, None, None)
    assert not {"audit", "stage"} & body.keys()
    assert "Built a payments service" not in str(body)


async def test_text_returns_both_texts_to_a_recruiter_and_is_refused_to_an_interviewer(
    world: World,
) -> None:
    await sql(
        world.engine,
        "INSERT INTO assignments(candidate_id, user_id) VALUES (:c, :u) RETURNING user_id",
        c=world.a,
        u=world.interviewer_id,
    )

    found = await world.recruiter.get(f"/v1/candidates/{world.a}/text")
    pending = await world.recruiter.get(f"/v1/candidates/{world.b}/text")
    refused = await world.interviewer.get(f"/v1/candidates/{world.a}/text")

    assert found.json() == {"raw_text": "Jane Doe. Built.", "anonymized_text": "Built."}
    assert pending.status_code == 404
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "forbidden")
