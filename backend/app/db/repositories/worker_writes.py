"""SQL the handlers use to read inputs and write results (docs/design/worker-lld.md, Q5 to Q11).

Methods take the caller's `AsyncSession` and never commit: `JobContext.fenced()` owns the
transaction and has already locked the role, then the job row (`jobs.fence`), so a Worker that
lost its lease never gets here. A result writer re-reads the role (Q5; the lock is already held)
and returns False, writing nothing, when the role is no longer what the job was enqueued against
(the criteria changed, or the role was re-approved at a new version). Lock order: `roles`,
`jobs`, `candidates`, then `criteria`, `rubric_levels`, `questions`, `scores`. Nothing here
touches `candidates.stage` (tenet 4).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.gateway.text import AnonymizedText
from app.worker.ports import CriterionSpec, ProposedCriterion

_ROLE_SHARED: Final = text("SELECT status, criteria_version FROM roles WHERE id = :id FOR SHARE")
_ROLE_EXCLUSIVE: Final = text(
    "SELECT status, criteria_version FROM roles WHERE id = :id FOR UPDATE"
)


@dataclass(frozen=True, slots=True)
class RoleState:
    """What a result write compares against the job's `criteria_version`."""

    status: str
    criteria_version: int


@dataclass(frozen=True, slots=True)
class StoredFile:
    """The uploaded bytes, held until extraction succeeds (ADR-0008)."""

    media_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class ScoreRow:
    """One score ready to store: the quote was already found in the anonymized text by code."""

    criterion_id: UUID
    status: str
    model_score: int | None
    quote: str | None
    flag_reason: str | None


@dataclass(frozen=True, slots=True)
class NewQuestion:
    """One kit question for one criterion of the role."""

    criterion_id: UUID
    position: int
    question_text: str
    strong_answer: str
    weak_answer: str


async def read_role(
    session: AsyncSession, role_id: UUID, *, exclusive: bool = False
) -> RoleState | None:
    """Q5: lock the role (`FOR SHARE`, or `FOR UPDATE` for propose) and read its state."""
    row = (
        await session.execute(_ROLE_EXCLUSIVE if exclusive else _ROLE_SHARED, {"id": role_id})
    ).first()
    return None if row is None else RoleState(row.status, row.criteria_version)


async def read_criteria(session: AsyncSession, role_id: UUID) -> list[CriterionSpec]:
    """Q6: the role's live criteria in order, each with its rubric levels."""
    criteria = (
        await session.execute(
            text(
                "SELECT id, name, kind, weight, position FROM criteria "
                "WHERE role_id = :role AND retired_at IS NULL ORDER BY position, id"
            ),
            {"role": role_id},
        )
    ).all()
    levels = (
        await session.execute(
            text(
                "SELECT criterion_id, level, descriptor FROM rubric_levels "
                "WHERE criterion_id = ANY(CAST(:ids AS uuid[])) ORDER BY criterion_id, level"
            ),
            {"ids": [c.id for c in criteria]},
        )
    ).all()
    return [
        CriterionSpec(
            c.id,
            c.name,
            c.kind,
            c.weight,
            c.position,
            tuple((r.level, r.descriptor) for r in levels if r.criterion_id == c.id),
        )
        for c in criteria
    ]


async def read_file(session: AsyncSession, candidate_id: UUID) -> StoredFile | None:
    """Q7: the uploaded bytes, or None once they were deleted with the text stored."""
    row = (
        await session.execute(
            text("SELECT media_type, content FROM resume_files WHERE candidate_id = :id"),
            {"id": candidate_id},
        )
    ).first()
    return None if row is None else StoredFile(row.media_type, bytes(row.content))


async def text_exists(session: AsyncSession, candidate_id: UUID) -> bool:
    """Q7: whether the anonymized text is stored, so a retry skips extraction."""
    found = await session.scalar(
        text("SELECT 1 FROM resume_texts WHERE candidate_id = :id"), {"id": candidate_id}
    )
    return found is not None


