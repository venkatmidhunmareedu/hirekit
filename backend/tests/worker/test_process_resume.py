"""`process_resume`: extract, anonymize, store the texts apart, score; statuses and failures."""

import asyncio
from collections import Counter
from dataclasses import dataclass

from app.anonymizer.pipeline import InputTooLargeError
from app.anonymizer.verify import AnonymizationLeakError
from app.gateway.errors import RateLimitedError
from app.gateway.text import AnonymizedText
from app.worker.errors import ExtractionError
from app.worker.handlers import build_handlers
from app.worker.handlers.process_resume import NO_FILE_CODE, ResumeDeps, make_process_resume
from app.worker.loop import run_worker
from app.worker.outcome import (
    ANONYMIZATION_LEAK,
    EXTRACTION_FAILED,
    INPUT_TOO_LARGE,
    NO_FILE,
    Failed,
    Succeeded,
)
from tests.worker.fakes import FakeAnonymizer, FakeExtractor, FakeResumeWrites, reply
from tests.worker.test_scoring import Rig, rig, scores


@dataclass
class ResumeRig:
    base: Rig
    extractor: FakeExtractor
    anonymizer: FakeAnonymizer
    writes: FakeResumeWrites
    deps: ResumeDeps


def resume_rig() -> ResumeRig:
    base = rig()
    extractor, anonymizer = FakeExtractor(base.sessions), FakeAnonymizer(base.sessions)
    writes = FakeResumeWrites(base.jobs)
    return ResumeRig(base, extractor, anonymizer, writes, ResumeDeps(extractor, anonymizer, writes))


async def run(r: ResumeRig) -> object:
    return await make_process_resume(r.deps, r.base.deps)(r.base.ctx)


def ready_to_score(r: ResumeRig) -> None:
    r.base.gateway.replies = [reply()]
    r.base.parser.results = [scores(r.base, None, None)]


async def test_process_resume_walks_the_statuses_parsing_anonymizing_scoring_done() -> None:
    r = resume_rig()
    ready_to_score(r)
    assert await run(r) == Succeeded()
    assert [c[2] for c in r.base.jobs.statuses()] == ["parsing", "anonymizing", "scoring", "done"]
    assert ("succeed", 1) in r.base.jobs.calls


async def test_process_resume_stores_raw_and_anonymized_text_apart_and_deletes_the_file() -> None:
    r = resume_rig()
    ready_to_score(r)
    await run(r)
    assert r.writes.stored == [
        {
            "raw_text": "Jane Doe built billing in Go.",
            "anonymized": "[NAME] built billing in Go.",
            "anonymizer_version": 7,
            "identity_name": "Jane Doe",
        }
    ]
    assert r.writes.file is None  # store_texts deletes the file in the same transaction


async def test_process_resume_passes_only_anonymized_text_to_the_gateway() -> None:
    r = resume_rig()
    ready_to_score(r)
    await run(r)
    request = r.base.gateway.requests[0]
    assert isinstance(request.input, AnonymizedText)
    assert "Jane" not in request.input.value
    assert "Jane" not in request.input.value
    assert r.anonymizer.seen == ["Jane Doe built billing in Go."]  # only the raw text went in


async def test_process_resume_skips_extraction_when_the_text_already_exists() -> None:
    r = resume_rig()
    r.writes.text_stored = True
    ready_to_score(r)
    assert await run(r) == Succeeded()
    assert r.extractor.calls == []
    assert r.anonymizer.seen == []
    assert ("read_file",) not in r.base.jobs.calls
    assert r.writes.stored == []
    assert [c[2] for c in r.base.jobs.statuses()] == ["parsing", "scoring", "done"]


async def test_extraction_failure_keeps_the_file_and_fails_with_a_plain_reason() -> None:
    r = resume_rig()
    r.extractor.error = ExtractionError("scanned")
    assert await run(r) == Failed("extraction_failed", EXTRACTION_FAILED)
    assert r.writes.file is not None
    assert r.writes.stored == []
    assert r.anonymizer.seen == []
    assert r.base.gateway.requests == []


async def test_an_anonymization_leak_fails_permanently_and_nothing_is_stored_or_sent() -> None:
    r = resume_rig()
    r.anonymizer.error = AnonymizationLeakError(Counter(email=1))
    assert await run(r) == Failed("anonymization_leak", ANONYMIZATION_LEAK)
    assert r.writes.stored == []
    assert r.writes.file is not None
    assert r.base.gateway.requests == []


async def test_a_resume_over_the_size_limit_fails_permanently_with_a_plain_reason() -> None:
    r = resume_rig()
    r.anonymizer.error = InputTooLargeError()
    assert await run(r) == Failed("input_too_large", INPUT_TOO_LARGE)
    assert r.writes.stored == []


async def test_a_missing_file_with_no_stored_text_fails_and_needs_a_new_upload() -> None:
    r = resume_rig()
    r.writes.file = None
    assert await run(r) == Failed(NO_FILE_CODE, NO_FILE)
    assert r.extractor.calls == []


async def test_no_transaction_is_open_during_extraction_anonymization_or_the_gateway_call() -> None:
    r = resume_rig()
    ready_to_score(r)
    await run(r)
    assert r.extractor.open_during_call == [0]
    assert r.anonymizer.open_during_call == [0]
    assert r.base.gateway.open_during_call == [0]


async def test_the_lease_is_renewed_before_extraction_and_before_anonymization() -> None:
    r = resume_rig()
    ready_to_score(r)
    await run(r)
    names = [c[0] for c in r.base.jobs.calls]
    assert names.count("renew") == 3  # extraction, anonymization, the scoring call


async def test_every_write_is_fenced_without_the_exclusive_role_lock() -> None:
    r = resume_rig()
    ready_to_score(r)
    await run(r)
    assert r.base.jobs.fence_exclusive
    assert not any(r.base.jobs.fence_exclusive)


async def test_retry_puts_the_candidate_back_to_queued() -> None:
    r = resume_rig()
    r.base.gateway.replies = [RateLimitedError("slow down")]
    r.base.jobs.queue = [r.base.ctx.job]
    stop = asyncio.Event()
    clock = r.base.jobs.clock
    clock.stop, clock.stop_after_sleeps = stop, 1
    await run_worker(
        sessions=r.base.sessions.begin,
        jobs=r.base.jobs,
        writes=r.base.jobs,
        handlers=build_handlers(r.base.deps, r.deps),
        stop=stop,
        now=clock.now,
        sleep=clock.sleep,
        poll_seconds=1,
        lease_seconds=180,
    )
    assert [c[0] for c in r.base.jobs.writes()] == ["reschedule"]
    assert r.base.jobs.statuses()[-1][2] == "queued"
