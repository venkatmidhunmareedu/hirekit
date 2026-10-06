"""The kit handlers: one call per criterion, strict parse, one schema retry, a fenced write."""

from dataclasses import dataclass, replace
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.repositories.worker_writes import NewQuestion, RoleState
from app.gateway.errors import BudgetReachedError
from app.gateway.text import JobDescriptionText, PromptText
from app.worker.context import JobContext
from app.worker.errors import LeaseLostError, SchemaError
from app.worker.handlers.kit import (
    KIT_FAILED_CODE,
    KIT_MAX_TOKENS,
    NO_QUESTION,
    KitDeps,
    make_generate_kit,
    make_regenerate_question,
)
from app.worker.outcome import KIT_FAILED, SOMETHING_WENT_WRONG, Failed, Stale, Succeeded
from app.worker.ports import CriterionSpec, ProposedQuestion
from tests.worker.fakes import (
    FakeClock,
    FakeGateway,
    FakeJobs,
    FakeKitPrompt,
    FakeKitWrites,
    FakeSessions,
    make_criteria,
    make_job,
    make_kit_deps,
    reply,
)

ONE = ProposedQuestion("Tell me about Go?", "strong", "weak")
TWO = ProposedQuestion("Tell me about SQL?", "strong too", "weak too")


@dataclass
class Rig:
    ctx: JobContext
    jobs: FakeJobs
    sessions: FakeSessions
    writes: FakeKitWrites
    gateway: FakeGateway
    prompt: FakeKitPrompt
    deps: KitDeps
    criteria: list[CriterionSpec]


def rig(job_type: str = "generate_kit", *, criteria: int = 2) -> Rig:
    job = make_job(1, job_type=job_type)
    sessions, jobs = FakeSessions(), FakeJobs(FakeClock())
    deps, gateway, prompt, writes = make_kit_deps(sessions, jobs, job.role_id)
    writes.criteria = make_criteria(criteria)
    return Rig(
        JobContext(job, sessions.begin, jobs, 180),
        jobs,
        sessions,
        writes,
        gateway,
        prompt,
        deps,
        writes.criteria,
    )


def regenerate_rig() -> Rig:
    r = rig("regenerate_question")
    r.writes.probed = r.criteria[1].id
    job = replace(r.ctx.job, question_id=uuid4())
    return replace(r, ctx=JobContext(job, r.sessions.begin, r.jobs, 180))


async def generate(r: Rig) -> object:
    return await make_generate_kit(r.deps)(r.ctx)


async def regenerate(r: Rig) -> object:
    return await make_regenerate_question(r.deps)(r.ctx)


def writes_made(r: Rig) -> list[str]:
    return [c[0] for c in r.jobs.calls if c[0] in {"replace_kit", "replace_question", "succeed"}]


async def test_generate_kit_makes_one_call_per_criterion() -> None:
    r = rig(criteria=3)
    r.gateway.replies = [reply(), reply(), reply()]
    r.prompt.results = [[ONE], [ONE, TWO], [TWO]]

    assert await generate(r) == Succeeded()

    assert [q.purpose for q in r.gateway.requests] == ["kit"] * 3
    assert [q.schema_retry for q in r.gateway.requests] == [0, 0, 0]
    assert r.prompt.built_for == r.criteria
    assert [(q.criterion_id, q.position) for q in r.writes.kit] == [
        (r.criteria[0].id, 1),
        (r.criteria[1].id, 1),
        (r.criteria[1].id, 2),
        (r.criteria[2].id, 1),
    ]
    assert r.writes.kit[0] == NewQuestion(r.criteria[0].id, 1, ONE.question_text, "strong", "weak")
    assert ("succeed", 1) in r.jobs.calls


