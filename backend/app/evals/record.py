"""`python -m app.evals.record`: the pipeline `make record` runs between preflight and finish.

Scores the seed resumes through the live Gateway, which writes the recordings (no direct file
writes here). Only scoring calls are recorded; criteria and kit recordings are HK-50.
`--smoke` scores one resume. Refuses unless MODEL_MODE=live and RECORD_RESPONSES=true, and
under CI. Exit codes: 0 done, 1 the run failed part-way, 2 refused.
"""

import argparse
import asyncio
import dataclasses
import sys
from pathlib import Path
from typing import TextIO
from urllib.parse import urlsplit

from pydantic import ValidationError

from app.core.config import Settings
from app.evals.gateway import open_gateway
from app.evals.run import run_scoring
from app.gateway.errors import GatewayError
from app.gateway.types import Recording
from app.seed.__main__ import DEFAULT_ROOT
from app.seed.data import SeedData, load_seed
from app.worker.handlers.scoring import ScoringGateway


def _recorded(directory: Path) -> dict[str, tuple[int, int]]:
    """File name to (input, output) tokens for every recording in the directory."""
    found: dict[str, tuple[int, int]] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            recording = Recording.model_validate_json(path.read_text(encoding="utf-8"))
        except OSError, ValidationError:
            continue  # the ledger file and anything else that is not a recording
        found[path.name] = (recording.response.input_tokens, recording.response.output_tokens)
    return found


async def run_record(
    gateway: ScoringGateway,
    seed: SeedData,
    seed_root: Path,
    recordings_dir: Path,
    *,
    smoke: bool,
    out: TextIO,
    plan: str = "",
) -> int:
    """Score one resume (smoke) or all, printing the plan first and the counts after."""
    if smoke:
        first = min(seed.resumes)
        seed = dataclasses.replace(seed, resumes={first: seed.resumes[first]})
    n = len(seed.resumes)
    out.write(f"record: plan: {n} scoring {'call' if n == 1 else 'calls'}{plan}\n")
    before = _recorded(recordings_dir)
    code = 0
    try:
        await run_scoring(seed, gateway, seed_root=seed_root)
    except GatewayError as error:
        out.write(f"record: stopped: {error.message}\n")
        code = 1
    new = [tokens for name, tokens in _recorded(recordings_dir).items() if name not in before]
    out.write(
        f"record: {len(new)} {'recording' if len(new) == 1 else 'recordings'} written "
        f"(one per live call), input tokens {sum(t[0] for t in new)}, "
        f"output tokens {sum(t[1] for t in new)}\n"
    )
    if code == 0:
        out.write("record: next, run make eval with the same RECORDINGS_DIR\n")
    return code


async def main(
    argv: list[str], *, settings: Settings | None = None, out: TextIO | None = None
) -> int:
    out = out or sys.stdout
    parser = argparse.ArgumentParser(prog="python -m app.evals.record")
    parser.add_argument("--smoke", action="store_true", help="score one resume only")
    parser.add_argument("--seed-dir", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)
    try:
        settings = settings or Settings()
    except ValidationError as exc:
        out.write(f"record: refused: invalid settings ({len(exc.errors())} problems)\n")
        return 2
    if settings.ci:
        out.write("record: refused: recording is manual and never runs under CI\n")
        return 2
    if settings.model_mode != "live" or not settings.record_responses:
        out.write(
            "record: refused: run it through make record (MODEL_MODE=live, RECORD_RESPONSES=true)\n"
        )
        return 2
    seed = load_seed(args.seed_dir)
    host = urlsplit(settings.model_base_url).hostname if settings.model_base_url else None
    plan = (
        f", model {settings.model_id}, host {host or 'provider default'}, "
        f"recordings {settings.recordings_dir}"
    )
    async with open_gateway(settings) as gateway:
        return await run_record(
            gateway,
            seed,
            args.seed_dir,
            settings.recordings_dir,
            smoke=args.smoke,
            out=out,
            plan=plan,
        )


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
