"""In-memory stand-ins for the user and session repositories."""

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.db.models import Criterion, Role, RubricLevel, User, UserSession
from app.db.repositories.jobs_api import JobView, QueueRow
from app.db.repositories.sessions import hash_token


class FakeUsers:
    def __init__(self) -> None:
        self.rows: list[User] = []

    def add(
        self, *, email: str, role: str, password_hash: str | None = None, name: str = "Riya"
    ) -> User:
        user = User(
            id=uuid.uuid4(),
            name=name,
            email=email,
            role=role,
            password_hash=password_hash or "unused",
        )
        self.rows.append(user)
        return user

    async def by_email(self, email: str) -> User | None:
        return next((u for u in self.rows if u.email.lower() == email.lower()), None)

    async def by_id(self, user_id: uuid.UUID) -> User | None:
        return next((u for u in self.rows if u.id == user_id), None)


class FakeSessions:
    def __init__(self) -> None:
        self.rows: dict[bytes, UserSession] = {}

    async def create(
        self, token: str, user_id: uuid.UUID, csrf_token: str, expires_at: datetime
    ) -> None:
        self.rows[hash_token(token)] = UserSession(
            token_hash=hash_token(token),
            user_id=user_id,
            csrf_token=csrf_token,
            expires_at=expires_at,
        )

    async def read_valid(self, token: str) -> UserSession | None:
        row = self.rows.get(hash_token(token))
        if row is None or row.expires_at <= datetime.now(UTC):
            return None
        return row

    async def delete(self, token: str) -> None:
        self.rows.pop(hash_token(token), None)

    async def sign_in(self, user: User, *, ttl: timedelta = timedelta(hours=1)) -> SignedIn:
        token = f"tok-{uuid.uuid4().hex}"
        csrf = f"csrf-{uuid.uuid4().hex}"
        await self.create(token, user.id, csrf, datetime.now(UTC) + ttl)
        return SignedIn(token=token, csrf=csrf)


class SignedIn:
    def __init__(self, *, token: str, csrf: str) -> None:
        self.token = token
        self.csrf = csrf

    @property
    def cookie(self) -> dict[str, str]:
        return {"Cookie": f"hirekit_session={self.token}"}

    @property
    def unsafe_headers(self) -> dict[str, str]:
        return {**self.cookie, "X-CSRF-Token": self.csrf}


