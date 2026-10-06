"""In-memory decision and audit repositories for the override, stage and reveal tests."""

import uuid
from dataclasses import dataclass, field

from app.db.repositories.decisions import CandidateRow, CriterionRow, ScoreRow


@dataclass
class FakeScore:
    row: ScoreRow
    note: str | None = None
    by: uuid.UUID | None = None


@dataclass
class FakeDecisions:
    role_version: dict[uuid.UUID, int] = field(default_factory=dict)
    candidates: dict[uuid.UUID, CandidateRow] = field(default_factory=dict)
    criteria: dict[tuple[uuid.UUID, uuid.UUID], CriterionRow] = field(default_factory=dict)
    scores: dict[tuple[uuid.UUID, uuid.UUID, int], FakeScore] = field(default_factory=dict)
    stage_writes: list[tuple[uuid.UUID, str]] = field(default_factory=list)

    def seed(
        self,
        *,
        version: int = 1,
        stage: str = "new",
        status: str = "scored",
        model_score: int | None = 3,
    ) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        """A role, a candidate with an identity and one criterion: (role, candidate, criterion)."""
        role_id, candidate_id, criterion_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.role_version[role_id] = version
        self.candidates[candidate_id] = CandidateRow(role_id, stage, "Jane_Doe_CV.pdf", "Jane Doe")
        self.criteria[(role_id, criterion_id)] = CriterionRow("Python", "must_have")
        quote = "Built a payments service" if status == "scored" else None
        self.scores[(candidate_id, criterion_id, version)] = FakeScore(
            ScoreRow(status, model_score, quote, None, None)
        )
        return role_id, candidate_id, criterion_id

    async def role_of(self, candidate_id: uuid.UUID) -> uuid.UUID | None:
        row = self.candidates.get(candidate_id)
        return None if row is None else row.role_id

    async def lock_role_version(self, role_id: uuid.UUID) -> int | None:
        return self.role_version.get(role_id)

    async def lock_candidate(self, candidate_id: uuid.UUID) -> CandidateRow | None:
        return self.candidates.get(candidate_id)

    async def criterion(self, role_id: uuid.UUID, criterion_id: uuid.UUID) -> CriterionRow | None:
        return self.criteria.get((role_id, criterion_id))

    async def lock_score(
        self, candidate_id: uuid.UUID, criterion_id: uuid.UUID, version: int
    ) -> ScoreRow | None:
        found = self.scores.get((candidate_id, criterion_id, version))
        return None if found is None else found.row

    async def write_override(
        self,
        candidate_id: uuid.UUID,
        criterion_id: uuid.UUID,
        version: int,
        score: int,
        note: str,
        user_id: uuid.UUID,
    ) -> None:
        found = self.scores[(candidate_id, criterion_id, version)]
        found.row = ScoreRow(
            found.row.status, found.row.model_score, found.row.quote, found.row.flag_reason, score
        )
        found.note, found.by = note, user_id

    async def write_stage(self, candidate_id: uuid.UUID, stage: str) -> None:
        old = self.candidates[candidate_id]
        self.candidates[candidate_id] = CandidateRow(
            old.role_id, stage, old.file_name, old.identity_name
        )
        self.stage_writes.append((candidate_id, stage))


@dataclass
class FakeAudit:
    events: list[dict[str, object]] = field(default_factory=list)

    async def score_override(
        self,
        candidate_id: uuid.UUID,
        actor_id: uuid.UUID,
        criterion_name: str,
        old_score: int | None,
        new_score: int,
        note: str,
    ) -> None:
        self.events.append(
            {
                "kind": "score_override",
                "candidate": candidate_id,
                "actor": actor_id,
                "criterion": criterion_name,
                "old": old_score,
                "new": new_score,
                "note": note,
            }
        )

    async def stage_change(
        self,
        candidate_id: uuid.UUID,
        actor_id: uuid.UUID,
        from_stage: str,
        to_stage: str,
        note: str | None,
    ) -> None:
        self.events.append(
            {
                "kind": "stage_change",
                "candidate": candidate_id,
                "actor": actor_id,
                "from": from_stage,
                "to": to_stage,
                "note": note,
            }
        )

    async def identity_reveal(self, candidate_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        self.events.append(
            {"kind": "identity_reveal", "candidate": candidate_id, "actor": actor_id}
        )
