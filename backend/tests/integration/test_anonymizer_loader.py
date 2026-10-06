"""`load_anonymized` against Postgres: the stored text comes back as an `AnonymizedText`."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.anonymizer import load_anonymized
from app.core.errors import NotFoundError
from app.gateway.text import AnonymizedText

pytestmark = pytest.mark.integration


async def test_load_anonymized_returns_the_stored_text_as_anonymized_text(
    session: AsyncSession,
) -> None:
    role = (
        await session.execute(
            text("INSERT INTO roles (title, job_description) VALUES ('Engineer', 'x') RETURNING id")
        )
    ).scalar_one()
    candidate = (
        await session.execute(
            text(
                "INSERT INTO candidates (role_id, file_name, content_hash) "
                "VALUES (:role, 'cv.pdf', :hash) RETURNING id"
            ),
            {"role": role, "hash": "a" * 64},
        )
    ).scalar_one()
    await session.execute(
        text("INSERT INTO resume_texts (candidate_id, anonymized_text) VALUES (:c, :t)"),
        {"c": candidate, "t": "[NAME] built payments."},
    )
    loaded = await load_anonymized(session, candidate)
    assert isinstance(loaded, AnonymizedText)
    assert loaded.value == "[NAME] built payments."


async def test_a_candidate_with_no_stored_text_is_not_found(session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await load_anonymized(session, uuid4())
