"""`python -m app.seed`: write the seed roles and candidates in one transaction, then the users.

Idempotent: roles, candidates and users already present are skipped (`--reset-passwords` resets
the users' passwords). Enqueues no jobs.
"""

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import make_engine, make_session_factory
from app.seed.candidates import seed_candidates
from app.seed.data import Expected, load_seed
from app.seed.load import seed_roles
from app.seed.users import format_outcome, seed_users

log = structlog.get_logger()

DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "seed"


@dataclass(frozen=True, slots=True)
class SeedResult:
    roles_created: int
    candidates_created: int


async def run_seed(
    session_factory: async_sessionmaker[AsyncSession],
    root: Path = DEFAULT_ROOT,
    expected: Expected | None = None,
) -> SeedResult:
    """Validate the tree, then write roles and candidates; any error rolls both back."""
    data = load_seed(root, expected)
    async with session_factory.begin() as session:
        roles = await seed_roles(session, data.roles)
        candidates = await seed_candidates(session, data, root / "resumes")
    return SeedResult(roles_created=roles, candidates_created=candidates)


async def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.seed")
    parser.add_argument(
        "--reset-passwords",
        action="store_true",
        help="give the existing seed users new passwords (default: keep them)",
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    engine = make_engine(settings)
    try:
        factory = make_session_factory(engine)
        result = await run_seed(factory)
        async with factory.begin() as session:
            users = await seed_users(session, os.environ, reset=args.reset_passwords)
    finally:
        await engine.dispose()
    log.info(
        "seed_done",
        roles_created=result.roles_created,
        candidates_created=result.candidates_created,
        users={u.email: u.status for u in users},
    )
    for outcome in users:  # the only place a generated password appears, once, on stdout
        sys.stdout.write(format_outcome(outcome) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
