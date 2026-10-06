"""The real Gateway for the eval entry points, built by the Worker's own builder."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.core.config import Settings
from app.db.session import make_engine, make_session_factory
from app.gateway import Gateway
from app.worker.wiring import build_gateway


@asynccontextmanager
async def open_gateway(settings: Settings) -> AsyncIterator[Gateway]:
    """A Gateway over a real engine and ledger; both are closed on exit."""
    engine = make_engine(settings)
    gateway = build_gateway(settings, make_session_factory(engine).begin)
    try:
        yield gateway
    finally:
        await gateway.aclose()
        await engine.dispose()
