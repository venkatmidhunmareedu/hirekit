"""The jobs repository dependency, shared by the jobs and roles routers."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.jobs_api import JobsApiRepository
from app.db.session import get_session


def get_jobs(session: Annotated[AsyncSession, Depends(get_session)]) -> JobsApiRepository:
    """The jobs repository for this request."""
    return JobsApiRepository(session)


Jobs = Annotated[JobsApiRepository, Depends(get_jobs)]
