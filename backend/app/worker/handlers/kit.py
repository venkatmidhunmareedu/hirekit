"""The kit handlers: `generate_kit` for a role and `regenerate_question` for one question.

Order (docs/design/worker-lld.md section 4.5): in one fenced transaction read the role, its live
criteria and each criterion's job description text, and end the job as stale before any call if
the role is not Approved at the job's version; call the gateway with no transaction open (the
lease is renewed before each call), once per criterion for a kit and once for a question, with
one more call at `schema_retry=1` if a reply is malformed or truncated; a second failure is
`Failed`, nothing is written. The model sees the job description and the criterion, never resume
text: purpose `kit` takes `JobDescriptionText`. A reply is validated once, in
`KitPrompt.parse`. Each handler ends its own job inside the fenced write.

Lock modes of the write, both without `exclusive`: the role is locked `FOR SHARE`, because the
write changes questions and the kit header, never the role, so a criteria edit (`FOR UPDATE`)
and the writes see one role state and kit writes do not queue behind each other on the role.
`generate_kit` also passes `lock_open_jobs`: it cancels the role's open `regenerate_question`
jobs before it deletes questions, so it takes every open job of the role in ascending id, its own
row included, before it checks its own lease (LLD section 5). `regenerate_question` writes one
question and cancels nothing, so its own row is all it needs.
"""

from dataclasses import dataclass
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.worker_writes import NewQuestion, RoleState
from app.gateway import GatewayRequest, GatewayResponse
from app.gateway.text import JobDescriptionText, PromptText
from app.worker.context import JobContext
from app.worker.errors import SchemaError
from app.worker.handlers.scoring import JobEnds
from app.worker.loop import Handler
from app.worker.outcome import KIT_FAILED, SOMETHING_WENT_WRONG, Failed, Outcome, Stale, Succeeded
from app.worker.ports import CriterionSpec, JobDescriptionLoader, KitPrompt, ProposedQuestion

KIT_MAX_TOKENS: Final = 1500
KIT_FAILED_CODE: Final = "kit_failed"
NO_QUESTION: Final = "no_question"


class KitGateway(Protocol):
    """The part of `app.gateway.Gateway` these handlers call."""

    async def complete(self, request: GatewayRequest) -> GatewayResponse: ...


