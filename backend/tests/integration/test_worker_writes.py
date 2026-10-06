"""The worker writes against Postgres: statuses, texts, scores, criteria and kits (Q5 to Q11)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import jobs, worker_writes
from app.db.repositories.worker_writes import NewQuestion, ScoreRow
from app.gateway.text import mint_anonymized
from app.worker.context import JobContext
from app.worker.errors import LeaseLostError
from app.worker.ports import ProposedCriterion
from tests.integration.test_jobs_repository import seed_job, seed_role

pytestmark = pytest.mark.integration

LEVELS = ("none", "basic", "solid", "strong", "expert")
PROPOSED = [
    ProposedCriterion("Python", "must_have", Decimal(3), LEVELS),
    ProposedCriterion("SQL", "nice_to_have", Decimal(1), LEVELS),
]
PDF_FILE = (
    "INSERT INTO resume_files (candidate_id, media_type, content) "
    "VALUES (:c, 'application/pdf', '\\x25504446')"
)


async def count(session: AsyncSession, sql: str, **params: object) -> int:
    return int(await session.scalar(text(sql), params) or 0)


async def seed_approved_role(session: AsyncSession, *, version: int = 1) -> tuple[UUID, list[UUID]]:
    """An Approved role at `version` with two live criteria; returns (role id, criterion ids)."""
    role = await seed_role(session)
    await session.execute(
        text("UPDATE roles SET status = 'approved', criteria_version = :v WHERE id = :id"),
        {"id": role, "v": version},
    )
    ids = []
    for position, name in enumerate(("Python", "SQL"), start=1):
        criterion = await session.scalar(
            text(
                "INSERT INTO criteria (role_id, name, kind, weight, position) "
                "VALUES (:role, :name, 'must_have', 1, :position) RETURNING id"
            ),
            {"role": role, "name": name, "position": position},
        )
        assert criterion is not None
        ids.append(criterion)
    return role, ids


async def candidate_of(session: AsyncSession, role: UUID) -> UUID:
    _, candidate = await seed_job(session, role)
    return candidate


def scored(criterion: UUID, value: int = 3) -> ScoreRow:
    return ScoreRow(criterion, "scored", value, "built payments", None)


def failed(criterion: UUID) -> ScoreRow:
    return ScoreRow(criterion, "failed", None, None, None)


async def score_rows(session: AsyncSession, candidate: UUID) -> dict[UUID, tuple[str, int | None]]:
    rows = await session.execute(
        text("SELECT criterion_id, status, model_score FROM scores WHERE candidate_id = :c"),
        {"c": candidate},
    )
    return {r.criterion_id: (r.status, r.model_score) for r in rows}


async def write(
    session: AsyncSession, role: UUID, candidate: UUID, rows: list[ScoreRow], version: int = 1
) -> bool:
    return await worker_writes.write_scores(
        session, role_id=role, criteria_version=version, candidate_id=candidate, scores=rows
    )


async def test_a_status_update_on_the_reclaim_path_keeps_the_identity_name(
    session: AsyncSession,
) -> None:
    role = await seed_role(session)
    expired = timedelta(seconds=-1)
    _, candidate = await seed_job(session, role, attempt=3, running_lease_in=expired)

    assert await jobs.claim(session, lease_seconds=180) is None  # exhausted: set_status failed

    state = (
        await session.execute(
            text("SELECT processing_status, identity_name FROM candidates WHERE id = :id"),
            {"id": candidate},
        )
    ).one()
    assert tuple(state) == ("failed", "Jane")
    await worker_writes.set_status(session, candidate, "queued")
    name = await session.scalar(
        text("SELECT identity_name FROM candidates WHERE id = :id"), {"id": candidate}
    )
    assert name == "Jane"


async def test_process_resume_stores_raw_and_anonymized_text_apart_and_deletes_the_file(
    session: AsyncSession,
) -> None:
    role = await seed_role(session)
    candidate = await candidate_of(session, role)
    await session.execute(text(PDF_FILE), {"c": candidate})

    await worker_writes.store_texts(
        session,
        candidate,
        raw_text="Jane Roe built payments.",
        anonymized=mint_anonymized("[NAME] built payments."),
        anonymizer_version=1,
        identity_name="Jane Roe",
        status="scoring",
    )

    raw = await session.scalar(
        text("SELECT raw_text FROM resume_raw_texts WHERE candidate_id = :c"), {"c": candidate}
    )
    anonymized = await session.scalar(
        text("SELECT anonymized_text FROM resume_texts WHERE candidate_id = :c"), {"c": candidate}
    )
    assert (raw, anonymized) == ("Jane Roe built payments.", "[NAME] built payments.")
    assert await worker_writes.read_file(session, candidate) is None
    assert await worker_writes.text_exists(session, candidate)
    row = (
        await session.execute(
            text("SELECT processing_status, identity_name FROM candidates WHERE id = :c"),
            {"c": candidate},
        )
    ).one()
    assert tuple(row) == ("scoring", "Jane Roe")


async def test_extraction_failure_keeps_the_file_and_fails_with_a_plain_reason(
    session: AsyncSession,
) -> None:
    role = await seed_role(session)
    candidate = await candidate_of(session, role)
    await session.execute(text(PDF_FILE), {"c": candidate})

    await worker_writes.set_status(session, candidate, "failed", "No text could be read")

    stored = await worker_writes.read_file(session, candidate)
    assert stored is not None
    assert (stored.media_type, stored.content) == ("application/pdf", b"%PDF")
    reason = "SELECT failure_reason FROM candidates WHERE id = :c"
    assert await session.scalar(text(reason), {"c": candidate}) == "No text could be read"
    await worker_writes.set_status(session, candidate, "queued")  # a retry clears the reason
    assert await session.scalar(text(reason), {"c": candidate}) is None


async def test_read_criteria_returns_live_criteria_in_order_with_their_rubric(
    session: AsyncSession,
) -> None:
    role, ids = await seed_approved_role(session)
    await session.execute(
        text("UPDATE criteria SET retired_at = now() WHERE id = :id"), {"id": ids[1]}
    )
    await session.execute(
        text("INSERT INTO rubric_levels (criterion_id, level, descriptor) VALUES (:c, 2, 'ok')"),
        {"c": ids[0]},
    )

    specs = await worker_writes.read_criteria(session, role)

    assert [(s.id, s.name, s.position) for s in specs] == [(ids[0], "Python", 1)]
    assert specs[0].rubric == ((2, "ok"),)


async def test_upsert_never_overwrites_an_override(session: AsyncSession) -> None:
    role, ids = await seed_approved_role(session)
    candidate = await candidate_of(session, role)
    user = await session.scalar(
        text(
            "INSERT INTO users (name, email, password_hash, role) "
            "VALUES ('A', 'a@b.c', 'x', 'recruiter') RETURNING id"
        )
    )
    await write(session, role, candidate, [failed(ids[0])])
    await session.execute(
        text(
            "UPDATE scores SET override_score = 4, override_note = 'Recruiter judged it strong', "
            "overridden_by = :u WHERE candidate_id = :c"
        ),
        {"u": user, "c": candidate},
    )

    await write(session, role, candidate, [scored(ids[0])])

    row = (
        await session.execute(
            text(
                "SELECT status, override_score, overridden_by FROM scores WHERE candidate_id = :c"
            ),
            {"c": candidate},
        )
    ).one()
    assert tuple(row) == ("scored", 4, user)


async def test_same_version_rescore_rewrites_only_failed_rows(session: AsyncSession) -> None:
    role, ids = await seed_approved_role(session)
    candidate = await candidate_of(session, role)
    await write(session, role, candidate, [scored(ids[0], 3), failed(ids[1])])

    await write(session, role, candidate, [scored(ids[0], 1), scored(ids[1], 2)])

    assert await score_rows(session, candidate) == {
        ids[0]: ("scored", 3),  # a scored row is never rewritten at the same version
        ids[1]: ("scored", 2),
    }


async def test_a_failed_criterion_can_be_rescored_without_touching_the_others(
    session: AsyncSession,
) -> None:
    role, ids = await seed_approved_role(session)
    candidate = await candidate_of(session, role)
    await write(session, role, candidate, [scored(ids[0], 4), failed(ids[1])])

    await write(session, role, candidate, [scored(ids[1], 2)])

    assert await score_rows(session, candidate) == {ids[0]: ("scored", 4), ids[1]: ("scored", 2)}


async def test_scores_are_discarded_when_the_criteria_changed_after_enqueue(
    session: AsyncSession,
) -> None:
    role, ids = await seed_approved_role(session)
    candidate = await candidate_of(session, role)
    await session.execute(
        text("UPDATE roles SET criteria_version = 2 WHERE id = :id"), {"id": role}
    )

    assert await write(session, role, candidate, [scored(ids[0])]) is False
    assert await score_rows(session, candidate) == {}


async def test_scores_are_discarded_when_the_role_was_reapproved_at_a_new_version(
    session: AsyncSession,
) -> None:
    """The ABA case: Approved at 1, edited and re-approved at 2; the job's version 1 is dead."""
    role, ids = await seed_approved_role(session, version=2)
    candidate = await candidate_of(session, role)

    assert not await write(session, role, candidate, [scored(ids[0])], version=1)
    await session.execute(text("UPDATE roles SET status = 'draft' WHERE id = :id"), {"id": role})
    assert not await write(session, role, candidate, [scored(ids[0])], version=2)
    assert await score_rows(session, candidate) == {}


