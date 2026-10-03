"""The scoring step: strict parse, one schema retry, quotes verified by code, stale rules."""

from dataclasses import dataclass, field, replace
from decimal import Decimal
from uuid import UUID

import pytest

from app.db.repositories.worker_writes import RoleState
from app.gateway.errors import BudgetReachedError
from app.gateway.text import AnonymizedText
from app.worker.context import JobContext
from app.worker.errors import LeaseLostError, SchemaError
from app.worker.handlers.scoring import NO_CANDIDATE, QUOTE_NOT_FOUND, ScoringDeps, score_candidate
from app.worker.outcome import SOMETHING_WENT_WRONG, Failed, Stale, Succeeded
from app.worker.ports import ParsedScore
from tests.worker.fakes import (
    FakeAnonymizedLoader,
    FakeClock,
    FakeGateway,
    FakeJobs,
    FakeQuoteVerifier,
    FakeScoreParser,
    FakeScoringPrompt,
    FakeScoringWrites,
    FakeSessions,
    make_criteria,
    make_job,
    reply,
)


@dataclass
class Rig:
    ctx: JobContext
    jobs: FakeJobs
    sessions: FakeSessions
    writes: FakeScoringWrites
    gateway: FakeGateway
    prompt: FakeScoringPrompt
    parser: FakeScoreParser
    verifier: FakeQuoteVerifier
    deps: ScoringDeps
    criteria_ids: list[UUID] = field(default_factory=list)


def rig(*, criteria: int = 2) -> Rig:
    job = make_job(1, job_type="process_resume")
    assert job.candidate_id is not None
    sessions = FakeSessions()
    jobs = FakeJobs(FakeClock())
    writes = FakeScoringWrites(jobs, make_criteria(criteria))
    gateway = FakeGateway(sessions)
    prompt, parser = FakeScoringPrompt(), FakeScoreParser()
    verifier = FakeQuoteVerifier(jobs=jobs)
    loader = FakeAnonymizedLoader({job.candidate_id: "Built the billing service in Go."})
    deps = ScoringDeps(gateway, writes, jobs, loader, prompt, parser, verifier, "scoring-v1")
    return Rig(
        JobContext(job, sessions.begin, jobs, 180),
        jobs,
        sessions,
        writes,
        gateway,
        prompt,
        parser,
        verifier,
        deps,
        [c.id for c in writes.criteria],
    )


def scores(r: Rig, *quotes: str | None, value: int = 3) -> list[ParsedScore]:
    return [ParsedScore(cid, value, q) for cid, q in zip(r.criteria_ids, quotes, strict=True)]


async def test_scoring_asks_for_a_score_and_a_quote_or_no_evidence_per_criterion() -> None:
    r = rig()
    r.gateway.replies = [reply()]
    r.parser.results = [scores(r, "built billing", None)]
    r.verifier.found = {"built billing"}
    assert await score_candidate(r.ctx, r.deps, mark_done=True) == Succeeded()
    assert r.prompt.built_for == [r.writes.criteria]
    request = r.gateway.requests[0]
    assert (request.purpose, request.schema_retry, request.max_tokens) == ("scoring", 0, 1500)
    assert isinstance(request.input, AnonymizedText)
    assert request.role_id == r.ctx.job.role_id
    assert [(w.status, w.model_score, w.quote) for w in r.writes.written] == [
        ("scored", 3, "built billing"),
        ("no_evidence", 0, None),
    ]
    assert ("succeed", 1) in r.jobs.calls
    assert r.jobs.statuses()[0][2] == "done"


async def test_scoring_retries_once_on_malformed_output_with_schema_retry_one() -> None:
    r = rig()
    r.gateway.replies = [reply("bad"), reply("good")]
    r.parser.results = [SchemaError("bad"), scores(r, None, None)]
    assert await score_candidate(r.ctx, r.deps, mark_done=True) == Succeeded()
    assert [q.schema_retry for q in r.gateway.requests] == [0, 1]
    assert all(w.status == "no_evidence" for w in r.writes.written)


