"""`propose_criteria`: one call, strict parse, one schema retry, a fenced Draft-role write."""

from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.db.repositories.worker_writes import RoleState
from app.gateway.errors import BudgetReachedError
from app.gateway.text import JobDescriptionText
from app.worker.context import JobContext
from app.worker.errors import LeaseLostError, SchemaError
from app.worker.handlers.propose_criteria import (
    CRITERIA_FAILED_CODE,
    CRITERIA_MAX_TOKENS,
    CriteriaDeps,
    make_propose_criteria,
)
from app.worker.outcome import CRITERIA_FAILED, Failed, Stale, Succeeded
from app.worker.ports import ProposedCriterion
from tests.worker.fakes import (
    FakeClock,
    FakeCriteriaPrompt,
    FakeCriteriaWrites,
    FakeGateway,
    FakeJobs,
    FakeSessions,
    make_criteria,
    make_criteria_deps,
    make_job,
    reply,
)

PROPOSED = [
    ProposedCriterion("Go", "must_have", Decimal(1), ("none", "a", "b", "c", "expert")),
]


@dataclass
class Rig:
    ctx: JobContext
    jobs: FakeJobs
    sessions: FakeSessions
    writes: FakeCriteriaWrites
    gateway: FakeGateway
    prompt: FakeCriteriaPrompt
    deps: CriteriaDeps


def rig() -> Rig:
    job = make_job(1, job_type="propose_criteria")
    sessions, jobs = FakeSessions(), FakeJobs(FakeClock())
    deps, gateway, prompt, writes = make_criteria_deps(sessions, jobs, job.role_id)
    return Rig(
        JobContext(job, sessions.begin, jobs, 180), jobs, sessions, writes, gateway, prompt, deps
    )


async def run(r: Rig) -> object:
    return await make_propose_criteria(r.deps)(r.ctx)


async def test_propose_criteria_writes_criteria_and_rubric_and_bumps_the_version() -> None:
    r = rig()
    r.gateway.replies = [reply("proposal")]
    r.prompt.results = [PROPOSED]

    assert await run(r) == Succeeded()

    assert r.writes.inserted == PROPOSED
    assert ("insert_criteria", 1) in r.jobs.calls
    assert ("succeed", 1) in r.jobs.calls
    assert r.jobs.statuses() == []


async def test_propose_criteria_sends_the_job_description_under_the_criteria_purpose() -> None:
    r = rig()
    r.gateway.replies = [reply()]
    r.prompt.results = [PROPOSED]

    await run(r)

    request = r.gateway.requests[0]
    assert request.purpose == "criteria"
    assert request.schema_retry == 0
    assert request.max_tokens == CRITERIA_MAX_TOKENS
    assert isinstance(request.input, JobDescriptionText)
    assert request.input.value == "Senior Go engineer for billing."


async def test_propose_criteria_retries_once_on_malformed_output_with_schema_retry_one() -> None:
    r = rig()
    r.gateway.replies = [reply("bad"), reply("good")]
    r.prompt.results = [SchemaError("bad"), PROPOSED]

    assert await run(r) == Succeeded()

    assert [q.schema_retry for q in r.gateway.requests] == [0, 1]
    assert r.writes.inserted == PROPOSED


async def test_a_truncated_reply_counts_as_malformed_and_is_not_parsed() -> None:
    r = rig()
    r.gateway.replies = [reply("cut", "length"), reply("good")]
    r.prompt.results = [PROPOSED]

    assert await run(r) == Succeeded()

    assert r.prompt.parsed == ["good"]
    assert [q.schema_retry for q in r.gateway.requests] == [0, 1]


async def test_propose_criteria_failure_leaves_the_role_draft_and_writes_nothing() -> None:
    r = rig()
    r.gateway.replies = [reply("bad"), reply("worse")]
    r.prompt.results = [SchemaError("bad"), SchemaError("worse")]

    assert await run(r) == Failed(CRITERIA_FAILED_CODE, CRITERIA_FAILED)

    assert len(r.gateway.requests) == 2
    assert not any(c[0] in {"insert_criteria", "succeed", "mark_stale"} for c in r.jobs.calls)


async def test_a_gateway_error_propagates_for_the_loop_to_decide_and_writes_nothing() -> None:
    r = rig()
    r.gateway.replies = [BudgetReachedError(Decimal(8), Decimal(8))]

    with pytest.raises(BudgetReachedError):
        await run(r)

    assert not any(c[0] in {"insert_criteria", "succeed", "mark_stale"} for c in r.jobs.calls)


async def test_propose_criteria_after_cancel_writes_nothing() -> None:
    r = rig()
    r.jobs.lease_gone = True

    with pytest.raises(LeaseLostError):
        await run(r)

    assert r.gateway.requests == []
    assert r.writes.inserted == []


async def test_a_lease_lost_during_the_call_stops_before_the_write() -> None:
    r = rig()
    r.gateway.replies = [reply()]
    r.prompt.results = [PROPOSED]
    r.jobs.lease_gone = True

    with pytest.raises(LeaseLostError):
        await run(r)

    assert r.writes.inserted == []


@pytest.fixture(name="existing")
def existing_fixture() -> Rig:
    return rig()


async def test_propose_criteria_on_a_role_that_already_has_criteria_is_stale_and_inserts_nothing(
    existing: Rig,
) -> None:
    r = existing
    r.writes.live = make_criteria(1)

    assert await run(r) == Stale()

    assert ("mark_stale", 1) in r.jobs.calls
    assert r.gateway.requests == []
    assert r.writes.inserted == []


async def test_a_criteria_row_that_appears_during_the_call_makes_the_write_stale() -> None:
    r = rig()
    r.gateway.replies = [reply()]
    r.prompt.results = [PROPOSED]
    r.writes.inserted_version = None

    assert await run(r) == Stale()

    assert ("mark_stale", 1) in r.jobs.calls
    assert ("succeed", 1) not in r.jobs.calls


async def test_an_approved_role_is_stale_and_makes_no_call() -> None:
    r = rig()
    r.writes.role = RoleState("approved", 1)

    assert await run(r) == Stale()

    assert r.gateway.requests == []
    assert ("mark_stale", 1) in r.jobs.calls


async def test_a_role_at_another_version_is_stale_and_makes_no_call() -> None:
    r = rig()
    r.writes.role = RoleState("draft", 5)

    assert await run(r) == Stale()

    assert r.gateway.requests == []


async def test_a_deleted_role_is_stale_and_makes_no_call() -> None:
    r = rig()
    r.writes.role = None

    assert await run(r) == Stale()

    assert r.gateway.requests == []


async def test_no_transaction_is_open_during_the_gateway_call() -> None:
    r = rig()
    r.gateway.replies = [reply("bad"), reply("good")]
    r.prompt.results = [SchemaError("bad"), PROPOSED]

    await run(r)

    assert r.gateway.open_during_call == [0, 0]


async def test_the_lease_is_renewed_before_each_call() -> None:
    r = rig()
    r.gateway.replies = [reply("bad"), reply("good")]
    r.prompt.results = [SchemaError("bad"), PROPOSED]

    await run(r)

    assert [c[0] for c in r.jobs.calls].count("renew") == 2


async def test_the_result_write_is_fenced_exclusively_and_the_read_is_not() -> None:
    r = rig()
    r.gateway.replies = [reply()]
    r.prompt.results = [PROPOSED]

    await run(r)

    assert r.jobs.fence_exclusive == [False, True]