async def test_a_stale_process_resume_with_no_score_rows_reads_as_needing_scoring(
    session: AsyncSession,
) -> None:
    role, _ = await seed_approved_role(session, version=2)
    candidate = await candidate_of(session, role)

    await worker_writes.set_status(session, candidate, "done")  # what a Stale outcome writes

    status = await session.scalar(
        text("SELECT processing_status FROM candidates WHERE id = :c"), {"c": candidate}
    )
    current = await count(
        session,
        "SELECT count(*) FROM scores s JOIN roles r ON r.criteria_version = s.criteria_version "
        "WHERE s.candidate_id = :c AND r.id = :r",
        c=candidate,
        r=role,
    )
    assert (status, current) == ("done", 0)


async def test_propose_criteria_writes_criteria_and_rubric_and_bumps_the_version(
    session: AsyncSession,
) -> None:
    role = await seed_role(session)

    version = await worker_writes.insert_criteria(
        session, role_id=role, criteria_version=1, proposed=PROPOSED
    )

    assert version == 2
    specs = await worker_writes.read_criteria(session, role)
    assert [(s.name, s.position, [lv for lv, _ in s.rubric]) for s in specs] == [
        ("Python", 1, [0, 1, 2, 3, 4]),
        ("SQL", 2, [0, 1, 2, 3, 4]),
    ]
    assert specs[0].rubric[4] == (4, "expert")
    state = await worker_writes.read_role(session, role)
    assert state is not None
    assert (state.status, state.criteria_version) == ("draft", 2)


