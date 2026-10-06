"""`score_candidate` with the real builder, parser and verifier; only the gateway is a fake."""

import json

from app.prompts.scoring_parser import ScoreReplyParser
from app.prompts.scoring_prompt import ScoringPromptBuilder
from app.worker.context import JobContext
from app.worker.handlers.scoring import QUOTE_NOT_FOUND, ScoringDeps, score_candidate
from app.worker.outcome import Succeeded
from app.worker.quotes import WhitespaceQuoteVerifier
from tests.worker.fakes import (
    FakeAnonymizedLoader,
    FakeClock,
    FakeGateway,
    FakeJobs,
    FakeScoringWrites,
    FakeSessions,
    make_criteria,
    make_job,
    reply,
)

TEXT = "Built the billing service in Go.\nMentored two juniors."


async def run(model_reply: str) -> tuple[FakeScoringWrites, FakeGateway]:
    job = make_job(1)
    assert job.candidate_id is not None
    sessions = FakeSessions()
    jobs = FakeJobs(FakeClock())
    writes = FakeScoringWrites(jobs, make_criteria(2))
    gateway = FakeGateway(sessions, [reply(model_reply)])
    builder = ScoringPromptBuilder()
    deps = ScoringDeps(
        gateway,
        writes,
        jobs,
        FakeAnonymizedLoader({job.candidate_id: TEXT}),
        builder,
        ScoreReplyParser(),
        WhitespaceQuoteVerifier(),
        builder.prompt_version,
    )
    ctx = JobContext(job, sessions.begin, jobs, 180)
    assert await score_candidate(ctx, deps, mark_done=True) == Succeeded()
    return writes, gateway


def scores(*items: tuple[int, int, str | None]) -> str:
    return json.dumps({"scores": [{"criterion": c, "value": v, "quote": q} for c, v, q in items]})


async def test_a_verified_quote_is_stored_and_the_request_is_well_formed() -> None:
    writes, gateway = await run(scores((1, 3, "billing   service\nin Go"), (2, 0, None)))
    assert [(w.status, w.model_score) for w in writes.written] == [
        ("scored", 3),
        ("no_evidence", 0),
    ]
    request = gateway.requests[0]
    assert request.prompt_version == "scoring-v1"
    assert request.input.value == TEXT
    assert "<criteria>" in request.system.value


async def test_an_invented_quote_becomes_no_evidence() -> None:
    writes, _ = await run(scores((1, 4, "Led a team of fifty"), (2, 0, None)))
    row = writes.written[0]
    assert (row.status, row.model_score, row.quote, row.flag_reason) == (
        "no_evidence",
        0,
        None,
        QUOTE_NOT_FOUND,
    )


async def test_a_null_quote_with_a_non_zero_value_is_stored_as_zero_no_evidence() -> None:
    writes, _ = await run(scores((1, 3, None), (2, 0, "no evidence found")))
    assert [(w.status, w.model_score, w.quote) for w in writes.written] == [
        ("no_evidence", 0, None),
        ("no_evidence", 0, None),
    ]
