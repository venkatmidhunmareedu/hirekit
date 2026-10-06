"""In-memory stand-ins for the user and session repositories."""

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.api.candidates.assignment_schemas import InterviewerOption
from app.core.errors import FeedbackLockedError
from app.db.models import Criterion, Role, RubricLevel, User, UserSession
from app.db.repositories.cost import CallRow
from app.db.repositories.feedback import StoredFeedback
from app.db.repositories.jobs_api import JobView, QueueRow
from app.db.repositories.kit import QuestionRef
from app.db.repositories.scoring_jobs import CandidateState, RescoreTarget
from app.db.repositories.sessions import hash_token
from app.db.repositories.uploads import RoleState


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

    async def list_by_role(self, role: str, limit: int) -> list[InterviewerOption]:
        found = sorted((u for u in self.rows if u.role == role), key=lambda u: (u.name, u.id))
        return [InterviewerOption(id=u.id, name=u.name) for u in found[:limit]]


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


class FakeUploads:
    """Candidates, files and jobs in memory; shares the roles fake so a role can turn Draft."""

    def __init__(self, roles: FakeRoles) -> None:
        self.roles = roles
        self.spent: Decimal | None = Decimal(0)
        self.candidates: list[dict[str, object]] = []
        self.files: list[tuple[uuid.UUID, str, bytes]] = []
        self.jobs: list[tuple[uuid.UUID, uuid.UUID, int]] = []
        self.draft_after: int | None = None  # the role turns Draft once this many files are stored

    async def spent_usd(self) -> Decimal | None:
        return self.spent

    async def lock_role(self, role_id: uuid.UUID) -> RoleState | None:
        role = self.roles.rows.get(role_id)
        if role is None:
            return None
        if self.draft_after is not None and len(self.files) >= self.draft_after:
            role.status = "draft"
        return RoleState(role.status, role.criteria_version)

    async def find_duplicate(
        self, role_id: uuid.UUID, content_hash: str
    ) -> tuple[uuid.UUID, int] | None:
        for c in self.candidates:
            if c["role_id"] == role_id and c["content_hash"] == content_hash:
                return uuid.UUID(str(c["id"])), int(str(c["candidate_no"]))
        return None

    async def insert_candidate(
        self,
        role_id: uuid.UUID,
        file_name: str,
        content_hash: str,
        duplicate_of_id: uuid.UUID | None,
    ) -> tuple[uuid.UUID, int]:
        candidate_id, number = uuid.uuid4(), len(self.candidates) + 1
        self.candidates.append(
            {
                "id": candidate_id,
                "candidate_no": number,
                "role_id": role_id,
                "file_name": file_name,
                "content_hash": content_hash,
                "duplicate_of_id": duplicate_of_id,
            }
        )
        return candidate_id, number

    async def insert_file(self, candidate_id: uuid.UUID, media_type: str, content: bytes) -> None:
        self.files.append((candidate_id, media_type, content))

    async def enqueue_process_resume(
        self, role_id: uuid.UUID, candidate_id: uuid.UUID, criteria_version: int
    ) -> None:
        self.jobs.append((role_id, candidate_id, criteria_version))


