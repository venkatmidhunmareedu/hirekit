"""In-memory stand-in for the assignment repository."""

import uuid

from app.api.candidates.assignment_schemas import CandidateAssignment, MyCandidate
from tests.api.fakes import FakeUsers


class FakeAssignments:
    """Candidates and (candidate, user) pairs; roles come from the users fake."""

    def __init__(self, users: FakeUsers) -> None:
        self.users = users
        self.candidates: dict[uuid.UUID, MyCandidate] = {}
        self.pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.submitted: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.limits: list[int] = []

    def seed_candidate(self, number: int = 1, candidate_id: uuid.UUID | None = None) -> uuid.UUID:
        candidate_id = candidate_id or uuid.uuid4()
        self.candidates[candidate_id] = MyCandidate(
            candidate_id=candidate_id,
            candidate_no=number,
            role_id=uuid.uuid4(),
            role_title="Backend engineer",
            has_submitted=False,
        )
        return candidate_id

    async def candidate_exists(self, candidate_id: uuid.UUID) -> bool:
        return candidate_id in self.candidates

    async def user_role(self, user_id: uuid.UUID) -> str | None:
        user = await self.users.by_id(user_id)
        return None if user is None else user.role

    async def add(self, candidate_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.pairs.add((candidate_id, user_id))

    async def remove(self, candidate_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.pairs.discard((candidate_id, user_id))

    async def for_interviewer(self, user_id: uuid.UUID, limit: int) -> list[MyCandidate]:
        self.limits.append(limit)
        mine = [c for c in self.candidates.values() if (c.candidate_id, user_id) in self.pairs]
        return [
            c.model_copy(update={"has_submitted": (c.candidate_id, user_id) in self.submitted})
            for c in sorted(mine, key=lambda c: c.candidate_no)[:limit]
        ]

    async def for_candidate(self, candidate_id: uuid.UUID) -> list[CandidateAssignment]:
        found: list[CandidateAssignment] = []
        for cid, uid in self.pairs:
            user = await self.users.by_id(uid)
            if cid == candidate_id and user is not None:
                found.append(CandidateAssignment(user_id=uid, name=user.name))
        return sorted(found, key=lambda a: (a.name, a.user_id))
