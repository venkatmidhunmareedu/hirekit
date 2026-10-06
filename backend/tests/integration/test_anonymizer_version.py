"""`resume_texts.anonymizer_version` (migration 3): smallint, NOT NULL, default 1."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def new_candidate(session: AsyncSession) -> object:
    role = (
        await session.execute(
            text("INSERT INTO roles (title, job_description) VALUES ('Engineer', 'x') RETURNING id")
        )
    ).scalar_one()
    return (
        await session.execute(
            text(
                "INSERT INTO candidates (role_id, file_name, content_hash) "
                "VALUES (:role, 'cv.pdf', :hash) RETURNING id"
            ),
            {"role": role, "hash": "a" * 64},
        )
    ).scalar_one()


async def test_the_column_is_a_not_null_smallint_defaulting_to_one(session: AsyncSession) -> None:
    row = (
        await session.execute(
            text(
                "SELECT data_type, is_nullable, column_default FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'resume_texts' "
                "AND column_name = 'anonymizer_version'"
            )
        )
    ).one()
    assert tuple(row) == ("smallint", "NO", "1")


async def test_an_insert_that_omits_the_version_stores_one(session: AsyncSession) -> None:
    candidate = await new_candidate(session)
    await session.execute(
        text("INSERT INTO resume_texts (candidate_id, anonymized_text) VALUES (:c, 'x')"),
        {"c": candidate},
    )
    stored = await session.scalar(
        text("SELECT anonymizer_version FROM resume_texts WHERE candidate_id = :c"),
        {"c": candidate},
    )
    assert stored == 1


async def test_a_stored_version_reads_back(session: AsyncSession) -> None:
    candidate = await new_candidate(session)
    await session.execute(
        text(
            "INSERT INTO resume_texts (candidate_id, anonymized_text, anonymizer_version) "
            "VALUES (:c, 'x', 2)"
        ),
        {"c": candidate},
    )
    stored = await session.scalar(
        text("SELECT anonymizer_version FROM resume_texts WHERE candidate_id = :c"),
        {"c": candidate},
    )
    assert stored == 2