async def test_propose_criteria_on_a_role_that_already_has_criteria_is_stale_and_inserts_nothing(
    session: AsyncSession,
) -> None:
    role, ids = await seed_approved_role(session)
    await session.execute(text("UPDATE roles SET status = 'draft' WHERE id = :id"), {"id": role})

    inserted = await worker_writes.insert_criteria(
        session, role_id=role, criteria_version=1, proposed=PROPOSED
    )

    assert inserted is None
    assert [s.id for s in await worker_writes.read_criteria(session, role)] == ids
    state = await worker_writes.read_role(session, role)
    assert state is not None
    assert state.criteria_version == 1


async def test_propose_criteria_after_cancel_writes_nothing(session: AsyncSession) -> None:
    """AC-US-00-001-4: the context's fence refuses before any write reaches the database."""
    role = await seed_role(session)
    job_id, _ = await seed_job(session, role)
    job = await jobs.claim(session, lease_seconds=180)
    assert job is not None
    await session.execute(
        text(
            "UPDATE jobs SET status = 'cancelled', lease_token = NULL, lease_expires_at = NULL "
            "WHERE id = :id"
        ),
        {"id": job_id},
    )

    @asynccontextmanager
    async def same_transaction() -> AsyncIterator[AsyncSession]:
        yield session

    with pytest.raises(LeaseLostError):
        async with JobContext(job, same_transaction, jobs, 180).fenced() as fenced:
            await worker_writes.insert_criteria(
                fenced, role_id=role, criteria_version=1, proposed=PROPOSED
            )

    assert await worker_writes.read_criteria(session, role) == []


async def seed_kit(session: AsyncSession, role: UUID, ids: list[UUID]) -> list[UUID]:
    await worker_writes.replace_kit(
        session,
        role_id=role,
        criteria_version=1,
        questions=[
            NewQuestion(ids[0], 1, "Old one?", "strong", "weak"),
            NewQuestion(ids[0], 2, "Old two?", "strong", "weak"),
        ],
    )
    rows = await session.execute(
        text("SELECT id FROM questions WHERE role_id = :r ORDER BY position"), {"r": role}
    )
    return [r.id for r in rows]


async def test_generate_kit_replaces_questions_and_records_the_criteria_version(
    session: AsyncSession,
) -> None:
    role, ids = await seed_approved_role(session)
    await seed_kit(session, role, ids)
    await session.execute(
        text("UPDATE roles SET criteria_version = 2 WHERE id = :id"), {"id": role}
    )

    written = await worker_writes.replace_kit(
        session,
        role_id=role,
        criteria_version=2,
        questions=[NewQuestion(ids[1], 1, "New?", "strong", "weak")],
    )

    assert written
    rows = await session.execute(
        text("SELECT criterion_id, question_text FROM questions WHERE role_id = :r"), {"r": role}
    )
    assert [tuple(r) for r in rows] == [(ids[1], "New?")]
    kit = await count(
        session, "SELECT criteria_version FROM interview_kits WHERE role_id = :r", r=role
    )
    assert kit == 2