async def test_scoring_marks_every_criterion_failed_after_the_second_malformed_output() -> None:
    r = rig()
    r.gateway.replies = [reply("bad"), reply("worse")]
    r.parser.results = [SchemaError("bad"), SchemaError("worse")]
    assert await score_candidate(r.ctx, r.deps, mark_done=True) == Succeeded()
    assert len(r.gateway.requests) == 2  # one retry, never a third call
    assert [w.status for w in r.writes.written] == ["failed", "failed"]


async def test_scoring_never_guesses_a_value_for_a_failed_criterion() -> None:
    r = rig()
    r.gateway.replies = [reply("bad"), reply("worse")]
    r.parser.results = [SchemaError("bad"), SchemaError("worse")]
    await score_candidate(r.ctx, r.deps, mark_done=True)
    assert all(w.model_score is None and w.quote is None for w in r.writes.written)


async def test_a_criterion_missing_from_a_parsed_reply_is_stored_failed_not_guessed() -> None:
    r = rig()
    r.gateway.replies = [reply()]
    r.parser.results = [scores(r, None, None)[:1]]
    await score_candidate(r.ctx, r.deps, mark_done=True)
    assert [w.status for w in r.writes.written] == ["no_evidence", "failed"]
    assert r.writes.written[1].model_score is None


async def test_truncated_output_counts_as_malformed() -> None:
    r = rig()
    r.gateway.replies = [reply("cut", finish_reason="length"), reply("good")]
    r.parser.results = [scores(r, None, None)]
    await score_candidate(r.ctx, r.deps, mark_done=True)
    assert r.parser.parsed == ["good"]  # the truncated reply was never parsed
    assert [q.schema_retry for q in r.gateway.requests] == [0, 1]


async def test_two_truncated_outputs_fail_every_criterion() -> None:
    r = rig()
    r.gateway.replies = [reply("cut", finish_reason="length")] * 2
    await score_candidate(r.ctx, r.deps, mark_done=True)
    assert [w.status for w in r.writes.written] == ["failed", "failed"]


async def test_a_quote_that_is_not_in_the_text_is_replaced_and_the_score_capped_and_flagged() -> (
    None
):
    r = rig()
    r.gateway.replies = [reply()]
    r.parser.results = [scores(r, "invented quote", "built billing", value=4)]
    r.verifier.found = {"built billing"}
    await score_candidate(r.ctx, r.deps, mark_done=True)
    first, second = r.writes.written
    assert (first.status, first.model_score, first.quote) == ("no_evidence", 0, None)
    assert first.flag_reason == QUOTE_NOT_FOUND
    assert (second.status, second.model_score, second.flag_reason) == ("scored", 4, None)


async def test_no_evidence_is_stored_as_zero_with_no_quote() -> None:
    r = rig()
    r.gateway.replies = [reply()]
    r.parser.results = [scores(r, None, None, value=4)]  # the model gave 4 without evidence
    await score_candidate(r.ctx, r.deps, mark_done=True)
    assert [(w.status, w.model_score, w.quote, w.flag_reason) for w in r.writes.written] == [
        ("no_evidence", 0, None, None)
    ] * 2
    assert r.verifier.checked == []  # no quote, nothing to verify


async def test_a_score_row_is_written_only_after_its_quote_was_verified() -> None:
    r = rig()
    r.gateway.replies = [reply()]
    r.parser.results = [scores(r, "q1", "q2")]
    await score_candidate(r.ctx, r.deps, mark_done=True)
    names = [c[0] for c in r.jobs.calls]
    assert names.index("verify") < names.index("write_scores")
    assert [c[1] for c in r.jobs.calls if c[0] == "verify"] == ["q1", "q2"]


async def test_scores_are_discarded_when_the_criteria_changed_after_enqueue() -> None:
    r = rig()
    r.gateway.replies = [reply()]
    r.parser.results = [scores(r, None, None)]
    r.writes.accept_scores = False  # the role moved on while the model was working
    assert await score_candidate(r.ctx, r.deps, mark_done=True) == Stale()
    assert r.writes.written == []
    assert ("mark_stale", 1) in r.jobs.calls
    assert ("succeed", 1) not in r.jobs.calls


