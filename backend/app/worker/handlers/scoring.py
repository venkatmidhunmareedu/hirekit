"""The shared "score one candidate" step used by `process_resume` and `rescore`.

Order (docs/design/worker-lld.md section 4.3): read the role, criteria and anonymized text in
one fenced transaction and end the job as stale before any model call if the role is not
Approved at the job's version; call the gateway with no transaction open (the lease is renewed
before each call); verify every quote in code; write the result in one fenced transaction.

Lock mode of the result write: `fenced()` without `exclusive`, so the role is locked `FOR SHARE`.
The write changes scores, never the role, so many Workers may write at once while a criteria
edit (`FOR UPDATE`) waits for them or they wait for it: the version check and the scores
upsert then see one role state. `exclusive=True` is for `propose_criteria` only (LLD section 5).

A score has a quote that code found in the anonymized text, or it is stored as no evidence
with value 0 (S-2 to S-4). A reply that stays malformed twice, or is truncated, stores every
criterion as `failed` with no value (S-5, REQ-023).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, Protocol
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.worker_writes import RoleState, ScoreRow
from app.gateway import GatewayRequest, GatewayResponse
from app.gateway.text import AnonymizedText, PromptText
from app.worker.context import JobContext
from app.worker.errors import SchemaError
from app.worker.outcome import SOMETHING_WENT_WRONG, Failed, Outcome, Stale, Succeeded
from app.worker.ports import (
    AnonymizedLoader,
    CriterionSpec,
    ParsedScore,
    QuoteVerifier,
    ScoreParser,
    ScoringPrompt,
)

log = structlog.get_logger()

SCORING_MAX_TOKENS: Final = 1500
NO_CANDIDATE: Final = "no_candidate"
QUOTE_NOT_FOUND: Final = "The quote was not found in the resume text, so it was replaced."


class ScoringGateway(Protocol):
    """The part of `app.gateway.Gateway` this step calls."""

    async def complete(self, request: GatewayRequest) -> GatewayResponse: ...


class ScoringWrites(Protocol):
    """The part of `app.db.repositories.worker_writes` this step calls (Q5 to Q9, Q8a)."""

    async def read_role(
        self, session: AsyncSession, role_id: UUID, *, exclusive: bool = False
    ) -> RoleState | None: ...

    async def read_criteria(self, session: AsyncSession, role_id: UUID) -> list[CriterionSpec]: ...

    async def write_scores(
        self,
        session: AsyncSession,
        *,
        role_id: UUID,
        criteria_version: int,
        candidate_id: UUID,
        scores: list[ScoreRow],
    ) -> bool: ...

    async def set_status(
        self,
        session: AsyncSession,
        candidate_id: UUID,
        status: str,
        failure_reason: str | None = None,
    ) -> None: ...


class JobEnds(Protocol):
    """The part of `app.db.repositories.jobs` that ends a job inside the fenced transaction."""

    async def succeed(self, session: AsyncSession, job_id: int, lease_token: UUID) -> None: ...

    async def mark_stale(self, session: AsyncSession, job_id: int, lease_token: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class ScoringDeps:
    """Everything the scoring step needs; `prompt_version` comes from the prompt's owner."""

    gateway: ScoringGateway
    writes: ScoringWrites
    jobs: JobEnds
    load_anonymized: AnonymizedLoader
    prompt: ScoringPrompt
    parser: ScoreParser
    verifier: QuoteVerifier
    prompt_version: str