async def set_status(
    session: AsyncSession, candidate_id: UUID, status: str, failure_reason: str | None = None
) -> None:
    """Q8a: set `processing_status` and `failure_reason`; never touches stage or identity_name."""
    await session.execute(
        text(
            "UPDATE candidates SET processing_status = CAST(:status AS processing_state), "
            "failure_reason = :reason, updated_at = now() WHERE id = :id"
        ),
        {"id": candidate_id, "status": status, "reason": failure_reason},
    )


async def store_texts(
    session: AsyncSession,
    candidate_id: UUID,
    *,
    raw_text: str,
    anonymized: AnonymizedText,
    anonymizer_version: int,
    identity_name: str | None,
    status: str,
) -> None:
    """T3 with Q8b: store both texts apart, the name and the status, and delete the file.

    The only writer of `identity_name`; Q8a never writes it, so a later status update on the
    re-claim path cannot put NULL over the stored name.
    """
    await session.execute(
        text("INSERT INTO resume_raw_texts (candidate_id, raw_text) VALUES (:id, :raw)"),
        {"id": candidate_id, "raw": raw_text},
    )
    await session.execute(
        text(
            "INSERT INTO resume_texts (candidate_id, anonymized_text, anonymizer_version) "
            "VALUES (:id, :anonymized, :version)"
        ),
        {"id": candidate_id, "anonymized": anonymized.value, "version": anonymizer_version},
    )
    await session.execute(
        text(
            "UPDATE candidates SET processing_status = CAST(:status AS processing_state), "
            "failure_reason = NULL, identity_name = :name, updated_at = now() WHERE id = :id"
        ),
        {"id": candidate_id, "status": status, "name": identity_name},
    )
    await session.execute(
        text("DELETE FROM resume_files WHERE candidate_id = :id"), {"id": candidate_id}
    )


async def write_scores(
    session: AsyncSession,
    *,
    role_id: UUID,
    criteria_version: int,
    candidate_id: UUID,
    scores: Sequence[ScoreRow],
) -> bool:
    """Q5 then Q9: upsert the scores if the role is Approved at `criteria_version`, else False.

    On a same-version rewrite only `failed` rows change, and `override_*` is never written.
    """
    role = await read_role(session, role_id)
    if role is None or role.status != "approved" or role.criteria_version != criteria_version:
        return False
    await session.execute(
        text(
            "INSERT INTO scores (candidate_id, criterion_id, criteria_version, status, "
            "model_score, quote, flag_reason) VALUES (:candidate, :criterion, :version, "
            "CAST(:status AS score_status), :score, :quote, :flag) "
            "ON CONFLICT (candidate_id, criterion_id, criteria_version) DO UPDATE SET "
            "status = EXCLUDED.status, model_score = EXCLUDED.model_score, "
            "quote = EXCLUDED.quote, flag_reason = EXCLUDED.flag_reason, updated_at = now() "
            "WHERE scores.status = 'failed'"
        ),
        [
            {
                "candidate": candidate_id,
                "criterion": s.criterion_id,
                "version": criteria_version,
                "status": s.status,
                "score": s.model_score,
                "quote": s.quote,
                "flag": s.flag_reason,
            }
            for s in scores
        ],
    )
    return True


