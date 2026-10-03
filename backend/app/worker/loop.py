"""The claim loop: claim a job, run its handler, apply the outcome, repeat.

A handler returns `Succeeded` or `Stale` after writing the end state inside its own fenced
transaction, so the loop writes nothing for them. A returned `Retry` or `Failed`, and any
exception, is applied here as one fenced finish (T5), the exception first through
`policy.next_step`. `LeaseLostError` drops the job: another Worker owns it. No transaction is
open while a handler runs. `claim` fails attempt-exhausted expired jobs itself and goes on to the
next one, so the loop only ever sees a job to run or nothing.
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from typing import Final

import structlog
from sqlalchemy.exc import InterfaceError, OperationalError

from app.worker.context import JobContext, JobsRepository, SessionFactory
from app.worker.errors import LeaseLostError
from app.worker.outcome import SOMETHING_WENT_WRONG, Failed, Outcome, Retry
from app.worker.policy import next_step

log = structlog.get_logger()

NO_HANDLER: Final = "no_handler"

Handler = Callable[[JobContext], Awaitable[Outcome]]
Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]


async def run_worker(
    *,
    sessions: SessionFactory,
    jobs: JobsRepository,
    handlers: Mapping[str, Handler],
    stop: asyncio.Event,
    now: Clock,
    sleep: Sleep,
    poll_seconds: float,
    lease_seconds: int,
) -> None:
    """Run until `stop` is set; the job in hand is finished first. `sleep` waits out a poll."""
    while not stop.is_set():
        try:
            async with sessions() as session:
                job = await jobs.claim(session, lease_seconds=lease_seconds)
        except (OperationalError, InterfaceError) as error:
            log.warning("claim_failed", error=type(error).__name__)
            job = None
        if job is None:
            await sleep(poll_seconds)
            continue
        ctx = JobContext(job, sessions, jobs, lease_seconds)
        try:
            await _run_one(ctx, handlers, jobs, now)
        except LeaseLostError:
            log.info("lease_lost", job_id=job.id, type=job.type)
        except (OperationalError, InterfaceError) as error:
            # The end state was not written; the lease expires and the job is reclaimed.
            log.warning("finish_failed", job_id=job.id, error=type(error).__name__)


async def _run_one(
    ctx: JobContext, handlers: Mapping[str, Handler], jobs: JobsRepository, now: Clock
) -> None:
    job = ctx.job
    handler = handlers.get(job.type)
    if handler is None:
        outcome: Outcome = Failed(NO_HANDLER, SOMETHING_WENT_WRONG)
    else:
        try:
            outcome = await handler(ctx)
        except LeaseLostError:
            raise
        except Exception as error:
            # Never the message: it can carry text (tenet 7).
            log.warning("job_failed", job_id=job.id, type=job.type, error=type(error).__name__)
            outcome = next_step(error, job.attempt, now(), job.deadline_at)
    if isinstance(outcome, Retry):
        async with ctx.sessions() as session:
            await jobs.reschedule(
                session, job.id, job.lease_token, run_after=outcome.run_after, code=outcome.code
            )
    elif isinstance(outcome, Failed):
        async with ctx.sessions() as session:
            await jobs.fail(session, job.id, job.lease_token, code=outcome.code)
