"""In-memory stand-in for the candidate read repository (HK-59)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.db.repositories.candidates import (
    AuditRow,
    CandidateRow,
    CellRow,
    RankedPage,
    RankedRow,
    TextRow,
)
from app.domain.visibility import Viewer


def cell(
    name: str = "Python",
    *,
    status: str = "scored",
    model: int | None = 3,
    override: int | None = None,
    stale: bool = False,
    evidence: bool = True,
) -> CellRow:
    return CellRow(
        criterion_id=uuid.uuid4(),
        criterion_name=name,
        kind="must_have",
        status=status,
        model_score=model,
        override_score=override,
        quote="Built a payments service." if evidence else None,
        flag_reason="not found" if evidence and status == "failed" else None,
        override_note="Strong referee call." if evidence and override is not None else None,
        stale=stale,
    )


class FakeCandidates:
    """`permissive` shows every id to every viewer: the permission matrix only checks roles."""

    def __init__(self, *, permissive: bool = False) -> None:
        self.permissive = permissive
        self.rows: dict[uuid.UUID, CandidateRow] = {}
        self.assigned: set[tuple[uuid.UUID, uuid.UUID]] = set()  # (candidate_id, user_id)
        self.submitted: set[tuple[uuid.UUID, uuid.UUID]] = set()
        self.score_cells: list[CellRow] = []
        self.texts_by_id: dict[uuid.UUID, TextRow] = {}
        self.roles: set[uuid.UUID] = set()
        self.ranked_calls: list[tuple[str | None, uuid.UUID | None, int, int]] = []
        self.page: RankedPage = RankedPage([], 0)

    def seed(self, role_id: uuid.UUID, *, candidate_no: int = 14) -> CandidateRow:
        row = CandidateRow(uuid.uuid4(), candidate_no, role_id, "screened", "done")
        self.rows[row.id] = row
        self.roles.add(role_id)
        return row

    def ranked_row(self, no: int, *cells: CellRow) -> RankedRow:
        return RankedRow(
            id=uuid.uuid4(),
            candidate_no=no,
            stage="new",
            processing_status="done",
            failure_reason=None,
            duplicate_of_candidate_no=None,
            total=Decimal("11.5"),
            must_have_covered=1,
            must_have_total=2,
            stale=any(c.stale for c in cells),
            cells=list(cells),
        )

    async def role_exists(self, role_id: uuid.UUID) -> bool:
        return self.permissive or role_id in self.roles

    async def ranked(
        self,
        role_id: uuid.UUID,
        stage: str | None,
        sort_criterion: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> RankedPage:
        self.ranked_calls.append((stage, sort_criterion, limit, offset))
        return self.page

    async def get(self, candidate_id: uuid.UUID, viewer: Viewer) -> CandidateRow | None:
        row = self.rows.get(candidate_id) or (
            CandidateRow(candidate_id, 1, uuid.uuid4(), "new", "done") if self.permissive else None
        )
        if row is None:
            return None
        if (
            viewer.is_recruiter
            or self.permissive
            or (candidate_id, viewer.user_id) in self.assigned
        ):
            return row
        return None

    async def cells(self, candidate_id: uuid.UUID, viewer: Viewer) -> list[CellRow]:
        if viewer.is_recruiter:
            return self.score_cells
        return [
            c.model_copy(update={"quote": None, "flag_reason": None, "override_note": None})
            for c in self.score_cells
        ]

    async def audit(self, candidate_id: uuid.UUID, limit: int) -> list[AuditRow]:
        return [
            AuditRow(
                1,
                "stage_change",
                uuid.uuid4(),
                None,
                None,
                None,
                "new",
                "screened",
                None,
                datetime.now(UTC),
            )
        ]

    async def has_submitted(self, candidate_id: uuid.UUID, viewer: Viewer) -> bool:
        return (candidate_id, viewer.user_id) in self.submitted

    async def texts(self, candidate_id: uuid.UUID) -> TextRow | None:
        if self.permissive:
            return TextRow("Jane Doe. Built.", "Built.")
        return self.texts_by_id.get(candidate_id)
