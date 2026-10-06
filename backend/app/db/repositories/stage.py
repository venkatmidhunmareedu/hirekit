"""The only module in the Api that writes `candidates.stage` (tenet 4).

`tests/api/guards.py` fails the build if any other module writes it. Nothing here commits;
the caller owns the transaction.
"""

import uuid
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_STAGE: Final = text(
    "UPDATE candidates SET stage = CAST(:stage AS candidate_stage), updated_at = now() "
    "WHERE id = :id"
)


async def write_stage(session: AsyncSession, candidate_id: uuid.UUID, stage: str) -> None:
    """Set the candidate's stage. The route that calls it has already audited the change."""
    await session.execute(_STAGE, {"id": candidate_id, "stage": stage})
