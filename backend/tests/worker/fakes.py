"""In-memory stand-ins for the clock, the transactions and the jobs repository.

`FakeJobs` records every call as a tuple and follows the real repository's rule that a write
after the lease is gone raises `LeaseLostError`; the SQL itself is proven against Postgres in
tests/integration/test_jobs_repository.py.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.jobs import Job
from app.worker.errors import LeaseLostError

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

    async def claim(self, session: AsyncSession, *, lease_seconds: int) -> Job | None:
        self.calls.append(("claim", lease_seconds))
        if self.claim_error:
            raise OperationalError("STATEMENT", {}, Exception("database down"))
        return self.queue.pop(0) if self.queue else None

    async def fence(self, session: AsyncSession, job_id: int, lease_token: UUID) -> None:
        self.calls.append(("fence", job_id, lease_token))
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

    def writes(self) -> list[tuple[object, ...]]:
        """Only the end-state writes, without claims, fences and renewals."""
        return [c for c in self.calls if c[0] in {"reschedule", "fail"}]
