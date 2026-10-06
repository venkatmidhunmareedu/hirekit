"""`load_anonymized` against Postgres: the stored text comes back as an `AnonymizedText`."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.anonymizer import load_anonymized
from app.anonymizer.pipeline import ANONYMIZER_VERSION
from app.core.errors import NotFoundError
from app.gateway.text import AnonymizedText

pytestmark = pytest.mark.integration


async def new_candidate(session: AsyncSession) -> UUID:
    role = (
        await session.execute(
            text("INSERT INTO roles (title, job_description) VALUES ('Engineer', 'x') RETURNING id")
        )
    ).scalar_one()
    candidate: UUID = (
        await session.execute(
            text(
                "INSERT INTO candidates (role_id, file_name, content_hash) "
                "VALUES (:role, 'cv.pdf', :hash) RETURNING id"
            ),
            {"role": role, "hash": "a" * 64},
        )
    ).scalar_one()
    return candidate


async def store(session: AsyncSession, candidate: UUID, stored: str, version: int) -> None:
    await session.execute(
        text(
            "INSERT INTO resume_texts (candidate_id, anonymized_text, anonymizer_version) "
            "VALUES (:c, :t, :v)"
        ),
        {"c": candidate, "t": stored, "v": version},
    )


async def test_load_anonymized_returns_the_stored_text_as_anonymized_text(
    session: AsyncSession,
) -> None:
    candidate = await new_candidate(session)
    await store(session, candidate, "[NAME] built payments.", ANONYMIZER_VERSION)
    loaded = await load_anonymized(session, candidate)
    assert isinstance(loaded, AnonymizedText)
    assert loaded.value == "[NAME] built payments."


async def test_a_candidate_with_no_stored_text_is_not_found(session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await load_anonymized(session, uuid4())


async def test_text_stored_by_an_older_anonymizer_is_scanned_again_before_it_is_minted(
    session: AsyncSession,
) -> None:
    candidate = await new_candidate(session)
    await store(session, candidate, "Mrs. Rao, mail rao@example.com", ANONYMIZER_VERSION - 1)
    loaded = await load_anonymized(session, candidate)
    assert loaded.value == "[TITLE] [NAME], mail [EMAIL]"


async def test_text_stored_by_the_current_anonymizer_is_not_scanned_again(
    session: AsyncSession,
) -> None:
    candidate = await new_candidate(session)
    await store(session, candidate, "Mrs. Rao, mail rao@example.com", ANONYMIZER_VERSION)
    loaded = await load_anonymized(session, candidate)
    assert loaded.value == "Mrs. Rao, mail rao@example.com"
