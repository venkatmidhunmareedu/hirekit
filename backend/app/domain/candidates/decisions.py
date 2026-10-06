"""Recruiter decisions on a candidate: override a score, change the stage, reveal the identity.

Nothing else in the Api moves a candidate or changes a score (tenet 4). Each decision is one
transaction: lock, change, audit row. Each commits the read the auth check opened, then runs in
one `db.begin()` block, like the roles service.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.candidates.decision_schemas import (
    Identity,
    OverrideRequest,
    ScoreCell,
    StageChanged,
    StageRequest,
)
from app.core.errors import NotFoundError, SameStageError, ScoresStaleError
from app.db.models import User
from app.db.repositories.audit import AuditRepository
from app.db.repositories.decisions import DecisionRepository

_NO_CANDIDATE = "candidate not found"


async def override_score(
    db: AsyncSession,
    decisions: DecisionRepository,
    audit: AuditRepository,
    user: User,
    candidate_id: uuid.UUID,
    criterion_id: uuid.UUID,
    body: OverrideRequest,
) -> ScoreCell:
    """Set the override on the score of the role's current criteria version; keep the model's."""
    await db.commit()
    role_id = await decisions.role_of(candidate_id)
    if role_id is None:
        raise NotFoundError(_NO_CANDIDATE)
    await db.commit()  # the unlocked read opened a transaction; the locks start a fresh one
    async with db.begin():
        version = await decisions.lock_role_version(role_id)  # roles before candidates
        if version is None or await decisions.lock_candidate(candidate_id) is None:
            raise NotFoundError(_NO_CANDIDATE)
        criterion = await decisions.criterion(role_id, criterion_id)
        if criterion is None:
            raise NotFoundError("criterion not found")
        score = await decisions.lock_score(candidate_id, criterion_id, version)
        if score is None:
            raise ScoresStaleError("the criteria changed; wait for the new scores")
        await decisions.write_override(
            candidate_id, criterion_id, version, body.override_score, body.note, user.id
        )
        old = score.override_score if score.override_score is not None else score.model_score
        await audit.score_override(
            candidate_id, user.id, criterion.name, old, body.override_score, body.note
        )
    return ScoreCell.model_validate(
        {
            "criterion_id": criterion_id,
            "criterion_name": criterion.name,
            "kind": criterion.kind,
            "status": score.status,
            "model_score": score.model_score,
            "override_score": body.override_score,
            "source": "recruiter_override",
            "stale": False,
            "quote": score.quote,
            "flag_reason": score.flag_reason,
            "override_note": body.note,
        }
    )


async def change_stage(
    db: AsyncSession,
    decisions: DecisionRepository,
    audit: AuditRepository,
    user: User,
    candidate_id: uuid.UUID,
    body: StageRequest,
) -> StageChanged:
    """Move the candidate and record from, to, who and the reason in the same transaction."""
    await db.commit()
    async with db.begin():
        candidate = await decisions.lock_candidate(candidate_id)
        if candidate is None:
            raise NotFoundError(_NO_CANDIDATE)
        if candidate.stage == body.stage:
            raise SameStageError(f"the candidate is already in {body.stage}")
        await decisions.write_stage(candidate_id, body.stage)
        await audit.stage_change(candidate_id, user.id, candidate.stage, body.stage, body.reason)
    return StageChanged.model_validate(
        {"candidate_id": candidate_id, "from_stage": candidate.stage, "to_stage": body.stage}
    )


async def reveal_identity(
    db: AsyncSession,
    decisions: DecisionRepository,
    audit: AuditRepository,
    user: User,
    candidate_id: uuid.UUID,
) -> Identity:
    """Commit the audit row first; the name is returned only after it is stored."""
    await db.commit()
    async with db.begin():
        candidate = await decisions.lock_candidate(candidate_id)
        if candidate is None:
            raise NotFoundError(_NO_CANDIDATE)
        await audit.identity_reveal(candidate_id, user.id)
    return Identity(identity_name=candidate.identity_name, file_name=candidate.file_name)
