"""Read side of candidates: the ranked list, the detail and the resume texts (api-lld Q8 to Q10).

Every query is parameterised, names its columns and is bounded. A query that returns candidate
data for one candidate takes a `Viewer`; an interviewer's predicate is in the SQL itself.
The ranked list is one statement, so its rows, totals and page count agree.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.visibility import Viewer


class CellRow(BaseModel):
    """One live criterion's score at the candidate's latest scored version."""

    criterion_id: uuid.UUID
    criterion_name: str
    kind: str
    status: str
    model_score: int | None
    override_score: int | None
    quote: str | None
    flag_reason: str | None
    override_note: str | None
    stale: bool


@dataclass(frozen=True, slots=True)
class RankedRow:
    id: uuid.UUID
    candidate_no: int
    stage: str
    processing_status: str
    failure_reason: str | None
    duplicate_of_candidate_no: int | None
    total: Decimal
    must_have_covered: int
    must_have_total: int
    stale: bool
    cells: list[CellRow]


@dataclass(frozen=True, slots=True)
class RankedPage:
    rows: list[RankedRow]
    total: int


@dataclass(frozen=True, slots=True)
class CandidateRow:
    id: uuid.UUID
    candidate_no: int
    role_id: uuid.UUID
    stage: str
    processing_status: str


@dataclass(frozen=True, slots=True)
class AuditRow:
    id: int
    kind: str
    actor_id: uuid.UUID
    criterion_name: str | None
    old_score: int | None
    new_score: int | None
    from_stage: str | None
    to_stage: str | None
    note: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TextRow:
    raw_text: str
    anonymized_text: str


_CELLS = TypeAdapter(list[CellRow])

# Q8. A candidate's scores are those of its newest scored criteria version; a failed criterion
# counts 0; retired criteria are not shown. Unscored candidates are kept (LEFT JOIN) with total 0.
_RANKED: Final = text("""
WITH cand AS (
    SELECT c.id, c.candidate_no, c.stage, c.processing_status, c.failure_reason, c.duplicate_of_id
    FROM candidates c
    WHERE c.role_id = :role_id AND (CAST(:stage AS candidate_stage) IS NULL OR c.stage = :stage)
), latest AS (
    SELECT s.candidate_id, max(s.criteria_version) AS version
    FROM scores s JOIN cand ON cand.id = s.candidate_id
    GROUP BY s.candidate_id
), cells AS (
    SELECT s.candidate_id, s.criterion_id, k.name, k.kind, k.weight, k.position, s.status,
           s.model_score, s.override_score, s.quote, s.flag_reason, s.override_note,
           s.criteria_version < r.criteria_version AS stale,
           coalesce(s.override_score, s.model_score, 0) AS effective
    FROM scores s
    JOIN latest l ON l.candidate_id = s.candidate_id AND l.version = s.criteria_version
    JOIN criteria k ON k.id = s.criterion_id AND k.retired_at IS NULL
    JOIN roles r ON r.id = :role_id
), agg AS (
    SELECT candidate_id,
           sum(effective * weight) AS total,
           count(*) FILTER (WHERE kind = 'must_have' AND status = 'scored') AS covered,
           bool_or(stale) AS stale,
           max(CASE WHEN criterion_id = CAST(:sort AS uuid) THEN effective END) AS sort_effective,
           jsonb_agg(jsonb_build_object(
               'criterion_id', criterion_id, 'criterion_name', name, 'kind', kind,
               'status', status, 'model_score', model_score, 'override_score', override_score,
               'quote', quote, 'flag_reason', flag_reason, 'override_note', override_note,
               'stale', stale) ORDER BY position, criterion_id) AS cells
    FROM cells GROUP BY candidate_id
)
SELECT cand.id, cand.candidate_no, cand.stage, cand.processing_status, cand.failure_reason,
       dup.candidate_no AS duplicate_of_candidate_no,
       coalesce(agg.total, 0) AS total,
       coalesce(agg.covered, 0) AS must_have_covered,
       (SELECT count(*) FROM criteria
        WHERE role_id = :role_id AND retired_at IS NULL AND kind = 'must_have') AS must_have_total,
       coalesce(agg.stale, false) AS stale,
       coalesce(agg.cells, '[]'::jsonb) AS cells,
       count(*) OVER () AS page_total
FROM cand
LEFT JOIN agg ON agg.candidate_id = cand.id
LEFT JOIN candidates dup ON dup.id = cand.duplicate_of_id
ORDER BY CASE WHEN CAST(:sort AS uuid) IS NULL THEN 0
              ELSE coalesce(agg.sort_effective, -1) END DESC,
         coalesce(agg.total, 0) DESC, cand.candidate_no
LIMIT :limit OFFSET :offset
""")

_COUNT: Final = text(
    "SELECT count(*) FROM candidates "
    "WHERE role_id = :role_id AND (CAST(:stage AS candidate_stage) IS NULL OR stage = :stage)"
)

# Q10. The interviewer predicate is part of the statement: an unassigned candidate returns no row.
_CANDIDATE: Final = text("""
SELECT c.id, c.candidate_no, c.role_id, c.stage, c.processing_status
FROM candidates c
WHERE c.id = :candidate_id
  AND (:is_recruiter OR EXISTS (
        SELECT 1 FROM assignments a WHERE a.candidate_id = c.id AND a.user_id = :viewer_id))