async def test_kit_prompt_contains_the_job_description_and_criteria_and_no_candidate_data() -> None:
    r = rig()
    r.gateway.replies = [reply(), reply()]
    r.prompt.results = [[ONE], [ONE]]

    await generate(r)

    for request, criterion in zip(r.gateway.requests, r.criteria, strict=True):
        assert isinstance(request.input, JobDescriptionText)
        assert request.input.value == f"Senior Go engineer for billing.\n{criterion.name}"
        assert isinstance(request.system, PromptText)
        assert request.max_tokens == KIT_MAX_TOKENS
    assert not any(c[0] in {"read_file", "read_anonymized"} for c in r.jobs.calls)


async def test_generate_kit_for_a_draft_role_is_stale_and_makes_no_call() -> None:
    r = rig()
    r.writes.role = RoleState("draft", 1)

    assert await generate(r) == Stale()

    assert r.gateway.requests == []
    assert ("mark_stale", 1) in r.jobs.calls
    assert writes_made(r) == []


async def test_generate_kit_for_a_role_at_another_version_or_deleted_is_stale() -> None:
    for role in (RoleState("approved", 5), None):
        r = rig()
        r.writes.role = role

        assert await generate(r) == Stale()

        assert r.gateway.requests == []


async def test_generate_kit_for_a_role_with_no_live_criteria_is_stale() -> None:
    r = rig(criteria=0)

    assert await generate(r) == Stale()

    assert r.gateway.requests == []


async def test_generate_kit_retries_a_malformed_reply_once_with_schema_retry_one() -> None:
    r = rig(criteria=1)
    r.gateway.replies = [reply("bad"), reply("good")]
    r.prompt.results = [SchemaError("bad"), [ONE]]

    assert await generate(r) == Succeeded()

    assert [q.schema_retry for q in r.gateway.requests] == [0, 1]


async def test_a_truncated_reply_counts_as_malformed_and_is_not_parsed() -> None:
    r = rig(criteria=1)
    r.gateway.replies = [reply("cut", "length"), reply("good")]
    r.prompt.results = [[ONE]]

    assert await generate(r) == Succeeded()

    assert r.prompt.parsed == ["good"]


async def test_generate_kit_fails_and_writes_nothing_when_one_criterion_stays_malformed() -> None:
    r = rig()
    r.gateway.replies = [reply(), reply("bad"), reply("worse")]
    r.prompt.results = [[ONE], SchemaError("bad"), SchemaError("worse")]

    assert await generate(r) == Failed(KIT_FAILED_CODE, KIT_FAILED)

    assert len(r.gateway.requests) == 3
    assert writes_made(r) == []


async def test_a_reply_with_no_questions_counts_as_malformed() -> None:
    r = rig(criteria=1)
    r.gateway.replies = [reply(), reply()]
    r.prompt.results = [[], []]

    assert await generate(r) == Failed(KIT_FAILED_CODE, KIT_FAILED)


async def test_a_gateway_error_propagates_for_the_loop_to_decide_and_writes_nothing() -> None:
    r = rig()
    r.gateway.replies = [reply(), BudgetReachedError(Decimal(8), Decimal(8))]
    r.prompt.results = [[ONE]]

    with pytest.raises(BudgetReachedError):
        await generate(r)

    assert writes_made(r) == []


async def test_generate_kit_discards_the_questions_when_the_role_changed_during_the_calls() -> None:
    r = rig()
    r.gateway.replies = [reply(), reply()]
    r.prompt.results = [[ONE], [ONE]]
    r.writes.accept = False

    assert await generate(r) == Stale()

    assert r.writes.kit == []
    assert ("mark_stale", 1) in r.jobs.calls
    assert ("succeed", 1) not in r.jobs.calls


async def test_generate_kit_after_cancel_writes_nothing() -> None:
    r = rig()
    r.jobs.lease_gone = True

    with pytest.raises(LeaseLostError):
        await generate(r)

    assert r.gateway.requests == []
    assert writes_made(r) == []


async def test_a_lease_lost_during_the_calls_stops_before_the_write() -> None:
    r = rig(criteria=1)
    r.gateway.replies = [reply()]
    r.prompt.results = [[ONE]]
    r.jobs.lease_gone = True

    with pytest.raises(LeaseLostError):
        await generate(r)

    assert r.writes.kit == []


