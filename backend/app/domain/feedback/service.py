"""Interviewer feedback: submit, read, approve an edit, save the edit.

An interviewer acts only on candidates assigned to them; any other candidate is a 404, the same as
an unknown one. The service owns every transaction.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.feedback.schemas import FeedbackItem, FeedbackList, FeedbackRow, FeedbackSubmit
from app.core.errors import FeedbackLockedError, IncompleteFeedbackError, NotFoundError
from app.db.models import User
from app.db.repositories.criteria import CriteriaRepository
from app.db.repositories.feedback import FeedbackRepository, StoredFeedback

_MISSING = "candidate not found"


def _out(rows: list[StoredFeedback]) -> FeedbackList:
    return FeedbackList(
        data=[
            FeedbackRow(
                interviewer_id=r.interviewer_id,
                criterion_id=r.criterion_id,
                score=r.score,
                comment=r.comment,
                locked=r.locked,
            )
            for r in rows
        ]
    )


def check_complete(
    items: list[FeedbackItem], live_ids: set[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, str]]:
    """Exactly one scored and commented item per live criterion, else `incomplete_feedback`."""
    chosen: dict[uuid.UUID, tuple[int, str]] = {}
    for item in items:
        if item.criterion_id not in live_ids:
            raise IncompleteFeedbackError("an item names a criterion this role does not have")
        if item.criterion_id in chosen:
            raise IncompleteFeedbackError("a criterion appears twice")
        if not item.comment.strip():
            raise IncompleteFeedbackError("every criterion needs a comment")
        chosen[item.criterion_id] = (item.score, item.comment)
    if chosen.keys() != live_ids:
        raise IncompleteFeedbackError("every criterion needs a score and a comment")
    return chosen


async def _assigned_role(
    feedback: FeedbackRepository, user: User, candidate_id: uuid.UUID
) -> uuid.UUID:
    """The candidate's role when the interviewer is assigned; otherwise a 404."""
    role_id = await feedback.candidate_role(candidate_id)
    if role_id is None or not await feedback.is_assigned(candidate_id, user.id):
        raise NotFoundError(_MISSING)
    return role_id


async def _live_ids(criteria: CriteriaRepository, role_id: uuid.UUID) -> set[uuid.UUID]:
    return {c.id for c in await criteria.live(role_id)}


async def submit(
    db: AsyncSession,
    feedback: FeedbackRepository,
    criteria: CriteriaRepository,
    user: User,
    candidate_id: uuid.UUID,
    body: FeedbackSubmit,
) -> FeedbackList:
    """Insert one locked row per live criterion; a second submit is `feedback_locked`."""
    role_id = await _assigned_role(feedback, user, candidate_id)
    if await feedback.rows(candidate_id, user.id):
        raise FeedbackLockedError("feedback is already submitted")
    chosen = check_complete(body.items, await _live_ids(criteria, role_id))
    await db.commit()  # ends the read transaction the checks opened
    async with db.begin():
        stored = await feedback.insert_all(
            candidate_id, user.id, [(k, s, c) for k, (s, c) in chosen.items()]
        )
        if not stored:
            raise NotFoundError(_MISSING)
    return _out(await feedback.rows(candidate_id, user.id))


async def read(feedback: FeedbackRepository, user: User, candidate_id: uuid.UUID) -> FeedbackList:
    """A recruiter reads every interviewer's rows; an interviewer reads their own."""
    if user.role == "interviewer":
        await _assigned_role(feedback, user, candidate_id)
        return _out(await feedback.rows(candidate_id, user.id))
    if await feedback.candidate_role(candidate_id) is None:
        raise NotFoundError(_MISSING)
    return _out(await feedback.rows(candidate_id, None))


async def approve_edit(
    db: AsyncSession,
    feedback: FeedbackRepository,
    recruiter: User,
    candidate_id: uuid.UUID,
    interviewer_id: uuid.UUID,
) -> FeedbackList:
    """Unlock one interviewer's rows for one edit; 404 when they have submitted nothing."""
    if not await feedback.rows(candidate_id, interviewer_id):
        raise NotFoundError("feedback not found")
    await db.commit()
    async with db.begin():
        await feedback.unlock(candidate_id, interviewer_id, recruiter.id)
    return _out(await feedback.rows(candidate_id, interviewer_id))


async def edit(
    db: AsyncSession,
    feedback: FeedbackRepository,
    criteria: CriteriaRepository,
    user: User,
    candidate_id: uuid.UUID,
    body: FeedbackSubmit,
) -> FeedbackList:
    """Save an approved edit and lock again; locked rows are `feedback_locked`."""
    role_id = await _assigned_role(feedback, user, candidate_id)
    before = await feedback.rows(candidate_id, user.id)
    if not before:
        raise NotFoundError("feedback not found")
    if any(r.locked for r in before):
        raise FeedbackLockedError("feedback is locked; a recruiter must approve an edit")
    chosen = check_complete(body.items, await _live_ids(criteria, role_id))
    if chosen.keys() != {r.criterion_id for r in before}:
        raise IncompleteFeedbackError("an edit covers the criteria that were submitted")
    await db.commit()
    async with db.begin():
        await feedback.save_edit(candidate_id, user.id, before, chosen)
    return _out(await feedback.rows(candidate_id, user.id))
