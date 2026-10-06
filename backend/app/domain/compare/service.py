"""The comparison view: two to four candidates of one role, one cell per criterion."""

import uuid
from collections import defaultdict

from app.api.compare.schemas import (
    CompareCandidate,
    CompareCell,
    CompareCriterion,
    CompareFeedback,
    Comparison,
)
from app.core.errors import NoCriteriaError, NotFoundError, ValidationFailedError
from app.db.models import User
from app.db.repositories.compare import CompareRepository
from app.db.repositories.criteria import CriteriaRepository
from app.domain.visibility import Viewer

MIN_CANDIDATES = 2
MAX_CANDIDATES = 4


def parse_ids(raw: str) -> list[uuid.UUID]:
    """Two to four distinct candidate ids, in the order given."""
    try:
        ids = [uuid.UUID(part.strip()) for part in raw.split(",")]
    except ValueError:
        raise ValidationFailedError("ids must be comma separated candidate ids") from None
    if not MIN_CANDIDATES <= len(ids) <= MAX_CANDIDATES or len(set(ids)) != len(ids):
        raise ValidationFailedError(
            f"compare {MIN_CANDIDATES} to {MAX_CANDIDATES} different candidates"
        )
    return ids


def disagrees(scores: list[int]) -> bool:
    """True when the interviewers who scored a criterion did not all give the same score."""
    return len(set(scores)) > 1


async def compare(
    compare_repo: CompareRepository, criteria: CriteriaRepository, user: User, raw_ids: str
) -> Comparison:
    """One unseen id (missing, or unassigned for an interviewer) is a 404 for the whole request."""
    ids = parse_ids(raw_ids)
    viewer = Viewer.of(user)
    found = {c.id: c for c in await compare_repo.candidates(viewer, ids)}
    if len(found) != len(ids):
        raise NotFoundError("candidate not found")
    role_ids = {c.role_id for c in found.values()}
    if len(role_ids) != 1:
        raise ValidationFailedError("compare candidates of one role")
    live = await criteria.live(role_ids.pop())
    if not live:
        raise NoCriteriaError("the role has no criteria to compare on")
    ordered = sorted(live, key=lambda c: c.kind != "must_have")  # stable: position kept in a kind

    scores = {(s.candidate_id, s.criterion_id): s for s in await compare_repo.scores(viewer, ids)}
    feedback: dict[tuple[uuid.UUID, uuid.UUID], list[CompareFeedback]] = defaultdict(list)
    for row in await compare_repo.feedback(viewer, ids):
        feedback[(row.candidate_id, row.criterion_id)].append(
            CompareFeedback(
                interviewer_id=row.interviewer_id,
                criterion_id=row.criterion_id,
                score=row.score,
                comment=row.comment,
                locked=row.locked,
            )
        )

    def cell(candidate_id: uuid.UUID, criterion_id: uuid.UUID) -> CompareCell:
        score = scores.get((candidate_id, criterion_id))
        rows = feedback[(candidate_id, criterion_id)]
        return CompareCell(
            criterion_id=criterion_id,
            model_score=score.model_score if score else None,
            override_score=score.override_score if score else None,
            feedback=rows,
            disagreement=disagrees([r.score for r in rows]),
        )

    return Comparison(
        criteria=[
            CompareCriterion.model_validate({"id": c.id, "name": c.name, "kind": c.kind})
            for c in ordered
        ],
        candidates=[
            CompareCandidate(
                candidate_id=i,
                candidate_no=found[i].candidate_no,
                cells=[cell(i, c.id) for c in ordered],
            )
            for i in ids
        ],
    )
