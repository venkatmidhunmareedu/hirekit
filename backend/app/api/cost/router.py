"""GET /v1/cost-log: the model budget and the call log (recruiter only)."""

from typing import Annotated, Final

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cost.schemas import CostLog
from app.core.auth import RecruiterUser
from app.core.config import Settings
from app.core.errors import ErrorEnvelope
from app.db.repositories.cost import CostRepository
from app.db.session import get_session
from app.domain.cost import service

router = APIRouter(prefix="/v1", tags=["cost"])

_ERRORS: Final[dict[int | str, dict[str, type[ErrorEnvelope]]]] = {
    code: {"model": ErrorEnvelope} for code in (401, 403, 422)
}


def get_costs(session: Annotated[AsyncSession, Depends(get_session)]) -> CostRepository:
    """The cost repository for this request."""
    return CostRepository(session)


Costs = Annotated[CostRepository, Depends(get_costs)]


@router.get("/cost-log", response_model=CostLog, responses=_ERRORS)
async def get_cost_log(
    _: RecruiterUser,
    request: Request,
    costs: Costs,
    response: Response,
    cursor: Annotated[str | None, Query(description="Opaque cursor from the previous page")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CostLog:
    """The budget and one page of calls, newest first."""
    response.headers["Cache-Control"] = "no-store"
    settings: Settings = request.app.state.settings
    return await service.cost_log(costs, settings, limit, cursor)
