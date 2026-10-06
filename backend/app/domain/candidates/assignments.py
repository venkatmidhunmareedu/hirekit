"""Assign and unassign interviewers. Only a recruiter reaches these (the route's dependency)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.candidates.assignment_schemas import (
    Assignment,
    CandidateAssignment,
    InterviewerOption,
    MyCandidate,
)
from app.core.errors import NotFoundError, ValidationFailedError
from app.db.repositories.assignments import AssignmentRepository
from app.db.repositories.users import UserRepository


async def assign(
    db: AsyncSession, repo: AssignmentRepository, candidate_id: uuid.UUID, user_id: uuid.UUID
) -> Assignment:
    """Assign an interviewer; the target must be an interviewer, a repeat changes nothing."""
    await db.commit()  # ends the read transaction the auth check opened
    async with db.begin():
        if not await repo.candidate_exists(candidate_id):
            raise NotFoundError("candidate not found")
        if await repo.user_role(user_id) != "interviewer":
            raise ValidationFailedError(
                "request failed validation",
                details={
                    "errors": [
                        {
                            "loc": ["body", "user_id"],
                            "msg": "must be an interviewer",
                            "type": "value_error",
                        }
                    ]
                },
            )
        await repo.add(candidate_id, user_id)
    return Assignment(candidate_id=candidate_id, user_id=user_id)


async def unassign(
    db: AsyncSession, repo: AssignmentRepository, candidate_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Remove the assignment; a repeat is a no-op, an unknown candidate is 404."""
    await db.commit()
    async with db.begin():
        if not await repo.candidate_exists(candidate_id):
            raise NotFoundError("candidate not found")
        await repo.remove(candidate_id, user_id)


async def my_candidates(
    repo: AssignmentRepository, user_id: uuid.UUID, limit: int
) -> list[MyCandidate]:
    """The caller's own assigned candidates."""
    return await repo.for_interviewer(user_id, limit)


async def list_interviewers(users: UserRepository, limit: int) -> list[InterviewerOption]:
    """Interviewers a recruiter can assign, by name."""
    return await users.list_by_role("interviewer", limit)


async def list_for_candidate(
    repo: AssignmentRepository, candidate_id: uuid.UUID
) -> list[CandidateAssignment]:
    """The candidate's assigned interviewers; an unknown candidate is 404."""
    if not await repo.candidate_exists(candidate_id):
        raise NotFoundError("candidate not found")
    return await repo.for_candidate(candidate_id)
