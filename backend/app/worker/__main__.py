"""`python -m app.worker`: build the engine and run the claim loop until SIGTERM or SIGINT.

The handlers come from `app.worker.wiring.build_worker`; replay or live is `Settings.model_mode`.
"""

import asyncio
import contextlib
import signal
from datetime import UTC, datetime

import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.repositories import jobs, worker_writes
from app.db.session import make_engine, make_session_factory
from app.worker.loop import run_worker
from app.worker.wiring import build_worker

log = structlog.get_logger()


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    engine = make_engine(settings)
    sessions = make_session_factory(engine)
    handlers, close_gateway = build_worker(settings, sessions.begin)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    async def sleep(seconds: float) -> None:
        """Wait out a poll, or less if a stop arrives."""
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=seconds)

    log.info("worker_started")
    try:
        await run_worker(
            sessions=sessions.begin,
            jobs=jobs,
            writes=worker_writes,
            handlers=handlers,
            stop=stop,
            now=lambda: datetime.now(UTC),
            sleep=sleep,
            poll_seconds=settings.worker_poll_seconds,
            lease_seconds=settings.worker_lease_seconds,
        )
    finally:
        await close_gateway()
        await engine.dispose()
        log.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())