""")

# `:evidence` is false for an interviewer: quote, flag reason and note are never returned to them.
_DETAIL_CELLS: Final = text("""
SELECT s.criterion_id, k.name AS criterion_name, k.kind, s.status, s.model_score,
       s.override_score,
       CASE WHEN :evidence THEN s.quote END AS quote,
       CASE WHEN :evidence THEN s.flag_reason END AS flag_reason,
       CASE WHEN :evidence THEN s.override_note END AS override_note,
       s.criteria_version < r.criteria_version AS stale
FROM scores s
JOIN criteria k ON k.id = s.criterion_id AND k.retired_at IS NULL
JOIN candidates c ON c.id = s.candidate_id
JOIN roles r ON r.id = c.role_id
WHERE s.candidate_id = :candidate_id
  AND s.criteria_version =
      (SELECT max(criteria_version) FROM scores WHERE candidate_id = :candidate_id)
ORDER BY k.position, k.id
""")

_AUDIT: Final = text("""
SELECT id, kind, actor_id, criterion_name, old_score, new_score, from_stage, to_stage, note,
       created_at
FROM audit_events WHERE candidate_id = :candidate_id
ORDER BY created_at DESC, id DESC
LIMIT :limit
""")

_SUBMITTED: Final = text(
    "SELECT EXISTS (SELECT 1 FROM feedback WHERE candidate_id = :candidate_id "
    "AND interviewer_id = :viewer_id)"
)

_TEXTS: Final = text("""
SELECT raw.raw_text, anon.anonymized_text
FROM resume_raw_texts raw JOIN resume_texts anon ON anon.candidate_id = raw.candidate_id
WHERE raw.candidate_id = :candidate_id
""")


class CandidateRepository:
    """Ranked list, detail, audit history and resume texts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def role_exists(self, role_id: uuid.UUID) -> bool:
        """True when the role row exists."""
        result = await self._session.execute(
            text("SELECT EXISTS (SELECT 1 FROM roles WHERE id = :id)"), {"id": role_id}
        )
        return bool(result.scalar_one())

    async def ranked(
        self,
        role_id: uuid.UUID,
        stage: str | None,
        sort_criterion: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> RankedPage:
        """One page of the role's candidates, best first; `total` counts the whole filter."""
        params = {
            "role_id": role_id,
            "stage": stage,
            "sort": sort_criterion,
            "limit": limit,
            "offset": offset,
        }
        found = (await self._session.execute(_RANKED, params)).mappings().all()
        if found:
            total = int(found[0]["page_total"])
        elif offset == 0:
            total = 0
        else:  # a page past the end: the window count has no row to ride on
            counted = await self._session.execute(_COUNT, {"role_id": role_id, "stage": stage})
            total = int(counted.scalar_one())
        rows = [
            RankedRow(
                id=r["id"],
                candidate_no=r["candidate_no"],
                stage=r["stage"],
                processing_status=r["processing_status"],
                failure_reason=r["failure_reason"],
                duplicate_of_candidate_no=r["duplicate_of_candidate_no"],
                total=r["total"],
                must_have_covered=r["must_have_covered"],
                must_have_total=r["must_have_total"],
                stale=r["stale"],
                cells=_CELLS.validate_python(r["cells"]),
            )
            for r in found
        ]
        return RankedPage(rows, total)

    async def get(self, candidate_id: uuid.UUID, viewer: Viewer) -> CandidateRow | None:
        """The candidate, or None when it does not exist or the viewer may not see it."""
        result = await self._session.execute(
            _CANDIDATE,
            {
                "candidate_id": candidate_id,
                "is_recruiter": viewer.is_recruiter,
                "viewer_id": viewer.user_id,
            },
        )
        row = result.mappings().first()
        return None if row is None else CandidateRow(**row)

    async def cells(self, candidate_id: uuid.UUID, viewer: Viewer) -> list[CellRow]:
        """The candidate's score cells; evidence columns only for a recruiter."""
        result = await self._session.execute(
            _DETAIL_CELLS, {"candidate_id": candidate_id, "evidence": viewer.is_recruiter}
        )
        return [CellRow(**r) for r in result.mappings()]

    async def audit(self, candidate_id: uuid.UUID, limit: int) -> list[AuditRow]:
        """The candidate's history, newest first. Recruiter callers only."""
        result = await self._session.execute(_AUDIT, {"candidate_id": candidate_id, "limit": limit})
        return [AuditRow(**r) for r in result.mappings()]

    async def has_submitted(self, candidate_id: uuid.UUID, viewer: Viewer) -> bool:
        """Q12: has this viewer submitted feedback on the candidate."""
        result = await self._session.execute(
            _SUBMITTED, {"candidate_id": candidate_id, "viewer_id": viewer.user_id}
        )
        return bool(result.scalar_one())

    async def texts(self, candidate_id: uuid.UUID) -> TextRow | None:
        """Raw and anonymized text; None until the worker has stored both."""
        result = await self._session.execute(_TEXTS, {"candidate_id": candidate_id})
        row = result.mappings().first()
        return None if row is None else TextRow(**row)