async def test_no_transaction_is_open_during_a_gateway_call() -> None:
    r = rig()
    r.gateway.replies = [reply("bad"), reply("good"), reply()]
    r.prompt.results = [SchemaError("bad"), [ONE], [ONE]]

    await generate(r)

    assert r.gateway.open_during_call == [0, 0, 0]


async def test_the_lease_is_renewed_before_each_call() -> None:
    r = rig()
    r.gateway.replies = [reply("bad"), reply("good"), reply()]
    r.prompt.results = [SchemaError("bad"), [ONE], [ONE]]

    await generate(r)

    assert [c[0] for c in r.jobs.calls].count("renew") == 3


async def test_the_kit_write_locks_the_role_shared_and_all_open_jobs_and_the_read_does_not() -> (
    None
):
    r = rig()
    r.gateway.replies = [reply(), reply()]
    r.prompt.results = [[ONE], [ONE]]

    await generate(r)

    assert r.jobs.fence_exclusive == [False, False]
    assert r.jobs.fence_open_jobs == [False, True]
    assert ("read_role", False) in r.jobs.calls


async def test_regenerate_question_replaces_the_one_question_it_probes() -> None:
    r = regenerate_rig()
    question_id = r.ctx.job.question_id
    r.gateway.replies = [reply()]
    r.prompt.results = [[ONE, TWO]]

    assert await regenerate(r) == Succeeded()

    assert len(r.gateway.requests) == 1
    assert r.prompt.built_for == [r.criteria[1]]
    assert r.gateway.requests[0].purpose == "kit"
    assert r.writes.replaced == [(question_id, ONE.question_text, "strong", "weak")]
    assert ("succeed", 1) in r.jobs.calls


async def test_regenerate_question_without_a_question_id_fails_with_a_plain_reason() -> None:
    r = rig("regenerate_question")

    assert await regenerate(r) == Failed(NO_QUESTION, SOMETHING_WENT_WRONG)

    assert r.gateway.requests == []


async def test_regenerate_question_for_a_deleted_question_is_stale_and_makes_no_call() -> None:
    r = regenerate_rig()
    r.writes.probed = None  # the question is gone

    assert await regenerate(r) == Stale()

    assert r.gateway.requests == []
    assert writes_made(r) == []


async def test_regenerate_question_for_a_draft_role_is_stale_and_makes_no_call() -> None:
    r = regenerate_rig()
    r.writes.role = RoleState("draft", 1)

    assert await regenerate(r) == Stale()

    assert r.gateway.requests == []


async def test_regenerate_question_fails_after_a_second_malformed_reply() -> None:
    r = regenerate_rig()
    r.gateway.replies = [reply("bad"), reply("worse")]
    r.prompt.results = [SchemaError("bad"), SchemaError("worse")]

    assert await regenerate(r) == Failed(KIT_FAILED_CODE, KIT_FAILED)

    assert [q.schema_retry for q in r.gateway.requests] == [0, 1]
    assert writes_made(r) == []


async def test_regenerate_question_discards_the_text_when_the_question_is_deleted_meanwhile() -> (
    None
):
    r = regenerate_rig()
    r.gateway.replies = [reply()]
    r.prompt.results = [[ONE]]
    r.writes.accept = False

    assert await regenerate(r) == Stale()

    assert r.writes.replaced == []
    assert ("mark_stale", 1) in r.jobs.calls


async def test_regenerate_question_fences_the_write_without_extra_locks() -> None:
    r = regenerate_rig()
    r.gateway.replies = [reply()]
    r.prompt.results = [[ONE]]

    await regenerate(r)

    assert r.jobs.fence_exclusive == [False, False]
    assert r.jobs.fence_open_jobs == [False, False]
    assert r.gateway.open_during_call == [0]
    assert [c[0] for c in r.jobs.calls].count("renew") == 1
