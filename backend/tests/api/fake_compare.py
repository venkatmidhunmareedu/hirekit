"""In-memory stand-in for the compare repository; the SQL itself is tested against Postgres."""

import uuid

from app.db.repositories.compare import CandidateRef, FeedbackCell, ScoreCell
from app.domain.visibility import Viewer


class FakeCompare:
    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, CandidateRef] = {}
        self.assigned: set[tuple[uuid.UUID, uuid.UUID]] = set()  # (candidate_id, user_id)
        self.score_rows: list[ScoreCell] = []
        self.feedback_rows: list[FeedbackCell] = []
        self._numbers = iter(range(1, 100))

    def seed(self, role_id: uuid.UUID) -> uuid.UUID:
        ref = CandidateRef(uuid.uuid4(), next(self._numbers), role_id)
        self.rows[ref.id] = ref
        return ref.id

    async def candidates(self, viewer: Viewer, ids: list[uuid.UUID]) -> list[CandidateRef]:
        return [
            r
            for i, r in self.rows.items()
            if i in ids and (not viewer.is_interviewer or (i, viewer.user_id) in self.assigned)
        ]

    async def scores(self, viewer: Viewer, ids: list[uuid.UUID]) -> list[ScoreCell]:
        return [s for s in self.score_rows if s.candidate_id in ids]

    async def feedback(self, viewer: Viewer, ids: list[uuid.UUID]) -> list[FeedbackCell]:
        return [f for f in self.feedback_rows if f.candidate_id in ids]