class KitWrites(Protocol):
    """The part of `app.db.repositories.worker_writes` these handlers call (Q5, Q6, Q11)."""

    async def read_role(
        self, session: AsyncSession, role_id: UUID, *, exclusive: bool = False
    ) -> RoleState | None: ...

    async def read_criteria(self, session: AsyncSession, role_id: UUID) -> list[CriterionSpec]: ...

    async def read_question(
        self, session: AsyncSession, role_id: UUID, question_id: UUID
    ) -> UUID | None: ...

    async def replace_kit(
        self,
        session: AsyncSession,
        *,
        role_id: UUID,
        criteria_version: int,
        questions: list[NewQuestion],
    ) -> bool: ...

    async def replace_question(
        self,
        session: AsyncSession,
        *,
        role_id: UUID,
        criteria_version: int,
        question_id: UUID,
        question_text: str,
        strong_answer: str,
        weak_answer: str,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class KitDeps:
    """Everything the kit handlers need; `prompt_version` comes from the prompt's owner."""

    gateway: KitGateway
    writes: KitWrites
    jobs: JobEnds
    load_job_description: JobDescriptionLoader
    prompt: KitPrompt
    prompt_version: str


@dataclass(frozen=True, slots=True)
class _Input:
    """One criterion and the text the model sees for it."""

    criterion: CriterionSpec
    description: JobDescriptionText


def make_generate_kit(deps: KitDeps) -> Handler:
    async def generate_kit(ctx: JobContext) -> Outcome:
        job = ctx.job
        async with ctx.fenced() as session:
            inputs = await _read_inputs(ctx, deps, session, None)
            if not inputs:
                return await _end_stale(ctx, deps, session)

        questions: list[NewQuestion] = []
        for item in inputs:
            proposed = await _ask(ctx, deps, item)
            if proposed is None:
                return Failed(KIT_FAILED_CODE, KIT_FAILED)
            questions += [
                NewQuestion(
                    item.criterion.id, position, p.question_text, p.strong_answer, p.weak_answer
                )
                for position, p in enumerate(proposed, start=1)
            ]

        async with ctx.fenced(lock_open_jobs=True) as session:
            written = await deps.writes.replace_kit(
                session,
                role_id=job.role_id,
                criteria_version=job.criteria_version,
                questions=questions,
            )
            if not written:
                return await _end_stale(ctx, deps, session)
            await deps.jobs.succeed(session, job.id, job.lease_token)
        return Succeeded()

    return generate_kit


def make_regenerate_question(deps: KitDeps) -> Handler:
    async def regenerate_question(ctx: JobContext) -> Outcome:
        job = ctx.job
        question_id = job.question_id
        if question_id is None:
            return Failed(NO_QUESTION, SOMETHING_WENT_WRONG)
        async with ctx.fenced() as session:
            inputs = await _read_inputs(ctx, deps, session, question_id)
            if not inputs:
                return await _end_stale(ctx, deps, session)

        proposed = await _ask(ctx, deps, inputs[0])
        if proposed is None:
            return Failed(KIT_FAILED_CODE, KIT_FAILED)
        question = proposed[0]

        async with ctx.fenced() as session:
            written = await deps.writes.replace_question(
                session,
                role_id=job.role_id,
                criteria_version=job.criteria_version,
                question_id=question_id,
                question_text=question.question_text,
                strong_answer=question.strong_answer,
                weak_answer=question.weak_answer,
            )
            if not written:
                return await _end_stale(ctx, deps, session)
            await deps.jobs.succeed(session, job.id, job.lease_token)
        return Succeeded()

    return regenerate_question


async def _read_inputs(
    ctx: JobContext, deps: KitDeps, session: AsyncSession, question_id: UUID | None
) -> list[_Input]:
    """The criteria to ask about, or none when the job is stale (nothing is called).

    A kit asks about every live criterion; a question asks about the one it probes.
    """
    job = ctx.job
    role = await deps.writes.read_role(session, job.role_id)
    if role is None or role.status != "approved" or role.criteria_version != job.criteria_version:
        return []
    criteria = await deps.writes.read_criteria(session, job.role_id)
    if question_id is not None:
        probed = await deps.writes.read_question(session, job.role_id, question_id)
        criteria = [c for c in criteria if c.id == probed]
    return [_Input(c, await deps.load_job_description(session, job.role_id, c)) for c in criteria]


async def call_kit(
    gateway: KitGateway,
    *,
    role_id: UUID | None,
    prompt_version: str,
    system: PromptText,
    description: JobDescriptionText,
    schema_retry: int,
) -> GatewayResponse:
    """The one kit request; the handlers and the prompt evals both make it here."""
    return await gateway.complete(
        GatewayRequest(
            purpose="kit",
            role_id=role_id,
            prompt_version=prompt_version,
            system=system,
            input=description,
            max_tokens=KIT_MAX_TOKENS,
            schema_retry=schema_retry,
        )
    )


async def _ask(ctx: JobContext, deps: KitDeps, item: _Input) -> list[ProposedQuestion] | None:
    """One call for one criterion, one more at `schema_retry=1`; None if both are unusable."""
    system = deps.prompt.build(item.criterion)
    for schema_retry in (0, 1):
        await ctx.renew()
        reply = await call_kit(
            deps.gateway,
            role_id=ctx.job.role_id,
            prompt_version=deps.prompt_version,
            system=system,
            description=item.description,
            schema_retry=schema_retry,
        )
        if reply.finish_reason == "length":
            continue
        try:
            proposed = deps.prompt.parse(reply.text)
        except SchemaError:
            continue
        if proposed:
            return proposed
    return None


async def _end_stale(ctx: JobContext, deps: KitDeps, session: AsyncSession) -> Stale:
    """Nothing was written: end the job as stale in this transaction."""
    await deps.jobs.mark_stale(session, ctx.job.id, ctx.job.lease_token)
    return Stale()
