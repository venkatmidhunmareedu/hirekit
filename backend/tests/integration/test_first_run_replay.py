"""The first run of the real Worker, offline: `build_worker` wiring over Postgres and recordings.

Everything is real (extractor, anonymizer, prompts, parsers, verifier, loaders, repositories, the
Gateway in replay mode) except the recorded model replies, which are authored here and keyed
through the same `request_key` the Gateway uses (`tests.gateway.fakes.record`). Replay builds no
transport and needs no key, so no model call can happen; a missing recording fails the job.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.anonymizer import anonymize
from app.db.repositories import jobs, worker_writes
from app.extraction import ResumeExtractor
from app.gateway import GatewayRequest
from app.gateway.text import mint_anonymized, mint_prompt
from app.jobs.job_description import load_job_description
from app.prompts.criteria_prompt import CriteriaPromptBuilder
from app.prompts.kit_prompt import KitPromptBuilder
from app.prompts.scoring_prompt import ScoringPromptBuilder
from app.worker.loop import run_worker
from app.worker.wiring import build_worker
from tests.extraction.test_extractor import PDF, make_pdf
from tests.gateway.fakes import make_settings, record
from tests.integration.test_jobs_repository import row, seed_job, seed_role
from tests.integration.test_worker_end_to_end import enqueue
from tests.integration.test_worker_writes import count, seed_approved_role
from tests.worker.fakes import FakeClock

pytestmark = pytest.mark.integration

LINE = "Jane Roe jane.roe@example.com Built payments systems in Python for six years."
REAL_QUOTE = "Built payments systems in Python"
INVENTED_QUOTE = "Led a team of fifty engineers"
RAW_VALUES = ("Jane", "Roe", "jane.roe@example.com")
LEVELS = ["none", "basic", "solid", "strong", "expert"]


async def run(session: AsyncSession, recordings: Path) -> None:
    """Drain the queue with the real wiring; the first empty poll stops the loop."""

    @asynccontextmanager
    async def same_transaction() -> AsyncIterator[AsyncSession]:
        yield session

    handlers, close = build_worker(make_settings(recordings), same_transaction)
    clock = FakeClock()
    stop = asyncio.Event()
    clock.stop = stop
    try:
        await run_worker(
            sessions=same_transaction,
            jobs=jobs,
            writes=worker_writes,
            handlers=handlers,
            stop=stop,
            now=clock.now,
            sleep=clock.sleep,
            poll_seconds=1,
            lease_seconds=180,
        )
    finally:
        await close()


async def resume_job(session: AsyncSession, role: UUID) -> tuple[int, UUID]:
    job_id, candidate = await seed_job(session, role)
    await session.execute(
        text("INSERT INTO resume_files (candidate_id, media_type, content) VALUES (:c, :m, :b)"),
        {"c": candidate, "m": PDF, "b": make_pdf([LINE])},
    )
    return job_id, candidate


def scoring_request(system: str, anonymized: str) -> GatewayRequest:
    return GatewayRequest(
        purpose="scoring",
        role_id=None,
        prompt_version="scoring-v1",
        system=mint_prompt(system),
        input=mint_anonymized(anonymized),
        max_tokens=1500,
        schema_retry=0,
    )


async def test_a_process_resume_job_runs_from_recordings_with_the_real_wiring(
    session: AsyncSession, tmp_path: Path
) -> None:
    role, ids = await seed_approved_role(session)
    job_id, candidate = await resume_job(session, role)
    criteria = await worker_writes.read_criteria(session, role)
    anonymized = anonymize(ResumeExtractor().extract(make_pdf([LINE]), PDF)).text.value
    assert REAL_QUOTE in anonymized
    assert [v for v in RAW_VALUES if v in anonymized] == []
    request = scoring_request(ScoringPromptBuilder().build(criteria).value, anonymized)
    reply = {
        "scores": [
            {"criterion": 1, "value": 4, "quote": REAL_QUOTE},
            {"criterion": 2, "value": 3, "quote": INVENTED_QUOTE},
        ]
    }
    record(request, make_settings(tmp_path), json.dumps(reply))

    await run(session, tmp_path)

    assert (await row(session, job_id))[0] == "succeeded"
    status = await session.scalar(
        text("SELECT processing_status FROM candidates WHERE id = :c"), {"c": candidate}
    )
    assert status == "done"
    rows = (
        await session.execute(
            text(
                "SELECT criterion_id, status, model_score, quote FROM scores WHERE candidate_id=:c"
            ),
            {"c": candidate},
        )
    ).all()
    by_criterion = {r.criterion_id: r for r in rows}
    assert (by_criterion[ids[0]].status, by_criterion[ids[0]].quote) == ("scored", REAL_QUOTE)
    assert (by_criterion[ids[1]].status, by_criterion[ids[1]].quote) == ("no_evidence", None)
    stored_raw = await session.scalar(
        text("SELECT raw_text FROM resume_raw_texts WHERE candidate_id = :c"), {"c": candidate}
    )
    stored_anon = await session.scalar(
        text("SELECT anonymized_text FROM resume_texts WHERE candidate_id = :c"), {"c": candidate}
    )
    assert stored_raw is not None
    assert "Jane Roe" in stored_raw
    assert stored_anon == anonymized
    files = "SELECT count(*) FROM resume_files WHERE candidate_id = :c"
    assert await count(session, files, c=candidate) == 0


async def test_a_missing_recording_fails_the_job_and_never_reaches_a_model(
    session: AsyncSession, tmp_path: Path
) -> None:
    role, _ = await seed_approved_role(session)
    job_id, candidate = await resume_job(session, role)

    await run(session, tmp_path)  # an empty recordings dir

    assert (await row(session, job_id))[0] != "succeeded"
    assert (
        await count(session, "SELECT count(*) FROM scores WHERE candidate_id=:c", c=candidate) == 0
    )


async def test_propose_criteria_then_generate_kit_run_from_recordings(
    session: AsyncSession, tmp_path: Path
) -> None:
    settings = make_settings(tmp_path)
    role = await seed_role(session)
    description = await load_job_description(session, role)
    criteria_reply = {
        "criteria": [
            {
                "name": name,
                "kind": "must_have",
                "weight": 3,
                "levels": [{"level": n, "descriptor": d} for n, d in enumerate(LEVELS)],
            }
            for name in ("Python", "SQL")
        ]
    }
    record(
        GatewayRequest(
            "criteria", None, "criteria-v1", CriteriaPromptBuilder().build(), description, 1500, 0
        ),
        settings,
        json.dumps(criteria_reply),
    )
    propose = await enqueue(session, "propose_criteria", role, 1)

    await run(session, tmp_path)

    assert (await row(session, propose))[0] == "succeeded"
    # The recruiter approves; only then may the kit be generated.
    await session.execute(text("UPDATE roles SET status = 'approved' WHERE id = :r"), {"r": role})
    live = await worker_writes.read_criteria(session, role)
    assert len(live) == 2
    for criterion in live:
        reply = {
            "questions": [
                {
                    "question": f"Tell me about {criterion.name} {n}.",
                    "strong_answer": "s",
                    "weak_answer": "w",
                }
                for n in (1, 2)
            ]
        }
        record(
            GatewayRequest(
                "kit",
                None,
                "kit-v1",
                KitPromptBuilder().build(criterion),
                await load_job_description(session, role, criterion),
                1500,
                0,
            ),
            settings,
            json.dumps(reply),
        )
    kit = await enqueue(session, "generate_kit", role, 2)

    await run(session, tmp_path)

    assert (await row(session, kit))[0] == "succeeded"
    assert await count(session, "SELECT count(*) FROM questions WHERE role_id = :r", r=role) == 4
