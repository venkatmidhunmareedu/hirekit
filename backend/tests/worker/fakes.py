"""In-memory stand-ins for the clock, the transactions and the jobs repository.

`FakeJobs` records every call as a tuple and follows the real repository's rule that a write
after the lease is gone raises `LeaseLostError`; the SQL itself is proven against Postgres in
tests/integration/test_jobs_repository.py.
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.jobs import Job
from app.db.repositories.worker_writes import RoleState, ScoreRow
from app.gateway import GatewayRequest, GatewayResponse
from app.gateway.text import (
    AnonymizedText,
    JobDescriptionText,
    PromptText,
    mint_anonymized,
    mint_job_description,
    mint_prompt,
)
from app.worker.errors import LeaseLostError
from app.worker.ports import CriterionSpec, ParsedScore

START = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


@dataclass
class FakeClock:
    """A clock that only moves when told to; `sleep` advances it and records the pause."""

    current: datetime = START
    slept: list[float] = field(default_factory=list)
    stop: asyncio.Event | None = None
    stop_after_sleeps: int = 1

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.advance(seconds)
        if self.stop is not None and len(self.slept) >= self.stop_after_sleeps:
            self.stop.set()


@dataclass
class FakeSessions:
    """Stands in for `async_sessionmaker.begin`; counts the transactions open right now."""

    open: int = 0
    opened: int = 0

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncSession]:
        self.open += 1
        self.opened += 1
        try:
            yield AsyncSession()  # never bound to an engine, so it never connects
        finally:
            self.open -= 1


def make_job(job_id: int = 1, *, job_type: str = "process_resume", attempt: int = 1) -> Job:
    return Job(
        id=job_id,
        type=job_type,
        role_id=uuid4(),
        candidate_id=uuid4(),
        question_id=None,
        criteria_version=1,
        attempt=attempt,
        deadline_at=START + timedelta(minutes=30),
        lease_token=uuid4(),
    )


@dataclass
class FakeJobs:
    """Hands out `queue` in order and records the writes the loop and the context make."""

    clock: FakeClock
    queue: list[Job] = field(default_factory=list)
    calls: list[tuple[object, ...]] = field(default_factory=list)
    lease_gone: bool = False
    claim_error: bool = False
    lease_expires_at: datetime | None = None
    fail_session: AsyncSession | None = None
    status_sessions: list[AsyncSession] = field(default_factory=list)
    fence_exclusive: list[bool] = field(default_factory=list)

    async def claim(self, session: AsyncSession, *, lease_seconds: int) -> Job | None:
        self.calls.append(("claim", lease_seconds))
        if self.claim_error:
            raise OperationalError("STATEMENT", {}, Exception("database down"))
        return self.queue.pop(0) if self.queue else None

    async def fence(
        self, session: AsyncSession, job_id: int, lease_token: UUID, *, exclusive: bool = False
    ) -> None:
        self.calls.append(("fence", job_id, lease_token))
        self.fence_exclusive.append(exclusive)
        if self.lease_gone:
            raise LeaseLostError("The job lease is gone")

    async def renew(
        self, session: AsyncSession, job_id: int, lease_token: UUID, *, lease_seconds: int
    ) -> None:
        self.calls.append(("renew", job_id, lease_token, lease_seconds))
        if self.lease_gone:
            raise LeaseLostError("The job lease is gone")
        self.lease_expires_at = self.clock.now() + timedelta(seconds=lease_seconds)

    async def reschedule(
        self,
        session: AsyncSession,
        job_id: int,
        lease_token: UUID,
        *,
        run_after: datetime,
        code: str,
    ) -> None:
        self.calls.append(("reschedule", job_id, run_after, code))

    async def fail(
        self, session: AsyncSession, job_id: int, lease_token: UUID, *, code: str
    ) -> None:
        self.calls.append(("fail", job_id, code))
        self.fail_session = session

    async def set_status(
        self,
        session: AsyncSession,
        candidate_id: UUID,
        status: str,
        failure_reason: str | None = None,
    ) -> None:
        """Stands in for `worker_writes.set_status`, which the loop calls beside `fail`."""
        self.calls.append(("set_status", candidate_id, status, failure_reason))
        self.status_sessions.append(session)

    async def succeed(self, session: AsyncSession, job_id: int, lease_token: UUID) -> None:
        self.calls.append(("succeed", job_id))

    async def mark_stale(self, session: AsyncSession, job_id: int, lease_token: UUID) -> None:
        self.calls.append(("mark_stale", job_id))

    def statuses(self) -> list[tuple[object, ...]]:
        """Only the candidate status writes."""
        return [c for c in self.calls if c[0] == "set_status"]

    def writes(self) -> list[tuple[object, ...]]:
        """Only the end-state writes, without claims, fences and renewals."""
        return [c for c in self.calls if c[0] in {"reschedule", "fail"}]


@dataclass
class FakeAnonymizedLoader:
    """Stands in for `app.anonymizer.load_anonymized`, minting like the real one."""

    texts: dict[UUID, str] = field(default_factory=dict)

    async def __call__(self, session: AsyncSession, candidate_id: UUID) -> AnonymizedText:
        return mint_anonymized(self.texts[candidate_id])


@dataclass
class FakeJobDescriptionLoader:
    """Stands in for the job-description loader, which has no package yet."""

    descriptions: dict[UUID, str] = field(default_factory=dict)

    async def __call__(
        self, session: AsyncSession, role_id: UUID, criterion: CriterionSpec | None = None
    ) -> JobDescriptionText:
        suffix = "" if criterion is None else f"\n{criterion.name}"
        return mint_job_description(self.descriptions[role_id] + suffix)


def make_criteria(count: int = 2) -> list[CriterionSpec]:
    return [
        CriterionSpec(uuid4(), f"criterion {i}", "must_have", Decimal(1), i, ((0, "none"),))
        for i in range(1, count + 1)
    ]


@dataclass
class FakeScoringWrites:
    """Stands in for `worker_writes`: one role state, the criteria, the scores written."""

    jobs: FakeJobs
    criteria: list[CriterionSpec] = field(default_factory=list)
    role: RoleState | None = field(default_factory=lambda: RoleState("approved", 1))
    accept_scores: bool = True
    written: list[ScoreRow] = field(default_factory=list)

    async def read_role(
        self, session: AsyncSession, role_id: UUID, *, exclusive: bool = False
    ) -> RoleState | None:
        self.jobs.calls.append(("read_role", exclusive))
        return self.role

    async def read_criteria(self, session: AsyncSession, role_id: UUID) -> list[CriterionSpec]:
        self.jobs.calls.append(("read_criteria",))
        return self.criteria

    async def write_scores(
        self,
        session: AsyncSession,
        *,
        role_id: UUID,
        criteria_version: int,
        candidate_id: UUID,
        scores: list[ScoreRow],
    ) -> bool:
        self.jobs.calls.append(("write_scores", criteria_version))
        if self.accept_scores:
            self.written = list(scores)
        return self.accept_scores

    async def set_status(
        self,
        session: AsyncSession,
        candidate_id: UUID,
        status: str,
        failure_reason: str | None = None,
    ) -> None:
        await self.jobs.set_status(session, candidate_id, status, failure_reason)


@dataclass
class FakeGateway:
    """Replays `replies` in order (an exception is raised) and records each request."""

    sessions: FakeSessions
    replies: list[GatewayResponse | Exception] = field(default_factory=list)
    requests: list[GatewayRequest] = field(default_factory=list)
    open_during_call: list[int] = field(default_factory=list)

    async def complete(self, request: GatewayRequest) -> GatewayResponse:
        self.requests.append(request)
        self.open_during_call.append(self.sessions.open)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def reply(text: str = "reply", finish_reason: str = "stop") -> GatewayResponse:
    return GatewayResponse(text, 10, 10, finish_reason, "key", True, Decimal(0))


@dataclass
class FakeScoringPrompt:
    built_for: list[list[CriterionSpec]] = field(default_factory=list)

    def build(self, criteria: list[CriterionSpec]) -> PromptText:
        self.built_for.append(criteria)
        return mint_prompt("score each criterion")


@dataclass
class FakeScoreParser:
    """One result per call: a list of scores, or an exception to raise."""

    results: list[list[ParsedScore] | Exception] = field(default_factory=list)
    parsed: list[str] = field(default_factory=list)
    on_parse: Callable[[], None] | None = None

    def parse(self, reply: str, criteria: list[CriterionSpec]) -> list[ParsedScore]:
        self.parsed.append(reply)
        if self.on_parse is not None:
            self.on_parse()
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


@dataclass
class FakeQuoteVerifier:
    """Accepts a quote only if it is in `found`; records the order against the other fakes."""

    found: set[str] = field(default_factory=set)
    checked: list[str] = field(default_factory=list)
    jobs: FakeJobs | None = None

    def verify(self, quote: str, text: AnonymizedText) -> bool:
        self.checked.append(quote)
        if self.jobs is not None:
            self.jobs.calls.append(("verify", quote))
        return quote in self.found
