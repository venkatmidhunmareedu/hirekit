"""GET /v1/compare?ids=: two to four candidates side by side."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.compare.schemas import Comparison
from app.api.roles.router import Criteria
from app.core.auth import CurrentUser
from app.core.errors import ErrorEnvelope
from app.db.repositories.compare import CompareRepository
from app.db.session import get_session
from app.domain.compare import service

router = APIRouter(prefix="/v1/compare", tags=["compare"])

_ERRORS: dict[int | str, dict[str, type[ErrorEnvelope]]] = {
    code: {"model": ErrorEnvelope} for code in (401, 404, 422)
}


def get_compare(session: Annotated[AsyncSession, Depends(get_session)]) -> CompareRepository:
    """The compare repository for this request."""
    return CompareRepository(session)


Compare = Annotated[CompareRepository, Depends(get_compare)]


@router.get("", response_model=Comparison, responses=_ERRORS)
async def compare_candidates(
    ids: Annotated[str, Query(description="Two to four candidate ids, comma separated")],
    user: CurrentUser,
    compare: Compare,
    criteria: Criteria,
    response: Response,
) -> Comparison:
    """Compare candidates by criterion; an unassigned id makes an interviewer's request a 404."""
    response.headers["Cache-Control"] = "no-store"
    return await service.compare(compare, criteria, user, ids)
