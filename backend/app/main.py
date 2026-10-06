"""Application factory for HireKitApp.

Wiring only: settings, logging, middleware, exception handlers,
routers and the lifespan that owns the database engine. Run with
`uvicorn app.main:create_app --factory`.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app import __version__
from app.api.auth.router import router as auth_router
from app.api.candidates.assignments import router as assignments_router
from app.api.health.router import router as health_router
from app.api.resumes.router import router as resumes_router
from app.api.roles.router import router as roles_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import BodyLimitMiddleware, RequestIdMiddleware
from app.db.session import make_engine, make_session_factory

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the engine on startup and dispose it on shutdown."""
    settings: Settings = app.state.settings
    engine = make_engine(settings)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    log.info("startup", env=settings.env, version=__version__)
    try:
        yield
    finally:
        await engine.dispose()
        log.info("shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application. Tests pass explicit settings."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)
    docs_enabled = settings.env != "production"
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.settings = settings
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(roles_router)
    app.include_router(resumes_router)
    app.include_router(assignments_router)
    return app
