"""`rescore`: the scoring step for one candidate, leaving `processing_status` alone."""

import asyncio

from app.gateway.errors import ProviderRejectedError
from app.worker.handlers import build_handlers
from app.worker.handlers.process_resume import ResumeDeps
from app.worker.handlers.rescore import make_rescore
from app.worker.loop import run_worker
from app.worker.outcome import Stale, Succeeded
from tests.worker.fakes import (
    FakeAnonymizer,
    FakeExtractor,
    FakeResumeWrites,
    make_criteria_deps,
    make_job,
    make_kit_deps,
    reply,
)
from tests.worker.test_scoring import rig, scores


async def test_rescore_scores_the_candidate_and_succeeds_without_touching_the_status() -> None:
    r = rig()
    r.gateway.replies = [reply()]
    r.parser.results = [scores(r, None, None)]
    assert await make_rescore(r.deps)(r.ctx) == Succeeded()
    assert [w.status for w in r.writes.written] == ["no_evidence", "no_evidence"]
    assert ("succeed", 1) in r.jobs.calls
    assert r.jobs.statuses() == []


async def test_a_stale_rescore_ends_the_job_and_leaves_the_candidate_as_it_was() -> None:
    r = rig()
    r.writes.accept_scores = False
    r.gateway.replies = [reply()]
    r.parser.results = [scores(r, None, None)]
    assert await make_rescore(r.deps)(r.ctx) == Stale()
    assert ("mark_stale", 1) in r.jobs.calls
    assert r.jobs.statuses() == []


async def test_a_failed_rescore_leaves_the_candidate_done() -> None:
    r = rig()
    job = make_job(1, job_type="rescore")
    r.jobs.queue = [job]
    r.gateway.replies = [ProviderRejectedError("rejected")]
    resume = ResumeDeps(
        FakeExtractor(r.sessions), FakeAnonymizer(r.sessions), FakeResumeWrites(r.jobs)
    )
    stop = asyncio.Event()
    r.jobs.clock.stop, r.jobs.clock.stop_after_sleeps = stop, 1
    await run_worker(
        sessions=r.sessions.begin,
        jobs=r.jobs,
        writes=r.jobs,
        handlers=build_handlers(
            r.deps,
            resume,
            make_criteria_deps(r.sessions, r.jobs)[0],
            make_kit_deps(r.sessions, r.jobs)[0],
        ),
        stop=stop,
        now=r.jobs.clock.now,
        sleep=r.jobs.clock.sleep,
        poll_seconds=1,
        lease_seconds=180,
    )
    assert [c[0] for c in r.jobs.writes()] == ["fail"]
    assert r.jobs.statuses() == []