class FakeScoringJobs:
    """Retry and rescore state in memory; `needs` and `open_jobs` are set per candidate."""

    def __init__(self, roles: FakeRoles) -> None:
        self.roles = roles
        self.spent: Decimal | None = Decimal(0)
        self.candidates: dict[uuid.UUID, tuple[uuid.UUID, int]] = {}  # id -> (role_id, number)
        self.needs: set[uuid.UUID] = set()
        self.open_jobs: set[uuid.UUID] = set()
        self.enqueued: list[tuple[str, uuid.UUID, uuid.UUID, int]] = []
        self.reset: list[uuid.UUID] = []

    def add(
        self, role_id: uuid.UUID, *, needs: bool = True, open_job: bool = False
    ) -> tuple[uuid.UUID, int]:
        candidate_id, number = uuid.uuid4(), len(self.candidates) + 1
        self.candidates[candidate_id] = (role_id, number)
        if needs:
            self.needs.add(candidate_id)
        if open_job:
            self.open_jobs.add(candidate_id)
        return candidate_id, number

    async def spent_usd(self) -> Decimal | None:
        return self.spent

    async def candidate_role_id(self, candidate_id: uuid.UUID) -> uuid.UUID | None:
        found = self.candidates.get(candidate_id)
        return None if found is None else found[0]

    async def lock_role(self, role_id: uuid.UUID) -> RoleState | None:
        role = self.roles.rows.get(role_id)
        return None if role is None else RoleState(role.status, role.criteria_version)

    async def lock_candidate(
        self, candidate_id: uuid.UUID, criteria_version: int
    ) -> CandidateState | None:
        if candidate_id not in self.candidates:
            return None
        return CandidateState(candidate_id in self.needs, candidate_id in self.open_jobs)

    async def lock_rescore_targets(
        self, role_id: uuid.UUID, criteria_version: int
    ) -> list[RescoreTarget]:
        return [
            RescoreTarget(i, number, i in self.open_jobs)
            for i, (rid, number) in sorted(self.candidates.items(), key=lambda kv: kv[1][1])
            if rid == role_id and i in self.needs
        ]

    async def enqueue(
        self, job_type: str, role_id: uuid.UUID, candidate_id: uuid.UUID, criteria_version: int
    ) -> int:
        self.enqueued.append((job_type, role_id, candidate_id, criteria_version))
        self.open_jobs.add(candidate_id)
        return 100 + len(self.enqueued)

    async def reset_candidate(self, candidate_id: uuid.UUID) -> None:
        self.reset.append(candidate_id)


class FakeCost:
    """A call log in memory, newest first, with the same keyset rule as the repository."""

    def __init__(self) -> None:
        self.spent: Decimal | None = Decimal("0.412300")
        self.calls: list[CallRow] = []

    def add(self, call_id: int, created_at: datetime) -> None:
        self.calls.append(
            CallRow(call_id, "scoring", "settled", "m", 10, 5, Decimal("0.002700"), created_at)
        )

    async def spent_usd(self) -> Decimal | None:
        return self.spent

    async def page(self, limit: int, after: tuple[datetime, int] | None) -> list[CallRow]:
        newest_first = sorted(self.calls, key=lambda c: (c.created_at, c.id), reverse=True)
        if after is not None:
            newest_first = [c for c in newest_first if (c.created_at, c.id) < after]
        return newest_first[:limit]


class FakeKit:
    """Kit header, questions and kit jobs in memory; shares the roles fake."""

    def __init__(self, roles: FakeRoles) -> None:
        self.roles = roles
        self.spent: Decimal | None = Decimal(0)
        self.versions: dict[uuid.UUID, int] = {}
        self.rows: dict[uuid.UUID, dict[str, object]] = {}
        self.jobs: list[tuple[str, uuid.UUID, uuid.UUID | None, int]] = []

    def seed_question(self, role_id: uuid.UUID, *, position: int = 0) -> uuid.UUID:
        question_id = uuid.uuid4()
        self.versions.setdefault(role_id, self.roles.rows[role_id].criteria_version)
        self.rows[question_id] = {
            "id": question_id,
            "role_id": role_id,
            "criterion_id": uuid.uuid4(),
            "question_text": "Q",
            "strong_answer": "S",
            "weak_answer": "W",
            "position": position,
        }
        return question_id

    async def spent_usd(self) -> Decimal | None:
        return self.spent

    async def lock_role(self, role_id: uuid.UUID) -> RoleState | None:
        role = self.roles.rows.get(role_id)
        return None if role is None else RoleState(role.status, role.criteria_version)

    async def kit_version(self, role_id: uuid.UUID) -> int | None:
        return self.versions.get(role_id)

    async def questions(self, role_id: uuid.UUID) -> list[SimpleNamespace]:
        mine = [SimpleNamespace(**r) for r in self.rows.values() if r["role_id"] == role_id]
        return sorted(mine, key=lambda q: (q.criterion_id, q.position))

    async def question(self, question_id: uuid.UUID) -> QuestionRef | None:
        row = self.rows.get(question_id)
        return None if row is None else QuestionRef(question_id, uuid.UUID(str(row["role_id"])))

    async def update_question(
        self,
        question_id: uuid.UUID,
        *,
        question_text: str | None,
        strong_answer: str | None,
        weak_answer: str | None,
        position: int | None,
    ) -> SimpleNamespace | None:
        row = self.rows.get(question_id)
        if row is None:
            return None
        changes = {
            "question_text": question_text,
            "strong_answer": strong_answer,
            "weak_answer": weak_answer,
            "position": position,
        }
        row.update({k: v for k, v in changes.items() if v is not None})
        return SimpleNamespace(**row)

    async def delete_question(self, question_id: uuid.UUID) -> bool:
        return self.rows.pop(question_id, None) is not None

    def _open(self, kind: str, role_id: uuid.UUID, question_id: uuid.UUID | None) -> bool:
        return any(j[:3] == (kind, role_id, question_id) for j in self.jobs)

    async def enqueue_generate_kit(self, role_id: uuid.UUID, version: int) -> int | None:
        if self._open("generate_kit", role_id, None):
            return None
        self.jobs.append(("generate_kit", role_id, None, version))
        return len(self.jobs)

    async def enqueue_regenerate(
        self, role_id: uuid.UUID, question_id: uuid.UUID, version: int
    ) -> int | None:
        if self._open("regenerate_question", role_id, question_id):
            return None
        self.jobs.append(("regenerate_question", role_id, question_id, version))
        return len(self.jobs)


