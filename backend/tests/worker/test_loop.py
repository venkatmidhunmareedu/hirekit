"""The claim loop with fakes: no database, no network, no real sleeping."""

import asyncio
from datetime import timedelta

import pytest

from app.db.repositories.jobs import Job
from app.gateway.errors import RateLimitedError
from app.worker.context import JobContext
from app.worker.errors import LeaseLostError
from app.worker.loop import Handler, run_worker
from app.worker.outcome import Failed, Outcome, Retry, Stale, Succeeded
from app.worker.policy import BACKOFF_SECONDS
from tests.worker.fakes import FakeClock, FakeJobs, FakeSessions, make_job

POLL = 1.0
LEASE = 180


async def drive(
    jobs: FakeJobs, clock: FakeClock, sessions: FakeSessions, handlers: dict[str, Handler]
) -> asyncio.Event:
    """Run until the clock's sleep stops the loop, or a handler sets the event."""
    stop = asyncio.Event()
    clock.stop = stop
    await run_worker(
        sessions=sessions.begin,
        jobs=jobs,
        handlers=handlers,
        stop=stop,
        now=clock.now,
        sleep=clock.sleep,
        poll_seconds=POLL,
        lease_seconds=LEASE,
    )
    return stop


def setup(*queue: Job) -> tuple[FakeJobs, FakeClock, FakeSessions]:
    clock = FakeClock()
    return FakeJobs(clock, list(queue)), clock, FakeSessions()


async def test_loop_runs_a_claimed_job_and_marks_it_succeeded() -> None:
    jobs, clock, sessions = setup(make_job(1))
    seen: list[int] = []

    async def handler(ctx: JobContext) -> Outcome:
        async with ctx.fenced():
            seen.append(ctx.job.id)
        return Succeeded()

    await drive(jobs, clock, sessions, {"process_resume": handler})
    assert seen == [1]
    assert jobs.writes() == []  # the handler wrote the end state inside its own fence
    assert sessions.open == 0


async def test_a_rate_limit_then_a_success_on_the_second_claim() -> None:
    jobs, clock, sessions = setup(make_job(1))
    attempts: list[int] = []

    async def handler(ctx: JobContext) -> Outcome:
        attempts.append(ctx.job.attempt)
        if len(attempts) == 1:
            raise RateLimitedError("429")
        return Succeeded()

    await drive(jobs, clock, sessions, {"process_resume": handler})
    assert jobs.writes() == [
        (
            "reschedule",
            1,
            clock.current - timedelta(seconds=POLL) + timedelta(seconds=BACKOFF_SECONDS[0]),
            "rate_limited",
        )
    ]
    jobs.queue.append(make_job(1, attempt=2))
    clock.slept.clear()
    await drive(jobs, clock, sessions, {"process_resume": handler})
    assert attempts == [1, 2]
    assert len(jobs.writes()) == 1


async def test_loop_sleeps_when_there_is_nothing_to_claim() -> None:
    jobs, clock, sessions = setup()
    await drive(jobs, clock, sessions, {})
    assert clock.slept == [POLL]
    assert jobs.calls == [("claim", LEASE)]


async def test_loop_stops_claiming_after_sigterm_and_finishes_the_current_job() -> None:
    jobs, clock, sessions = setup(make_job(1), make_job(2))
    stop = asyncio.Event()
    finished: list[int] = []

    async def handler(ctx: JobContext) -> Outcome:
        stop.set()  # SIGTERM arrives mid-job
        await asyncio.sleep(0)
        async with ctx.fenced():
            finished.append(ctx.job.id)
        return Succeeded()

    await run_worker(
        sessions=sessions.begin,
        jobs=jobs,
        handlers={"process_resume": handler},
        stop=stop,
        now=clock.now,
        sleep=clock.sleep,
        poll_seconds=POLL,
        lease_seconds=LEASE,
    )
    assert finished == [1]
    assert [j.id for j in jobs.queue] == [2]  # never claimed


async def test_lease_lost_drops_the_job_without_writing() -> None:
    jobs, clock, sessions = setup(make_job(1))

    async def handler(ctx: JobContext) -> Outcome:
        await ctx.renew()
        return Succeeded()

    jobs.lease_gone = True
    await drive(jobs, clock, sessions, {"process_resume": handler})
    assert jobs.writes() == []
    assert clock.slept == [POLL]  # the loop carried on to the next claim


async def test_a_lease_lost_while_applying_the_outcome_is_dropped() -> None:
    jobs, clock, sessions = setup(make_job(1))

    async def handler(ctx: JobContext) -> Outcome:
        raise LeaseLostError("gone")

    await drive(jobs, clock, sessions, {"process_resume": handler})
    assert jobs.writes() == []


async def test_an_unknown_job_type_is_failed_as_no_handler() -> None:
    jobs, clock, sessions = setup(make_job(1, job_type="mystery"))
    await drive(jobs, clock, sessions, {})
    assert jobs.writes() == [("fail", 1, "no_handler")]


async def test_a_job_that_raises_is_failed_with_only_its_class_name() -> None:
    jobs, clock, sessions = setup(make_job(1))

    async def handler(ctx: JobContext) -> Outcome:
        raise ValueError("resume text must not leak")

    await drive(jobs, clock, sessions, {"process_resume": handler})
    assert jobs.writes() == [("fail", 1, "ValueError")]


@pytest.mark.parametrize("outcome", [Succeeded(), Stale()])
async def test_a_handler_that_ends_the_job_itself_leaves_nothing_for_the_loop(
    outcome: Outcome,
) -> None:
    jobs, clock, sessions = setup(make_job(1))

    async def handler(ctx: JobContext) -> Outcome:
        return outcome

    await drive(jobs, clock, sessions, {"process_resume": handler})
    assert jobs.writes() == []


async def test_a_returned_failed_outcome_is_applied() -> None:
    jobs, clock, sessions = setup(make_job(1))

    async def handler(ctx: JobContext) -> Outcome:
        return Failed("extraction_failed", "No text")

    await drive(jobs, clock, sessions, {"process_resume": handler})
    assert jobs.writes() == [("fail", 1, "extraction_failed")]


async def test_a_returned_retry_outcome_is_applied() -> None:
    jobs, clock, sessions = setup(make_job(1))
    when = clock.now() + timedelta(seconds=30)

    async def handler(ctx: JobContext) -> Outcome:
        return Retry(when, "database_unavailable")

    await drive(jobs, clock, sessions, {"process_resume": handler})
    assert jobs.writes() == [("reschedule", 1, when, "database_unavailable")]


async def test_a_database_outage_on_claim_is_logged_and_waited_out() -> None:
    jobs, clock, sessions = setup()
    jobs.claim_error = True
    await drive(jobs, clock, sessions, {})
    assert clock.slept == [POLL]


async def test_no_transaction_is_open_while_a_handler_runs() -> None:
    jobs, clock, sessions = setup(make_job(1))
    open_during: list[int] = []

    async def handler(ctx: JobContext) -> Outcome:
        open_during.append(sessions.open)  # a gateway call would happen here
        return Succeeded()

    await drive(jobs, clock, sessions, {"process_resume": handler})
    assert open_during == [0]
