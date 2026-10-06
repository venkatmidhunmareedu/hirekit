"""`JobContext`: the fence comes first in every write, and the lease is renewed before each call."""

from datetime import timedelta

import pytest

from app.worker.context import JobContext
from app.worker.errors import LeaseLostError
from tests.worker.fakes import FakeClock, FakeJobs, FakeSessions, make_job

LEASE = 180


def build(jobs: FakeJobs, sessions: FakeSessions) -> JobContext:
    return JobContext(make_job(7), sessions.begin, jobs, LEASE)


async def test_fenced_locks_the_job_row_before_the_body_runs() -> None:
    jobs, sessions = FakeJobs(FakeClock()), FakeSessions()
    ctx = build(jobs, sessions)
    async with ctx.fenced():
        jobs.calls.append(("write",))
    assert [c[0] for c in jobs.calls] == ["fence", "write"]
    assert jobs.calls[0][1:] == (ctx.job.id, ctx.job.lease_token)


async def test_fenced_tells_the_fence_whether_the_role_lock_is_exclusive() -> None:
    jobs, sessions = FakeJobs(FakeClock()), FakeSessions()
    async with build(jobs, sessions).fenced(exclusive=True):
        pass
    async with build(jobs, sessions).fenced():
        pass
    assert jobs.fence_exclusive == [True, False]


async def test_fenced_raises_lease_lost_and_never_runs_the_body_when_the_lease_is_gone() -> None:
    jobs, sessions = FakeJobs(FakeClock(), lease_gone=True), FakeSessions()
    with pytest.raises(LeaseLostError):
        async with build(jobs, sessions).fenced():
            jobs.calls.append(("write",))
    assert ("write",) not in jobs.calls
    assert sessions.open == 0


async def test_renew_extends_the_lease_with_the_configured_seconds() -> None:
    clock = FakeClock()
    jobs, sessions = FakeJobs(clock), FakeSessions()
    ctx = build(jobs, sessions)
    await ctx.renew()
    assert jobs.calls == [("renew", ctx.job.id, ctx.job.lease_token, LEASE)]
    assert jobs.lease_expires_at == clock.now() + timedelta(seconds=LEASE)


async def test_renew_raises_lease_lost_when_the_lease_is_gone() -> None:
    jobs = FakeJobs(FakeClock(), lease_gone=True)
    with pytest.raises(LeaseLostError):
        await build(jobs, FakeSessions()).renew()


async def test_lease_is_renewed_before_each_model_call() -> None:
    """Eight calls of 25 seconds each outlast one 60 second lease only because of renewal."""
    clock = FakeClock()
    jobs, sessions = FakeJobs(clock), FakeSessions()
    ctx = JobContext(make_job(), sessions.begin, jobs, 60)
    for _ in range(8):
        await ctx.renew()
        clock.advance(25)  # the model call
        assert jobs.lease_expires_at is not None
        assert clock.now() < jobs.lease_expires_at
    assert [c[0] for c in jobs.calls] == ["renew"] * 8


async def test_no_transaction_is_open_during_a_gateway_call() -> None:
    clock = FakeClock()
    jobs, sessions = FakeJobs(clock), FakeSessions()
    ctx = build(jobs, sessions)
    await ctx.renew()
    assert sessions.open == 0  # a model call here would hold no transaction
    async with ctx.fenced():
        assert sessions.open == 1
    assert sessions.open == 0
