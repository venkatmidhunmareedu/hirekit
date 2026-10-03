"""`JobContext`: the claimed job, its lease, and the fenced-write helper every handler uses.

`renew` is called before every gateway call so a job with many calls keeps its lease for the
whole attempt. `fenced` opens a transaction and locks the job row first thing, so a Worker whose
lease is gone raises `LeaseLostError` and writes nothing (docs/design/worker-lld.md section 3).
Repositories take the session; the context and the loop own the transactions.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.jobs import Job

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
"""A transaction: `async_sessionmaker.begin`, which commits on exit and rolls back on error."""


class JobsRepository(Protocol):
    """The part of `app.db.repositories.jobs` the loop and the context call."""

    async def claim(self, session: AsyncSession, *, lease_seconds: int) -> Job | None: ...

    async def fence(self, session: AsyncSession, job_id: int, lease_token: UUID) -> None: ...

    async def renew(
        self, session: AsyncSession, job_id: int, lease_token: UUID, *, lease_seconds: int
    ) -> None: ...

    async def reschedule(
        self,
        session: AsyncSession,
        job_id: int,
        lease_token: UUID,
        *,
        run_after: datetime,
        code: str,
    ) -> None: ...

    async def fail(
        self, session: AsyncSession, job_id: int, lease_token: UUID, *, code: str
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class JobContext:
    """A claimed job with the means to keep and use its lease."""

    job: Job
    sessions: SessionFactory
    jobs: JobsRepository
    lease_seconds: int

    async def renew(self) -> None:
        """Extend the lease in its own short transaction; raises `LeaseLostError` if it is gone."""
        async with self.sessions() as session:
            await self.jobs.renew(
                session, self.job.id, self.job.lease_token, lease_seconds=self.lease_seconds
            )

    @asynccontextmanager
    async def fenced(self) -> AsyncIterator[AsyncSession]:
        """A transaction that starts by locking the job row; every handler write goes in one."""
        async with self.sessions() as session:
            await self.jobs.fence(session, self.job.id, self.job.lease_token)
            yield session
