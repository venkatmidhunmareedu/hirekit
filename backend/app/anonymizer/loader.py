"""`load_anonymized`: the one way stored text becomes an `AnonymizedText` again.

A re-scoring reads exactly the text its quotes were checked against, so it goes through the same
mint as a fresh run. Runs inside the caller's transaction; never commits.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.gateway.text import AnonymizedText, mint_anonymized

_Q1 = text("SELECT anonymized_text FROM resume_texts WHERE candidate_id = :candidate_id")


async def load_anonymized(session: AsyncSession, candidate_id: UUID) -> AnonymizedText:
    """The stored anonymized text of one candidate; `NotFoundError` when there is none."""
    stored = (await session.execute(_Q1, {"candidate_id": candidate_id})).scalar_one_or_none()
    if stored is None:
        msg = "No anonymized text is stored for this candidate."
        raise NotFoundError(msg)
    return mint_anonymized(stored)
