"""`python -m app.evals`: score the seed from recordings and run both evals. Replay only.

Exit codes: 0 both evals pass, 1 at least one fails, 2 refused (live mode, bad settings, a
recording missing). No live call is ever made from here.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from pydantic import ValidationError

from app.core.config import Settings
from app.evals.agreement import evaluate_agreement
from app.evals.gateway import open_gateway
from app.evals.nameswap import evaluate_name_swap
from app.evals.report import render_agreement_report, render_name_swap_report
from app.evals.run import run_scoring
from app.gateway.errors import GatewayError, RecordingMissingError
from app.prompts.scoring_prompt import ScoringPromptBuilder
from app.seed.__main__ import DEFAULT_ROOT
from app.seed.data import SeedData, load_seed
from app.worker.handlers.scoring import ScoringGateway


@dataclass(frozen=True, slots=True)
class EvalOutcome:
    exit_code: int
    message: str
    agreement_report: str | None = None
    name_swap_report: str | None = None


async def run_evals(
    gateway: ScoringGateway,
    seed: SeedData,
    seed_root: Path,
    *,
    model_id: str,
    prompt_version: str,
    label: str,
) -> EvalOutcome:
    """Score every seed resume once and judge both evals; a refusal is exit code 2."""
    try:
        results = await run_scoring(seed, gateway, seed_root=seed_root)
    except RecordingMissingError as error:
        return EvalOutcome(
            2,
            f"recording missing: {error.message}\n"
            "record it with make record (see backend/evals/README.md); nothing was called live",
        )
    except GatewayError as error:
        return EvalOutcome(2, f"refused: {error.message}")
    agreement = evaluate_agreement(results, seed.labels)
    swap = evaluate_name_swap(results, seed.pairs)
    names = {"model_id": model_id, "prompt_version": prompt_version, "run_date_label": label}
    return EvalOutcome(
        0 if agreement.passed and swap.passed else 1,
        "",
        render_agreement_report(agreement, **names),
        render_name_swap_report(swap, **names),
    )


async def main(
    argv: list[str], *, settings: Settings | None = None, out: TextIO | None = None
) -> int:
    out = out or sys.stdout
    parser = argparse.ArgumentParser(prog="python -m app.evals")
    parser.add_argument("--out", type=Path, help="write agreement.md and name-swap.md here")
    parser.add_argument("--seed-dir", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--label", default="unlabelled")
    args = parser.parse_args(argv)
    try:
        settings = settings or Settings()
    except ValidationError as exc:
        out.write(f"evals: refused: invalid settings ({len(exc.errors())} problems)\n")
        return 2
    if settings.model_mode != "replay":
        out.write("evals: refused: evals run on recordings only; unset MODEL_MODE=live\n")
        return 2
    seed = load_seed(args.seed_dir)
    async with open_gateway(settings) as gateway:
        outcome = await run_evals(
            gateway,
            seed,
            args.seed_dir,
            model_id=settings.model_id,
            prompt_version=ScoringPromptBuilder().prompt_version,
            label=args.label,
        )
    if outcome.message:
        out.write(f"evals: {outcome.message}\n")
    for name, text in (
        ("agreement.md", outcome.agreement_report),
        ("name-swap.md", outcome.name_swap_report),
    ):
        if text is None:
            continue
        out.write(text + "\n")
        if args.out is not None:
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / name).write_text(text)
    return outcome.exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