async def test_generate_kit_for_a_changed_role_writes_nothing(session: AsyncSession) -> None:
    role, ids = await seed_approved_role(session, version=2)

    written = await worker_writes.replace_kit(
        session,
        role_id=role,
        criteria_version=1,
        questions=[NewQuestion(ids[0], 1, "Q?", "strong", "weak")],
    )

    assert not written
    assert (
        await count(session, "SELECT count(*) FROM interview_kits WHERE role_id = :r", r=role) == 0
    )


async def test_regenerate_question_replaces_one_question_and_keeps_its_position(
    session: AsyncSession,
) -> None:
    role, ids = await seed_approved_role(session)
    first, second = await seed_kit(session, role, ids)

    written = await worker_writes.replace_question(
        session,
        role_id=role,
        criteria_version=1,
        question_id=second,
        question_text="Fresh?",
        strong_answer="s",
        weak_answer="w",
    )

    assert written
    rows = await session.execute(
        text("SELECT id, question_text, position FROM questions WHERE role_id = :r ORDER BY 3"),
        {"r": role},
    )
    assert [tuple(r) for r in rows] == [(first, "Old one?", 1), (second, "Fresh?", 2)]
    missing = await worker_writes.replace_question(
        session,
        role_id=role,
        criteria_version=1,
        question_id=uuid4(),
        question_text="x",
        strong_answer="s",
        weak_answer="w",
    )
    assert not missing


async def test_kit_transaction_cancels_open_regenerate_jobs_before_deleting_questions(
    session: AsyncSession,
) -> None:
    role, ids = await seed_approved_role(session)
    first, _ = await seed_kit(session, role, ids)
    insert = (
        "INSERT INTO jobs(type, role_id, question_id, criteria_version, status, attempt, "
        "lease_token, lease_expires_at) VALUES (:type, :r, :q, 1, 'running', 1, :t, "
        "now() + interval '3 minutes') RETURNING id"
    )
    regenerate = await session.scalar(
        text(insert), {"type": "regenerate_question", "r": role, "q": first, "t": uuid4()}
    )
    kit_job = await session.scalar(
        text(insert.replace(":q", "NULL")),
        {"type": "generate_kit", "r": role, "t": uuid4()},
    )

    await worker_writes.replace_kit(
        session,
        role_id=role,
        criteria_version=1,
        questions=[NewQuestion(ids[0], 1, "Q?", "s", "w")],
    )

    # The cascade removed the cancelled job with its question; the kit's own job is untouched.
    assert await count(session, "SELECT count(*) FROM jobs WHERE id = :i", i=regenerate) == 0
    assert await session.scalar(text("SELECT status FROM jobs WHERE id = :i"), {"i": kit_job}) == (
        "running"
    )


async def test_every_write_statement_is_allowed_to_the_worker_role(session: AsyncSession) -> None:
    """Migration 2 grants: every Q5 to Q11 statement runs as `hirekit_worker`, column grants too."""
    role, ids = await seed_approved_role(session)
    candidate = await candidate_of(session, role)
    draft = await seed_role(session)
    await session.execute(text(PDF_FILE), {"c": candidate})
    await session.execute(text("SET LOCAL ROLE hirekit_worker"))

    assert await worker_writes.read_file(session, candidate) is not None
    assert not await worker_writes.text_exists(session, candidate)
    await worker_writes.set_status(session, candidate, "parsing")
    await worker_writes.store_texts(
        session,
        candidate,
        raw_text="raw",
        anonymized=mint_anonymized("anon"),
        anonymizer_version=1,
        identity_name="Jane",
        status="scoring",
    )
    assert await write(session, role, candidate, [failed(ids[0])])
    assert await write(session, role, candidate, [scored(ids[0])])
    inserted = await worker_writes.insert_criteria(
        session, role_id=draft, criteria_version=1, proposed=PROPOSED
    )
    assert inserted == 2
    assert await worker_writes.replace_kit(
        session,
        role_id=role,
        criteria_version=1,
        questions=[NewQuestion(ids[0], 1, "Q?", "s", "w")],
    )
    question = await session.scalar(
        text("SELECT id FROM questions WHERE role_id = :r"), {"r": role}
    )
    assert await worker_writes.replace_question(
        session,
        role_id=role,
        criteria_version=1,
        question_id=question,
        question_text="Q2?",
        strong_answer="s",
        weak_answer="w",
    )
    assert len(await worker_writes.read_criteria(session, role)) == 2