async def score_candidate(ctx: JobContext, deps: ScoringDeps, *, mark_done: bool) -> Outcome:
    """Score the job's candidate against the role's live criteria.

    `mark_done` is True for `process_resume`, whose Succeeded and Stale ends set the candidate
    to `done`; a `rescore` leaves `processing_status` as it was.
    """
    job = ctx.job
    if job.candidate_id is None:
        return Failed(NO_CANDIDATE, SOMETHING_WENT_WRONG)
    candidate_id = job.candidate_id

    async with ctx.fenced() as session:
        role = await deps.writes.read_role(session, job.role_id)
        if (
            role is None
            or role.status != "approved"
            or role.criteria_version != job.criteria_version
        ):
            return await _end_stale(ctx, deps, session, candidate_id, mark_done)
        criteria = await deps.writes.read_criteria(session, job.role_id)
        if not criteria:
            return await _end_stale(ctx, deps, session, candidate_id, mark_done)
        text = await deps.load_anonymized(session, candidate_id)

    system = deps.prompt.build(criteria)
    rows = await score_text(
        deps.gateway,
        role_id=job.role_id,
        prompt_version=deps.prompt_version,
        system=system,
        criteria=criteria,
        text=text,
        parser=deps.parser,
        verifier=deps.verifier,
        before_call=ctx.renew,
    )

    async with ctx.fenced() as session:
        written = await deps.writes.write_scores(
            session,
            role_id=job.role_id,
            criteria_version=job.criteria_version,
            candidate_id=candidate_id,
            scores=rows,
        )
        if not written:
            return await _end_stale(ctx, deps, session, candidate_id, mark_done)
        if mark_done:
            await deps.writes.set_status(session, candidate_id, "done")
        await deps.jobs.succeed(session, job.id, job.lease_token)
    return Succeeded()


async def _end_stale(
    ctx: JobContext, deps: ScoringDeps, session: AsyncSession, candidate_id: UUID, mark_done: bool
) -> Stale:
    """Nothing was written (or is discarded): end the job as stale in this transaction."""
    if mark_done:
        await deps.writes.set_status(session, candidate_id, "done")
    await deps.jobs.mark_stale(session, ctx.job.id, ctx.job.lease_token)
    return Stale()


async def score_text(
    gateway: ScoringGateway,
    *,
    role_id: UUID,
    prompt_version: str,
    system: PromptText,
    criteria: list[CriterionSpec],
    text: AnonymizedText,
    parser: ScoreParser,
    verifier: QuoteVerifier,
    before_call: Callable[[], Awaitable[None]] | None = None,
) -> list[ScoreRow]:
    """Score one anonymized text: one call, and one more if the reply is malformed or truncated.

    Context-free core shared by the handler and the evals; `before_call` runs ahead of each
    gateway call (the handler renews its lease there). One row per criterion: a value is stored
    only with a quote that code found; two unusable replies make every row `failed`.
    """
    parsed: list[ParsedScore] | None = None
    for schema_retry in (0, 1):
        if before_call is not None:
            await before_call()
        reply = await gateway.complete(
            GatewayRequest(
                purpose="scoring",
                role_id=role_id,
                prompt_version=prompt_version,
                system=system,
                input=text,
                max_tokens=SCORING_MAX_TOKENS,
                schema_retry=schema_retry,
            )
        )
        if reply.finish_reason == "length":
            continue
        try:
            parsed = parser.parse(reply.text, criteria)
        except SchemaError:
            continue
        break
    return _rows(criteria, parsed, text, verifier)


def _rows(
    criteria: list[CriterionSpec],
    parsed: list[ParsedScore] | None,
    text: AnonymizedText,
    verifier: QuoteVerifier,
) -> list[ScoreRow]:
    """One row per live criterion; a value is stored only with a quote that code found."""
    by_criterion = {} if parsed is None else {p.criterion_id: p for p in parsed}
    rows: list[ScoreRow] = []
    for criterion in criteria:
        score = by_criterion.get(criterion.id)
        if score is None:
            rows.append(ScoreRow(criterion.id, "failed", None, None, None))
        elif score.quote is None:
            rows.append(ScoreRow(criterion.id, "no_evidence", 0, None, None))
        elif verifier.verify(score.quote, text):
            rows.append(ScoreRow(criterion.id, "scored", score.value, score.quote, None))
        else:
            rows.append(ScoreRow(criterion.id, "no_evidence", 0, None, QUOTE_NOT_FOUND))
    return rows
