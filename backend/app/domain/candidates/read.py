"""Reading candidates: the ranked list, the detail and the resume texts.

Nothing here writes. A recruiter sees everything; an interviewer sees an assigned candidate's
number and, only after submitting feedback, score values without quote, flag reason or note.
A candidate an interviewer is not assigned to is `not_found`, the same as one that does not exist.
"""

import uuid
from typing import Final

from app.api.candidates.schemas import (
    AuditEvent,
    CandidateDetail,
    CandidateText,
    Page,
    RankedCandidate,
    RankedList,
    ScoreCell,
)
from app.core.errors import NotFoundError, ValidationFailedError
from app.db.models import User
from app.db.repositories.candidates import CandidateRepository, CellRow
from app.db.repositories.criteria import CriteriaRepository
from app.domain.visibility import Viewer

AUDIT_LIMIT: Final = 200  # a candidate has a handful of events; the bound is a backstop


def viewer_of(user: User) -> Viewer:
    """The session user as a `Viewer`."""
    return Viewer(user.id, "recruiter" if user.role == "recruiter" else "interviewer")


def _source(cell: CellRow) -> str:
    if cell.override_score is not None:
        return "recruiter_override"
    return {"scored": "model_suggestion", "no_evidence": "no_evidence_found"}.get(
        cell.status, "failed"
    )


def _cell(cell: CellRow) -> ScoreCell:
    return ScoreCell.model_validate({**cell.model_dump(), "source": _source(cell)})


async def ranked_list(
    candidates: CandidateRepository,
    criteria: CriteriaRepository,
    role_id: uuid.UUID,
    stage: str | None,
    sort: str,
    limit: int,
    offset: int,
) -> RankedList:
    """Every candidate of the role, best first; `sort` is `total` or a live criterion id."""
    if not await candidates.role_exists(role_id):
        raise NotFoundError("role not found")
    sort_criterion: uuid.UUID | None = None
    if sort != "total":
        try:
            sort_criterion = uuid.UUID(sort)
        except ValueError:
            sort_criterion = None
        if sort_criterion is None or sort_criterion not in {
            c.id for c in await criteria.live(role_id)
        }:
            raise ValidationFailedError(
                "request failed validation",
                details={
                    "errors": [
                        {
                            "loc": ["query", "sort"],
                            "msg": "use total or the id of a criterion of this role",
                            "type": "value_error",
                        }
                    ]
                },
            )
    page = await candidates.ranked(role_id, stage, sort_criterion, limit, offset)
    return RankedList(
        data=[
            RankedCandidate.model_validate(
                {
                    "id": r.id,
                    "candidate_no": r.candidate_no,
                    "stage": r.stage,
                    "processing_status": r.processing_status,
                    "failure_reason": r.failure_reason,
                    "total": float(r.total),
                    "must_have_covered": r.must_have_covered,
                    "must_have_total": r.must_have_total,
                    "stale": r.stale,
                    "duplicate_of_candidate_no": r.duplicate_of_candidate_no,
                    "scores": [_cell(c) for c in r.cells],
                }
            )
            for r in page.rows
        ],
        page=Page(limit=limit, offset=offset, total=page.total),
    )


async def detail(
    candidates: CandidateRepository, user: User, candidate_id: uuid.UUID
) -> CandidateDetail:
    """One candidate as this viewer may see it."""
    viewer = viewer_of(user)
    row = await candidates.get(candidate_id, viewer)
    if row is None:
        raise NotFoundError("candidate not found")
    if viewer.is_recruiter:
        cells = await candidates.cells(candidate_id, viewer)
        events = await candidates.audit(candidate_id, AUDIT_LIMIT)
        return CandidateDetail.model_validate(
            {
                "id": row.id,
                "candidate_no": row.candidate_no,
                "role_id": row.role_id,
                "stage": row.stage,
                "processing_status": row.processing_status,
                "scores": [_cell(c) for c in cells],
                "audit": [AuditEvent.model_validate(e, from_attributes=True) for e in events],
            }
        )
    submitted = await candidates.has_submitted(candidate_id, viewer)
    view = {
        "id": row.id,
        "candidate_no": row.candidate_no,
        "role_id": row.role_id,
        "has_submitted": submitted,
    }
    if submitted:  # a field left out stays unset, so the route drops it instead of sending null
        view["scores"] = [_cell(c) for c in await candidates.cells(candidate_id, viewer)]
    return CandidateDetail.model_validate(view)


async def resume_text(candidates: CandidateRepository, candidate_id: uuid.UUID) -> CandidateText:
    """Raw and anonymized text; recruiters only (the route enforces the role)."""
    texts = await candidates.texts(candidate_id)
    if texts is None:
        raise NotFoundError("resume text not found")
    return CandidateText(raw_text=texts.raw_text, anonymized_text=texts.anonymized_text)