async def test_stale_scoring_makes_no_model_call_when_the_version_already_differs() -> None:
    r = rig()
    r.writes.role = RoleState("approved", r.ctx.job.criteria_version + 1)
    assert await score_candidate(r.ctx, r.deps, mark_done=True) == Stale()
    assert r.gateway.requests == []


@pytest.mark.parametrize("status", ["draft", "archived"])
async def test_a_role_that_is_not_approved_is_stale_before_any_call(status: str) -> None:
    r = rig()
    r.writes.role = RoleState(status, r.ctx.job.criteria_version)
    assert await score_candidate(r.ctx, r.deps, mark_done=True) == Stale()
    assert r.gateway.requests == []


async def test_a_deleted_role_or_empty_criteria_is_stale_before_any_call() -> None:
    r = rig()
    r.writes.role = None
    assert await score_candidate(r.ctx, r.deps, mark_done=True) == Stale()
    r = rig(criteria=0)
    assert await score_candidate(r.ctx, r.deps, mark_done=True) == Stale()
    assert r.gateway.requests == []


async def test_stale_job_is_marked_stale_and_the_candidate_done() -> None:
    r = rig()
    r.writes.role = RoleState("draft", 1)
    await score_candidate(r.ctx, r.deps, mark_done=True)
    assert r.jobs.statuses() == [("set_status", r.ctx.job.candidate_id, "done", None)]
    assert ("mark_stale", 1) in r.jobs.calls
    assert r.jobs.writes() == []  # the loop writes nothing more


async def test_the_result_write_takes_the_role_lock_shared_not_exclusive() -> None:
    r = rig()
    r.gateway.replies = [reply()]
    r.parser.results = [scores(r, None, None)]
    await score_candidate(r.ctx, r.deps, mark_done=True)
    assert r.jobs.fence_exclusive == [False, False]


async def test_no_transaction_is_open_during_the_scoring_gateway_call() -> None:
    r = rig()
    r.gateway.replies = [reply("bad"), reply("good")]
    r.parser.results = [SchemaError("bad"), scores(r, None, None)]
    await score_candidate(r.ctx, r.deps, mark_done=True)
    assert r.gateway.open_during_call == [0, 0]
    assert r.sessions.open == 0


async def test_the_lease_is_renewed_before_each_scoring_call() -> None:
    r = rig()
    r.gateway.replies = [reply("bad"), reply("good")]
    r.parser.results = [SchemaError("bad"), scores(r, None, None)]
    await score_candidate(r.ctx, r.deps, mark_done=True)
    names = [c[0] for c in r.jobs.calls if c[0] in {"renew", "fence"}]
    assert names == ["fence", "renew", "renew", "fence"]


async def test_a_budget_stop_propagates_and_writes_nothing() -> None:
    r = rig()
    r.gateway.replies = [BudgetReachedError(Decimal(8), Decimal(8))]
    with pytest.raises(BudgetReachedError):
        await score_candidate(r.ctx, r.deps, mark_done=True)
    assert r.writes.written == []
    assert ("write_scores", 1) not in r.jobs.calls


async def test_a_lease_lost_before_the_result_write_writes_nothing() -> None:
    r = rig()
    r.gateway.replies = [reply()]
    r.parser.results = [scores(r, None, None)]
    r.parser.on_parse = lambda: setattr(r.jobs, "lease_gone", True)
    with pytest.raises(LeaseLostError):
        await score_candidate(r.ctx, r.deps, mark_done=True)
    assert r.writes.written == []


async def test_a_job_without_a_candidate_is_failed_and_calls_nothing() -> None:
    r = rig()
    ctx = JobContext(replace(r.ctx.job, candidate_id=None), r.sessions.begin, r.jobs, 180)
    assert await score_candidate(ctx, r.deps, mark_done=True) == Failed(
        NO_CANDIDATE, SOMETHING_WENT_WRONG
    )
    assert r.gateway.requests == []
    assert r.jobs.calls == []
