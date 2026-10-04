"""`propose_criteria`: one model call, then criteria and rubric levels into a Draft role.

Order (docs/design/worker-lld.md section 4.4): in one fenced transaction read the role and its
job description and end the job as stale before any call if the role is not a Draft at the job's
version or already has live criteria; call the gateway with no transaction open (the lease is
renewed before each call), with one more call at `schema_retry=1` if the reply is malformed or
truncated; the second failure is `Failed`, the role stays Draft and nothing is written. The
proposal is validated once, in `CriteriaPrompt.parse`; this handler never reads a reply field.

Lock mode of the write: `fenced(exclusive=True)`. `insert_criteria` locks the role `FOR UPDATE`
(it changes `criteria_version`), so the fence takes the same lock first rather than upgrading a
`FOR SHARE` inside the transaction. The handler ends the job itself inside that transaction.
"""

from dataclasses import dataclass
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.worker_writes import RoleState
from app.gateway import GatewayRequest, GatewayResponse
from app.gateway.text import JobDescriptionText, PromptText
from app.worker.context import JobContext
from app.worker.errors import SchemaError
from app.worker.handlers.scoring import JobEnds
from app.worker.loop import Handler
from app.worker.outcome import CRITERIA_FAILED, Failed, Outcome, Stale, Succeeded
from app.worker.ports import (
    CriteriaPrompt,
    CriterionSpec,
    JobDescriptionLoader,
    ProposedCriterion,
)

CRITERIA_MAX_TOKENS: Final = 1500
CRITERIA_FAILED_CODE: Final = "criteria_failed"


class CriteriaGateway(Protocol):
    """The part of `app.gateway.Gateway` this handler calls."""

    async def complete(self, request: GatewayRequest) -> GatewayResponse: ...


class CriteriaWrites(Protocol):
    """The part of `app.db.repositories.worker_writes` this handler calls (Q5, Q6, Q10)."""

    async def read_role(
        self, session: AsyncSession, role_id: UUID, *, exclusive: bool = False
    ) -> RoleState | None: ...

    async def read_criteria(self, session: AsyncSession, role_id: UUID) -> list[CriterionSpec]: ...

    async def insert_criteria(
        self,
        session: AsyncSession,
        *,
        role_id: UUID,
        criteria_version: int,
        proposed: list[ProposedCriterion],
    ) -> int | None: ...


@dataclass(frozen=True, slots=True)
class CriteriaDeps:
    """Everything `propose_criteria` needs; `prompt_version` comes from the prompt's owner."""

    gateway: CriteriaGateway
    writes: CriteriaWrites
    jobs: JobEnds
    load_job_description: JobDescriptionLoader
    prompt: CriteriaPrompt
    prompt_version: str


async def call_criteria(
    gateway: CriteriaGateway,
    *,
    role_id: UUID | None,
    prompt_version: str,
    system: PromptText,
    description: JobDescriptionText,
    schema_retry: int,
) -> GatewayResponse:
    """The one criteria request; the handler and the prompt evals both make it here."""
    return await gateway.complete(
        GatewayRequest(
            purpose="criteria",
            role_id=role_id,
            prompt_version=prompt_version,
            system=system,
            input=description,
            max_tokens=CRITERIA_MAX_TOKENS,
            schema_retry=schema_retry,
        )
    )


def make_propose_criteria(deps: CriteriaDeps) -> Handler:
    async def propose_criteria(ctx: JobContext) -> Outcome:
        job = ctx.job
        async with ctx.fenced() as session:
            role = await deps.writes.read_role(session, job.role_id)
            if (
                role is None
                or role.status != "draft"
                or role.criteria_version != job.criteria_version
                or await deps.writes.read_criteria(session, job.role_id)
            ):
                return await _end_stale(ctx, deps, session)
            description = await deps.load_job_description(session, job.role_id)

        system = deps.prompt.build()
        proposed: list[ProposedCriterion] | None = None
        for schema_retry in (0, 1):
            await ctx.renew()
            reply = await call_criteria(
                deps.gateway,
                role_id=job.role_id,
                prompt_version=deps.prompt_version,
                system=system,
                description=description,
                schema_retry=schema_retry,
            )
            if reply.finish_reason == "length":
                continue
            try:
                proposed = deps.prompt.parse(reply.text)
            except SchemaError:
                continue
            break
        if proposed is None:
            return Failed(CRITERIA_FAILED_CODE, CRITERIA_FAILED)

        async with ctx.fenced(exclusive=True) as session:
            version = await deps.writes.insert_criteria(
                session,
                role_id=job.role_id,
                criteria_version=job.criteria_version,
                proposed=proposed,
            )
            if version is None:
                return await _end_stale(ctx, deps, session)
            await deps.jobs.succeed(session, job.id, job.lease_token)
        return Succeeded()

    return propose_criteria


async def _end_stale(ctx: JobContext, deps: CriteriaDeps, session: AsyncSession) -> Stale:
    """Nothing was written: end the job as stale in this transaction."""
    await deps.jobs.mark_stale(session, ctx.job.id, ctx.job.lease_token)
    return Stale()