class FakeFeedback:
    """Feedback rows, assignments and audit events in memory."""

    def __init__(self) -> None:
        self.role_of: dict[uuid.UUID, uuid.UUID] = {}  # candidate -> role
        self.assigned: set[tuple[uuid.UUID, uuid.UUID]] = set()  # (candidate, user)
        self.stored: list[tuple[uuid.UUID, StoredFeedback]] = []  # (candidate, row)
        self.audit: list[dict[str, object]] = []

    def candidate(self, role_id: uuid.UUID, *assign: uuid.UUID) -> uuid.UUID:
        candidate_id = uuid.uuid4()
        self.role_of[candidate_id] = role_id
        self.assigned |= {(candidate_id, u) for u in assign}
        return candidate_id

    def seed(
        self,
        candidate_id: uuid.UUID,
        interviewer_id: uuid.UUID,
        criterion_id: uuid.UUID,
        *,
        score: int = 3,
        comment: str = "Solid",
        locked: bool = True,
    ) -> None:
        row = StoredFeedback(interviewer_id, criterion_id, score, comment, locked, "Python")
        self.stored.append((candidate_id, row))

    async def candidate_role(self, candidate_id: uuid.UUID) -> uuid.UUID | None:
        return self.role_of.get(candidate_id)

    async def is_assigned(self, candidate_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return (candidate_id, user_id) in self.assigned

    async def rows(
        self, candidate_id: uuid.UUID, interviewer_id: uuid.UUID | None
    ) -> list[StoredFeedback]:
        return [
            r
            for c, r in self.stored
            if c == candidate_id and interviewer_id in (None, r.interviewer_id)
        ]

    async def insert_all(
        self,
        candidate_id: uuid.UUID,
        interviewer_id: uuid.UUID,
        items: list[tuple[uuid.UUID, int, str]],
    ) -> bool:
        if (candidate_id, interviewer_id) not in self.assigned:
            return False
        if await self.rows(candidate_id, interviewer_id):
            raise FeedbackLockedError("feedback is already submitted")
        for criterion_id, score, comment in items:
            self.seed(candidate_id, interviewer_id, criterion_id, score=score, comment=comment)
        return True

    async def save_edit(
        self,
        candidate_id: uuid.UUID,
        interviewer_id: uuid.UUID,
        before: list[StoredFeedback],
        items: dict[uuid.UUID, tuple[int, str]],
    ) -> None:
        for old in before:
            score, comment = items[old.criterion_id]
            self.stored.remove((candidate_id, old))
            self.seed(candidate_id, interviewer_id, old.criterion_id, score=score, comment=comment)
            if (score, comment) != (old.score, old.comment):
                self.audit.append(
                    {"kind": "feedback_edited", "old_score": old.score, "old_comment": old.comment}
                )

    async def unlock(
        self, candidate_id: uuid.UUID, interviewer_id: uuid.UUID, actor_id: uuid.UUID
    ) -> None:
        rows = [
            (c, r)
            for c, r in self.stored
            if c == candidate_id and r.interviewer_id == interviewer_id
        ]
        if any(r.locked for _, r in rows):
            for entry in rows:
                self.stored.remove(entry)
                self.stored.append((entry[0], replace(entry[1], locked=False)))
            self.audit.append({"kind": "feedback_edit_approved", "actor": actor_id})


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
