"""`python -m app.evals.record`: the pipeline `make record` runs between preflight and finish.

Makes the eval calls through the live Gateway, which writes the recordings (no direct file
writes here). Jobs (`--jobs`, default scoring): `scoring` scores the 40 seed resumes;
`process_resume` scores the injection cases of evals/scoring/cases.json (the seed resumes they
build on come from `scoring`); `criteria` and `kit` make one call per case of their
cases.json. `--smoke` limits every job to its first case. Refuses unless MODEL_MODE=live and
RECORD_RESPONSES=true, and under CI. Exit codes: 0 done, 1 the run failed part-way, 2 refused.
"""

import argparse
import asyncio
import dataclasses
import sys
from pathlib import Path
from typing import Final, TextIO
from urllib.parse import urlsplit

from pydantic import ValidationError

from app.core.config import Settings
from app.evals.cases import load_criteria_cases, load_kit_cases, load_scoring_cases
from app.evals.gateway import open_gateway
from app.evals.prompts_run import BACKEND, ask_criteria, ask_kit, ask_scoring
from app.evals.run import run_scoring
from app.gateway.errors import GatewayError
from app.gateway.types import Recording
from app.seed.__main__ import DEFAULT_ROOT
from app.seed.data import SeedData, load_role, load_seed
from app.worker.handlers.scoring import ScoringGateway

JOBS: Final = ("scoring", "process_resume", "criteria", "kit")


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


async def _make_calls(
    job: str,
    gateway: ScoringGateway,
    seed: SeedData,
    seed_root: Path,
    backend: Path,
    *,
    smoke: bool,
) -> int:
    """Make the calls of one job; returns how many were made."""
    evals = backend / "evals"
    if job == "scoring":
        if smoke:
            first = min(seed.resumes)
            seed = dataclasses.replace(seed, resumes={first: seed.resumes[first]})
        await run_scoring(seed, gateway, seed_root=seed_root)
        return len(seed.resumes)
    if job == "process_resume":
        injected = [c for c in load_scoring_cases(evals / "scoring/cases.json") if c.injected_line]
        for scoring_case in injected[:1] if smoke else injected:
            await ask_scoring(gateway, seed, seed_root, scoring_case)
        return 1 if smoke else len(injected)
    if job == "criteria":
        criteria = load_criteria_cases(evals / "criteria/cases.json")
        for criteria_case in criteria[:1] if smoke else criteria:
            await ask_criteria(gateway, load_role(backend / criteria_case.role_file))
        return 1 if smoke else len(criteria)
    kit = load_kit_cases(evals / "kit/cases.json")
    for kit_case in kit[:1] if smoke else kit:
        await ask_kit(gateway, load_role(backend / kit_case.role_file), kit_case.criterion)
    return 1 if smoke else len(kit)


def _planned(
    jobs: tuple[str, ...], seed: SeedData, backend: Path, *, smoke: bool
) -> dict[str, int]:
    evals = backend / "evals"
    counts = {
        "scoring": len(seed.resumes),
        "process_resume": sum(
            1 for c in load_scoring_cases(evals / "scoring/cases.json") if c.injected_line
        ),
        "criteria": len(load_criteria_cases(evals / "criteria/cases.json")),
        "kit": len(load_kit_cases(evals / "kit/cases.json")),
    }
    return {j: min(counts[j], 1) if smoke else counts[j] for j in jobs}


async def run_record(
    gateway: ScoringGateway,
    seed: SeedData,
    seed_root: Path,
    recordings_dir: Path,
    *,
    smoke: bool,
    out: TextIO,
    plan: str = "",
    jobs: tuple[str, ...] = ("scoring",),
    backend: Path = BACKEND,
) -> int:
    """Make the calls of each job (one case each when smoke), printing the plan and the counts."""
    planned = _planned(jobs, seed, backend, smoke=smoke)
    listed = ", ".join(f"{n} {job}" for job, n in planned.items())
    total = sum(planned.values())
    out.write(f"record: plan: {total} {'call' if total == 1 else 'calls'} ({listed}){plan}\n")
    before = _recorded(recordings_dir)
    code = 0
    try:
        for job in jobs:
            await _make_calls(job, gateway, seed, seed_root, backend, smoke=smoke)
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
        out.write(
            "record: next, run make eval and make eval-prompts with the same RECORDINGS_DIR\n"
        )
    return code


async def main(
    argv: list[str], *, settings: Settings | None = None, out: TextIO | None = None
) -> int:
    out = out or sys.stdout
    parser = argparse.ArgumentParser(prog="python -m app.evals.record")
    parser.add_argument("--smoke", action="store_true", help="one case per job only")
    parser.add_argument(
        "--jobs", nargs="+", choices=JOBS, default=["scoring"], help="which calls to make"
    )
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
            jobs=tuple(args.jobs),
        )


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