async def insert_criteria(
    session: AsyncSession,
    *,
    role_id: UUID,
    criteria_version: int,
    proposed: Sequence[ProposedCriterion],
) -> int | None:
    """Q5 (`FOR UPDATE`) then Q10: insert a proposal and bump the version; None writes nothing.

    Refused when the role is not Draft, its version differs from the job's, or it already has
    live criteria (a recruiter or an earlier run got there first).
    """
    role = await read_role(session, role_id, exclusive=True)
    if role is None or role.status != "draft" or role.criteria_version != criteria_version:
        return None
    live = await session.scalar(
        text("SELECT 1 FROM criteria WHERE role_id = :role AND retired_at IS NULL LIMIT 1"),
        {"role": role_id},
    )
    if live is not None:
        return None
    for position, criterion in enumerate(proposed, start=1):
        criterion_id = await session.scalar(
            text(
                "INSERT INTO criteria (role_id, name, kind, weight, position) VALUES "
                "(:role, :name, CAST(:kind AS criterion_kind), :weight, :position) RETURNING id"
            ),
            {
                "role": role_id,
                "name": criterion.name,
                "kind": criterion.kind,
                "weight": criterion.weight,
                "position": position,
            },
        )
        await session.execute(
            text(
                "INSERT INTO rubric_levels (criterion_id, level, descriptor) "
                "VALUES (:criterion, :level, :descriptor)"
            ),
            [
                {"criterion": criterion_id, "level": level, "descriptor": descriptor}
                for level, descriptor in enumerate(criterion.levels)
            ],
        )
    bumped = await session.scalar(
        text(
            "UPDATE roles SET criteria_version = criteria_version + 1, updated_at = now() "
            "WHERE id = :id RETURNING criteria_version"
        ),
        {"id": role_id},
    )
    return int(bumped)


async def replace_kit(
    session: AsyncSession,
    *,
    role_id: UUID,
    criteria_version: int,
    questions: Sequence[NewQuestion],
) -> bool:
    """Q5 then Q11: upsert the kit header, replace every question; False writes nothing.

    The role's open `regenerate_question` jobs are cancelled before the questions are deleted,
    after locking the open jobs in ascending id, so the cascade from `questions` into `jobs`
    never meets a job row another Worker holds.
    """
    role = await read_role(session, role_id)
    if role is None or role.status != "approved" or role.criteria_version != criteria_version:
        return False
    await session.execute(
        text(
            "INSERT INTO interview_kits (role_id, criteria_version) VALUES (:role, :version) "
            "ON CONFLICT (role_id) DO UPDATE SET criteria_version = EXCLUDED.criteria_version, "
            "updated_at = now()"
        ),
        {"role": role_id, "version": criteria_version},
    )
    await session.execute(
        text(
            "SELECT id FROM jobs WHERE role_id = :role AND status IN ('queued', 'running') "
            "ORDER BY id FOR UPDATE"
        ),
        {"role": role_id},
    )
    await session.execute(
        text(
            "UPDATE jobs SET status = 'cancelled', lease_token = NULL, lease_expires_at = NULL, "
            "updated_at = now() WHERE role_id = :role AND type = 'regenerate_question' "
            "AND status IN ('queued', 'running')"
        ),
        {"role": role_id},
    )
    await session.execute(text("DELETE FROM questions WHERE role_id = :role"), {"role": role_id})
    if questions:
        await session.execute(
            text(
                "INSERT INTO questions (role_id, criterion_id, question_text, strong_answer, "
                "weak_answer, position) VALUES (:role, :criterion, :question, :strong, :weak, "
                ":position)"
            ),
            [
                {
                    "role": role_id,
                    "criterion": q.criterion_id,
                    "question": q.question_text,
                    "strong": q.strong_answer,
                    "weak": q.weak_answer,
                    "position": q.position,
                }
                for q in questions
            ],
        )
    return True


async def replace_question(
    session: AsyncSession,
    *,
    role_id: UUID,
    criteria_version: int,
    question_id: UUID,
    question_text: str,
    strong_answer: str,
    weak_answer: str,
) -> bool:
    """Q5 then Q11: rewrite one question's text and answers, keeping its position.

    False writes nothing: the role changed, or the question was deleted meanwhile.
    """
    role = await read_role(session, role_id)
    if role is None or role.status != "approved" or role.criteria_version != criteria_version:
        return False
    result = await session.execute(
        text(
            "UPDATE questions SET question_text = :question, strong_answer = :strong, "
            "weak_answer = :weak, updated_at = now() WHERE id = :id AND role_id = :role "
            "RETURNING id"
        ),
        {
            "id": question_id,
            "role": role_id,
            "question": question_text,
            "strong": strong_answer,
            "weak": weak_answer,
        },
    )
    return result.first() is not None