class FakeRoles:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, Role] = {}
        self.assigned: set[tuple[uuid.UUID, uuid.UUID]] = set()  # (role_id, user_id)

    def seed(self, *, status: str = "draft", version: int = 1) -> Role:
        role = Role(
            id=uuid.uuid4(),
            title="Backend engineer",
            job_description="Build things.",
            status=status,
            criteria_version=version,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.rows[role.id] = role
        return role

    async def create(self, title: str, job_description: str) -> Role:
        role = self.seed()
        role.title, role.job_description = title, job_description
        return role

    async def list_recent(self, limit: int) -> list[Role]:
        newest_first = sorted(self.rows.values(), key=lambda r: r.created_at, reverse=True)
        return newest_first[:limit]

    async def get(self, role_id: uuid.UUID, *, lock: bool = False) -> Role | None:
        return self.rows.get(role_id)

    async def interviewer_can_read(self, role_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return (role_id, user_id) in self.assigned

    async def mark_draft_and_bump(self, role_id: uuid.UUID) -> Role:
        role = self.rows[role_id]
        role.status, role.criteria_version = "draft", role.criteria_version + 1
        return role

    async def mark_approved(self, role_id: uuid.UUID) -> Role:
        role = self.rows[role_id]
        role.status = "approved"
        return role


class FakeCriteria:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, Criterion] = {}
        self.rubrics: dict[uuid.UUID, dict[int, str]] = {}

    def seed(
        self, role_id: uuid.UUID, name: str, *, levels: int = 5, position: int = 0
    ) -> Criterion:
        criterion = Criterion(
            id=uuid.uuid4(),
            role_id=role_id,
            name=name,
            kind="must_have",
            weight=Decimal(3),
            position=position,
            retired_at=None,
        )
        self.rows[criterion.id] = criterion
        self.rubrics[criterion.id] = {n: f"level {n}" for n in range(levels)}
        return criterion

    async def live(self, role_id: uuid.UUID) -> list[Criterion]:
        mine = [c for c in self.rows.values() if c.role_id == role_id and c.retired_at is None]
        return sorted(mine, key=lambda c: c.position)

    async def levels(self, criterion_ids: list[uuid.UUID]) -> list[RubricLevel]:
        return [
            RubricLevel(criterion_id=i, level=n, descriptor=d)
            for i in criterion_ids
            for n, d in sorted(self.rubrics.get(i, {}).items())
        ]

    async def add(
        self, role_id: uuid.UUID, *, name: str, kind: str, weight: int, position: int
    ) -> uuid.UUID:
        criterion = self.seed(role_id, name, levels=0, position=position)
        criterion.kind, criterion.weight = kind, Decimal(weight)
        return criterion.id

    async def edit(
        self, criterion_id: uuid.UUID, *, name: str, kind: str, weight: int, position: int
    ) -> None:
        row = self.rows[criterion_id]
        row.name, row.kind, row.weight, row.position = name, kind, Decimal(weight), position

    async def retire(self, criterion_ids: list[uuid.UUID]) -> None:
        for i in criterion_ids:
            self.rows[i].retired_at = datetime.now(UTC)

    async def replace_levels(self, criterion_id: uuid.UUID, levels: list[tuple[int, str]]) -> None:
        self.rubrics[criterion_id] = dict(levels)


OPEN = ("queued", "running")


class FakeJobs:
    """In-memory stand-in for the jobs repository of the Api."""

    def __init__(self) -> None:
        self.rows: dict[int, JobView] = {}
        self.targets: dict[int, uuid.UUID] = {}  # job id -> candidate id
        self.candidate_failures: dict[uuid.UUID, str] = {}
        self.spent_usd: Decimal | None = None
        self.queue_rows: list[QueueRow] = []
        self.counts: tuple[int, int] = (0, 0)

    def seed(
        self,
        role_id: uuid.UUID,
        *,
        kind: str = "propose_criteria",
        status: str = "queued",
        candidate_id: uuid.UUID | None = None,
    ) -> JobView:
        job = JobView(
            id=len(self.rows) + 1,
            type=kind,
            status=status,
            role_id=role_id,
            candidate_no=None,
            criteria_version=1,
            attempt=0,
            last_error=None,
            created_at=datetime.now(UTC),
        )
        self.rows[job.id] = job
        if candidate_id is not None:
            self.targets[job.id] = candidate_id
        return job

    async def spent(self) -> Decimal | None:
        return self.spent_usd

    async def enqueue_propose(self, role_id: uuid.UUID, criteria_version: int) -> int | None:
        if any(
            j.role_id == role_id and j.type == "propose_criteria" and j.status in OPEN
            for j in self.rows.values()
        ):
            return None
        return self.seed(role_id).id

    async def get(self, job_id: int) -> JobView | None:
        return self.rows.get(job_id)

    async def cancel(self, job_id: int) -> bool:
        job = self.rows.get(job_id)
        if job is None or job.status not in OPEN:
            return False
        self.rows[job_id] = replace(job, status="cancelled")
        if job.type == "process_resume" and job_id in self.targets:
            self.candidate_failures[self.targets[job_id]] = "Cancelled by a recruiter"
        return True

    async def queue(self, role_id: uuid.UUID, limit: int) -> list[QueueRow]:
        return self.queue_rows[:limit]

    async def open_counts(self, role_id: uuid.UUID) -> tuple[int, int]:
        return self.counts
