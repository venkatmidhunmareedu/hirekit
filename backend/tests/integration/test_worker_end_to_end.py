"""The Worker end to end: `run_worker` and the real handlers over real rows on Postgres.

The repositories, the anonymizer, `load_anonymized` and the quote verifier are real; the
extractor, the prompts, the parsers, the job-description loader and the gateway are fakes, so
there is no network and no model call. Every test runs in one transaction that is rolled back.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.anonymizer import Anonymized, anonymize, load_anonymized
from app.db.repositories import jobs, worker_writes
from app.gateway import GatewayRequest, GatewayResponse
from app.gateway.text import AnonymizedText
from app.worker.errors import ExtractionError
from app.worker.handlers import build_handlers
from app.worker.handlers.kit import KitDeps
from app.worker.handlers.process_resume import ResumeDeps
from app.worker.handlers.propose_criteria import CriteriaDeps
from app.worker.handlers.scoring import ScoringDeps
from app.worker.loop import Handler, run_worker
from app.worker.outcome import EXTRACTION_FAILED, SOMETHING_WENT_WRONG
from app.worker.ports import ParsedScore, ProposedCriterion, ProposedQuestion
from app.worker.quotes import WhitespaceQuoteVerifier
from tests.integration.test_jobs_repository import row, seed_job, seed_role
from tests.integration.test_worker_writes import PDF_FILE, count, seed_approved_role
from tests.worker.fakes import (
    FakeClock,
    FakeCriteriaPrompt,
    FakeExtractor,
    FakeJobDescriptionLoader,
    FakeKitPrompt,
    FakeScoreParser,
    FakeScoringPrompt,
    FakeSessions,
    reply,
)

pytestmark = pytest.mark.integration

RESUME = (
    "Jane Roe\njane.roe@example.com\n+1 415 555 0132\n"
    "Built payments systems in Python for six years.\nLed a SQL migration."
)
RAW_VALUES = ("Jane", "Roe", "jane.roe@example.com", "415 555 0132")
REAL_QUOTE = "Built payments   systems in Python"  # extra spaces: only whitespace is normalized
INVENTED_QUOTE = "Led a team of fifty engineers"
LEVELS = ("none", "basic", "solid", "strong", "expert")


class RealAnonymizer:
    """The `Anonymizer` port over the real `app.anonymizer.anonymize`."""

    def anonymize(self, raw: str) -> Anonymized:
        return anonymize(raw)


@dataclass
class RecordingGateway:
    """Records every request; `on_call` runs inside the call, where a test can interfere."""

    requests: list[GatewayRequest] = field(default_factory=list)
    on_call: Callable[[], Awaitable[None]] | None = None

    async def complete(self, request: GatewayRequest) -> GatewayResponse:
        self.requests.append(request)
        if self.on_call is not None:
            await self.on_call()
        return reply("recorded")


@dataclass
class Rig:
    """`run_worker` wired to the real repositories over one session, with fake ports."""

    session: AsyncSession
    gateway: RecordingGateway
    extractor: FakeExtractor
    scoring_parser: FakeScoreParser
    criteria_prompt: FakeCriteriaPrompt
    kit_prompt: FakeKitPrompt
    descriptions: FakeJobDescriptionLoader
    handlers: dict[str, Handler]
    clock: FakeClock = field(default_factory=FakeClock)
    stop: asyncio.Event = field(default_factory=asyncio.Event)

    async def run(self, handlers: dict[str, Handler] | None = None) -> None:
        """Drain the queue: the first poll that finds nothing sets `stop`."""
        session = self.session

        @asynccontextmanager
        async def same_transaction() -> AsyncIterator[AsyncSession]:
            yield session

        self.stop.clear()
        self.clock.slept.clear()
        self.clock.stop = self.stop
        await run_worker(
            sessions=same_transaction,
            jobs=jobs,
            writes=worker_writes,
            handlers=self.handlers if handlers is None else handlers,
            stop=self.stop,
            now=self.clock.now,
            sleep=self.clock.sleep,
            poll_seconds=1,
            lease_seconds=180,
        )


def make_rig(session: AsyncSession, *, scores: list[list[ParsedScore]] | None = None) -> Rig:
    gateway = RecordingGateway()
    extractor = FakeExtractor(FakeSessions(), text=RESUME)
    parser = FakeScoreParser(results=[*(scores or [])])
    criteria_prompt = FakeCriteriaPrompt()
    kit_prompt = FakeKitPrompt()
    descriptions = FakeJobDescriptionLoader()
    handlers = build_handlers(
        ScoringDeps(
            gateway,
            worker_writes,
            jobs,
            load_anonymized,
            FakeScoringPrompt(),
            parser,
            WhitespaceQuoteVerifier(),
            "scoring-v1",
        ),
        ResumeDeps(extractor, RealAnonymizer(), worker_writes),
        CriteriaDeps(gateway, worker_writes, jobs, descriptions, criteria_prompt, "criteria-v1"),
        KitDeps(gateway, worker_writes, jobs, descriptions, kit_prompt, "kit-v1"),
    )
    return Rig(
        session, gateway, extractor, parser, criteria_prompt, kit_prompt, descriptions, handlers
    )


def both_criteria(ids: list[UUID]) -> list[ParsedScore]:
    """A quote that is in the text for the first criterion and an invented one for the second."""
    return [ParsedScore(ids[0], 4, REAL_QUOTE), ParsedScore(ids[1], 3, INVENTED_QUOTE)]


async def resume_job(session: AsyncSession, role: UUID) -> tuple[int, UUID]:
    """A queued process_resume job whose candidate has an uploaded file."""
    job_id, candidate = await seed_job(session, role)
    await session.execute(text(PDF_FILE), {"c": candidate})
    return job_id, candidate


async def candidate_state(session: AsyncSession, candidate: UUID) -> tuple[str, str | None, str]:
    state = (
        await session.execute(
            text(
                "SELECT processing_status, failure_reason, identity_name "
                "FROM candidates WHERE id = :c"
            ),
            {"c": candidate},
        )
    ).one()
    return state.processing_status, state.failure_reason, state.identity_name


async def enqueue(session: AsyncSession, job_type: str, role: UUID, version: int) -> int:
    """A job that targets a role (propose_criteria, generate_kit)."""
    job_id = await session.scalar(
        text("INSERT INTO jobs(type, role_id, criteria_version) VALUES (:t, :r, :v) RETURNING id"),
        {"t": job_type, "r": role, "v": version},
    )
    assert job_id is not None
    return int(job_id)


async def test_a_process_resume_job_takes_a_candidate_from_queued_to_done(
    session: AsyncSession,
) -> None:
    role, ids = await seed_approved_role(session)
    job_id, candidate = await resume_job(session, role)
    before = await candidate_state(session, candidate)
    rig = make_rig(session, scores=[both_criteria(ids)])

    await rig.run()

    assert before[0] == "queued"
    assert (await candidate_state(session, candidate))[:2] == ("done", None)
    status, attempt, token, error = await row(session, job_id)
    assert (status, attempt, token, error) == ("succeeded", 1, None, None)
    assert len(rig.gateway.requests) == 1


async def test_process_resume_stores_raw_and_anonymized_text_apart_and_deletes_the_file(
    session: AsyncSession,
) -> None:
    role, ids = await seed_approved_role(session)
    _, candidate = await resume_job(session, role)
    rig = make_rig(session, scores=[both_criteria(ids)])

    await rig.run()

    raw = await session.scalar(
        text("SELECT raw_text FROM resume_raw_texts WHERE candidate_id = :c"), {"c": candidate}
    )
    anonymized = await session.scalar(
        text("SELECT anonymized_text FROM resume_texts WHERE candidate_id = :c"), {"c": candidate}
    )
    assert raw == RESUME
    assert anonymized is not None
    assert [value for value in RAW_VALUES if value in anonymized] == []
    assert "Built payments systems in Python" in anonymized
    assert (
        await count(
            session, "SELECT count(*) FROM resume_files WHERE candidate_id = :c", c=candidate
        )
        == 0
    )
    assert (await candidate_state(session, candidate))[2] == "Jane Roe"


async def test_extraction_failure_keeps_the_file_and_fails_with_a_plain_reason(
    session: AsyncSession,
) -> None:
    role, _ = await seed_approved_role(session)
    job_id, candidate = await resume_job(session, role)
    rig = make_rig(session)
    rig.extractor.error = ExtractionError("scanned image")

    await rig.run()

    status, _, token, error = await row(session, job_id)
    assert (status, token, error) == ("failed", None, "extraction_failed")
    assert (await candidate_state(session, candidate))[:2] == ("failed", EXTRACTION_FAILED)
    assert (
        await count(
            session, "SELECT count(*) FROM resume_files WHERE candidate_id = :c", c=candidate
        )
        == 1
    )
    assert (
        await count(
            session, "SELECT count(*) FROM resume_texts WHERE candidate_id = :c", c=candidate
        )
        == 0
    )
    assert rig.gateway.requests == []


async def test_scores_exist_with_verified_quotes_and_an_invented_quote_is_no_evidence(
    session: AsyncSession,
) -> None:
    role, ids = await seed_approved_role(session)
    _, candidate = await resume_job(session, role)
    rig = make_rig(session, scores=[both_criteria(ids)])

    await rig.run()

    rows = (
        await session.execute(
            text(
                "SELECT criterion_id, status, model_score, quote, flag_reason FROM scores "
                "WHERE candidate_id = :c"
            ),
            {"c": candidate},
        )
    ).all()
    by_criterion = {r.criterion_id: r for r in rows}
    assert len(rows) == 2
    assert (by_criterion[ids[0]].status, by_criterion[ids[0]].model_score) == ("scored", 4)
    assert by_criterion[ids[0]].quote == REAL_QUOTE
    assert (by_criterion[ids[1]].status, by_criterion[ids[1]].model_score) == ("no_evidence", 0)
    assert by_criterion[ids[1]].quote is None
    assert by_criterion[ids[1]].flag_reason is not None


async def test_the_gateway_only_ever_receives_anonymized_text_for_scoring(
    session: AsyncSession,
) -> None:
    role, ids = await seed_approved_role(session)
    await resume_job(session, role)
    rig = make_rig(session, scores=[both_criteria(ids)])

    await rig.run()

    [request] = rig.gateway.requests
    assert request.purpose == "scoring"
    assert isinstance(request.input, AnonymizedText)
    sent = request.input.value + request.system.value
    assert [value for value in RAW_VALUES if value in sent] == []
    assert "[NAME]" in request.input.value


async def test_propose_criteria_then_generate_kit_on_an_approved_role_write_the_rows(
    session: AsyncSession,
) -> None:
    role = await seed_role(session)
    rig = make_rig(session)
    rig.descriptions.descriptions[role] = "Senior payments engineer."
    rig.criteria_prompt.results = [
        [
            ProposedCriterion("Python", "must_have", Decimal(3), LEVELS),
            ProposedCriterion("SQL", "nice_to_have", Decimal(1), LEVELS),
        ]
    ]
    propose = await enqueue(session, "propose_criteria", role, 1)

    await rig.run()

    assert (await row(session, propose))[0] == "succeeded"
    assert await count(session, "SELECT count(*) FROM criteria WHERE role_id = :r", r=role) == 2
    version = await session.scalar(
        text("SELECT criteria_version FROM roles WHERE id = :r"), {"r": role}
    )
    assert version == 2

    # The recruiter approves the proposal; only then may the kit be generated.
    await session.execute(text("UPDATE roles SET status = 'approved' WHERE id = :r"), {"r": role})
    rig.kit_prompt.results = [
        [ProposedQuestion("Describe a Python service you built.", "strong", "weak")],
        [ProposedQuestion("How do you tune a slow query?", "strong", "weak")],
    ]
    kit = await enqueue(session, "generate_kit", role, 2)

    await rig.run()

    assert (await row(session, kit))[0] == "succeeded"
    kit_version = await session.scalar(
        text("SELECT criteria_version FROM interview_kits WHERE role_id = :r"), {"r": role}
    )
    assert kit_version == 2
    assert await count(session, "SELECT count(*) FROM questions WHERE role_id = :r", r=role) == 2
    assert [r.purpose for r in rig.gateway.requests] == ["criteria", "kit", "kit"]


async def test_a_cancelled_job_writes_nothing(session: AsyncSession) -> None:
    role, ids = await seed_approved_role(session)
    job_id, candidate = await resume_job(session, role)
    rig = make_rig(session, scores=[both_criteria(ids)])

    async def recruiter_cancels() -> None:
        await session.execute(
            text(
                "UPDATE jobs SET status = 'cancelled', lease_token = NULL, "
                "lease_expires_at = NULL WHERE id = :id"
            ),
            {"id": job_id},
        )

    rig.gateway.on_call = recruiter_cancels

    await rig.run()

    assert (await row(session, job_id))[0] == "cancelled"
    assert (
        await count(session, "SELECT count(*) FROM scores WHERE candidate_id = :c", c=candidate)
        == 0
    )
    assert (await candidate_state(session, candidate))[0] == "scoring"  # the Api's cancel sets it


async def test_an_unknown_job_type_fails_as_no_handler_and_the_candidate_is_failed(
    session: AsyncSession,
) -> None:
    role, _ = await seed_approved_role(session)
    job_id, candidate = await resume_job(session, role)
    rig = make_rig(session)
    handlers = {k: v for k, v in rig.handlers.items() if k != "process_resume"}

    await rig.run(handlers)

    status, _, token, error = await row(session, job_id)
    assert (status, token, error) == ("failed", None, "no_handler")
    assert (await candidate_state(session, candidate))[:2] == ("failed", SOMETHING_WENT_WRONG)
    assert rig.gateway.requests == []


async def test_graceful_shutdown_stops_between_jobs(session: AsyncSession) -> None:
    role, ids = await seed_approved_role(session)
    first, _ = await resume_job(session, role)
    second, _ = await resume_job(session, role)
    rig = make_rig(session, scores=[both_criteria(ids), both_criteria(ids)])

    async def sigterm() -> None:
        rig.stop.set()

    rig.gateway.on_call = sigterm

    await rig.run()

    assert (await row(session, first))[0] == "succeeded"  # the job in hand was finished
    assert (await row(session, second))[0] == "queued"  # and no new one was claimed
    assert rig.clock.slept == []


async def test_a_batch_of_100_resumes_runs_end_to_end_with_fake_ports_and_replay(
    session: AsyncSession,
) -> None:
    role, ids = await seed_approved_role(session)
    for _ in range(100):
        await resume_job(session, role)
    rig = make_rig(session, scores=[both_criteria(ids) for _ in range(100)])

    await rig.run()

    done = "SELECT count(*) FROM jobs WHERE role_id = :r AND status = 'succeeded'"
    assert await count(session, done, r=role) == 100
    assert (
        await count(session, "SELECT count(*) FROM candidates WHERE processing_status = 'done'")
        == 100
    )
    assert await count(session, "SELECT count(*) FROM scores") == 200
    assert len(rig.gateway.requests) == 100
