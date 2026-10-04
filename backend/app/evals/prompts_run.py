"""`python -m app.evals.prompts_run`: judge the recorded replies of scoring, criteria and kit.

For each prompt, the same call the Worker makes is replayed from a recording and the reply is
checked by `app.evals.prompts`: a contract layer (the production parser accepts it) and a
behaviour layer (quote found, injection does not move the score, term coverage, distinct
questions). Only the first attempt (schema_retry 0) is judged, so a reply the Worker would have
retried counts as a failure here. Replay only: no live call is ever made from here.

Exit codes: 0 every check passes, 1 at least one fails, 2 refused (live mode, bad settings, a
recording missing). The reports say what was checked; they never claim quality or fairness.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TextIO

from pydantic import ValidationError

from app.anonymizer import anonymize
from app.core.config import Settings
from app.evals.cases import (
    CriteriaCase,
    KitCase,
    ScoringCase,
    load_criteria_cases,
    load_kit_cases,
    load_scoring_cases,
)
from app.evals.gateway import open_gateway
from app.evals.prompts import (
    Violation,
    check_criteria,
    check_injection,
    check_kit,
    check_scoring,
    quote_counts,
)
from app.evals.run import criterion_specs
from app.extraction import ResumeExtractor
from app.gateway.errors import GatewayError, RecordingMissingError
from app.gateway.text import AnonymizedText
from app.jobs.job_description import job_description_text
from app.prompts.criteria_prompt import CriteriaPromptBuilder
from app.prompts.kit_prompt import KitPromptBuilder
from app.prompts.scoring_prompt import ScoringPromptBuilder
from app.seed.__main__ import DEFAULT_ROOT
from app.seed.candidates import MEDIA_TYPES
from app.seed.data import SeedData, SeedRole, load_role, load_seed
from app.worker.handlers.kit import call_kit
from app.worker.handlers.propose_criteria import call_criteria
from app.worker.handlers.scoring import ScoringGateway, call_scoring
from app.worker.ports import CriterionSpec

BACKEND: Final = Path(__file__).resolve().parents[2]
NAMES: Final = ("scoring", "criteria", "kit")
SCOPE: Final = (
    "Contract and coverage verified; quality reviewed by a person: not done. These checks do not "
    "show that a prompt is good or fair. Anonymization is a floor, not proof of fairness: proxy "
    "signals such as schools, clubs, gendered wording and career gaps can remain."
)


@dataclass(frozen=True, slots=True)
class Applied:
    """One check applied to one case; `details` is empty when it passed."""

    check: str
    case: str
    details: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptReport:
    name: str
    prompt_version: str
    applied: tuple[Applied, ...]
    notes: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return all(not a.details for a in self.applied)


@dataclass(frozen=True, slots=True)
class PromptOutcome:
    exit_code: int
    message: str
    reports: dict[str, str]


@dataclass(frozen=True, slots=True)
class AskedScoring:
    reply: str
    text: AnonymizedText
    criteria: list[CriterionSpec]


def _applied(case: str, checks: tuple[str, ...], violations: list[Violation]) -> list[Applied]:
    return [Applied(c, case, tuple(v.detail for v in violations if v.check == c)) for c in checks]


def _role_of(seed: SeedData, resume_id: str) -> SeedRole:
    return next(r for r in seed.roles if resume_id.startswith(f"{r.slug}-"))


async def ask_scoring(
    gateway: ScoringGateway, seed: SeedData, seed_root: Path, case: ScoringCase
) -> AskedScoring:
    """The scoring call for one case, as `run.score_resume` makes it; the first attempt only."""
    role = _role_of(seed, case.resume)
    found = [
        p for ext in MEDIA_TYPES if (p := seed_root / "resumes" / f"{case.resume}.{ext}").is_file()
    ]
    if len(found) != 1:
        raise ValueError(f"{case.resume}: expected one built file in {seed_root}/resumes")
    raw = await asyncio.to_thread(
        ResumeExtractor().extract, found[0].read_bytes(), MEDIA_TYPES[found[0].suffix[1:]]
    )
    if case.injected_line is not None:
        raw = f"{raw}\n{case.injected_line}"
    anonymized = await asyncio.to_thread(anonymize, raw)
    specs = criterion_specs(role)
    builder = ScoringPromptBuilder()
    reply = await call_scoring(
        gateway,
        role_id=None,
        prompt_version=builder.prompt_version,
        system=builder.build(specs),
        text=anonymized.text,
        schema_retry=0,
    )
    return AskedScoring(reply.text, anonymized.text, specs)


async def ask_criteria(gateway: ScoringGateway, role: SeedRole) -> str:
    """The criteria call for one job description; the first attempt only."""
    builder = CriteriaPromptBuilder()
    reply = await call_criteria(
        gateway,
        role_id=None,
        prompt_version=builder.prompt_version,
        system=builder.build(),
        description=job_description_text(role.title, role.job_description),
        schema_retry=0,
    )
    return reply.text


async def ask_kit(gateway: ScoringGateway, role: SeedRole, criterion: str) -> str:
    """The kit call for one criterion of one role; the first attempt only."""
    spec = next(s for s in criterion_specs(role) if s.name == criterion)
    builder = KitPromptBuilder()
    reply = await call_kit(
        gateway,
        role_id=None,
        prompt_version=builder.prompt_version,
        system=builder.build(spec),
        description=job_description_text(role.title, role.job_description, spec),
        schema_retry=0,
    )
    return reply.text


async def run_scoring_set(
    gateway: ScoringGateway, seed: SeedData, seed_root: Path, cases: list[ScoringCase]
) -> PromptReport:
    asked = {c.id: await ask_scoring(gateway, seed, seed_root, c) for c in cases}
    plain = {c.resume: asked[c.id] for c in cases if c.injected_line is None}
    applied: list[Applied] = []
    found = given = 0
    for case in cases:
        got = asked[case.id]
        checks = ("contract", "injection") if case.injected_line else ("contract",)
        violations = check_scoring(got.reply, got.criteria)
        if case.injected_line:
            violations += check_injection(plain[case.resume].reply, got.reply, got.criteria)
        applied += _applied(case.id, checks, violations)
        n_found, n_given = quote_counts(got.reply, got.criteria, got.text)
        found, given = found + n_found, given + n_given
    rate = f"{found} of {given} ({100 * found // given}%)" if given else "no quotes given"
    note = (
        f"Quote found rate: {rate}. Reported on its own, not a pass bar. A quote counts when "
        "its whitespace-normalized text is a literal substring of the anonymized resume."
    )
    return PromptReport("scoring", ScoringPromptBuilder().prompt_version, tuple(applied), (note,))


async def run_criteria_set(
    gateway: ScoringGateway, cases: list[CriteriaCase], backend: Path
) -> PromptReport:
    applied: list[Applied] = []
    for case in cases:
        reply = await ask_criteria(gateway, load_role(backend / case.role_file))
        violations = check_criteria(reply, list(case.required_terms))
        applied += _applied(case.id, ("contract", "coverage"), violations)
    return PromptReport("criteria", CriteriaPromptBuilder().prompt_version, tuple(applied))


async def run_kit_set(gateway: ScoringGateway, cases: list[KitCase], backend: Path) -> PromptReport:
    applied: list[Applied] = []
    for case in cases:
        reply = await ask_kit(gateway, load_role(backend / case.role_file), case.criterion)
        applied += _applied(case.id, ("contract", "distinct"), check_kit(reply, case.criterion))
    return PromptReport("kit", KitPromptBuilder().prompt_version, tuple(applied))


def render_report(report: PromptReport, *, model_id: str, label: str) -> str:
    checks = list(dict.fromkeys(a.check for a in report.applied))
    rows = [
        f"| {c} | {sum(not a.details for a in report.applied if a.check == c)} "
        f"| {sum(a.check == c for a in report.applied)} |"
        for c in checks
    ]
    failures = [f"- {a.case}, {a.check}: {detail}" for a in report.applied for detail in a.details]
    lines = [
        f"# {'PASS' if report.passed else 'FAIL'}: {report.name} eval ({report.name}-"
        f"{report.prompt_version})",
        "",
        f"Model: {model_id}. Prompt version: {report.prompt_version}. Run: {label}.",
        "Replayed from recorded replies, first attempt only; no live call.",
        "",
        "| Check | Passed | Cases |",
        "| --- | --- | --- |",
        *rows,
        "",
        *[n for note in report.notes for n in (note, "")],
        "## Failures",
        "",
        *(failures or ["None."]),
        "",
        "## What this shows",
        "",
        SCOPE,
    ]
    return "\n".join(lines)


async def run_prompt_evals(
    gateway: ScoringGateway,
    seed: SeedData,
    seed_root: Path,
    backend: Path,
    *,
    model_id: str,
    label: str,
) -> PromptOutcome:
    """Run all three sets; a refusal or a missing recording is exit code 2."""
    evals = backend / "evals"
    try:
        reports = [
            await run_scoring_set(
                gateway, seed, seed_root, load_scoring_cases(evals / "scoring/cases.json")
            ),
            await run_criteria_set(
                gateway, load_criteria_cases(evals / "criteria/cases.json"), backend
            ),
            await run_kit_set(gateway, load_kit_cases(evals / "kit/cases.json"), backend),
        ]
    except RecordingMissingError as error:
        return PromptOutcome(
            2,
            f"recording missing: {error.message}\n"
            "record it with make record (see backend/evals/README.md); nothing was called live",
            {},
        )
    except GatewayError as error:
        return PromptOutcome(2, f"refused: {error.message}", {})
    return PromptOutcome(
        0 if all(r.passed for r in reports) else 1,
        "",
        {r.name: render_report(r, model_id=model_id, label=label) for r in reports},
    )


def write_reports(outcome: PromptOutcome, evals: Path) -> None:
    """Write each report; a refused run (exit 2) removes the old ones, which no longer match."""
    for name in NAMES:
        path = evals / name / "report.md"
        if name in outcome.reports:
            path.write_text(outcome.reports[name] + "\n", encoding="utf-8")
        elif outcome.exit_code == 2:
            path.unlink(missing_ok=True)


async def main(
    argv: list[str], *, settings: Settings | None = None, out: TextIO | None = None
) -> int:
    out = out or sys.stdout
    parser = argparse.ArgumentParser(prog="python -m app.evals.prompts_run")
    parser.add_argument("--backend-dir", type=Path, default=BACKEND, help="holds evals/<name>/")
    parser.add_argument("--seed-dir", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--label", default="unlabelled")
    args = parser.parse_args(argv)
    try:
        settings = settings or Settings()
    except ValidationError as exc:
        out.write(f"eval-prompts: refused: invalid settings ({len(exc.errors())} problems)\n")
        return 2
    if settings.model_mode != "replay":
        out.write("eval-prompts: refused: evals run on recordings only; unset MODEL_MODE=live\n")
        return 2
    seed = load_seed(args.seed_dir)
    async with open_gateway(settings) as gateway:
        outcome = await run_prompt_evals(
            gateway,
            seed,
            args.seed_dir,
            args.backend_dir,
            model_id=settings.model_id,
            label=args.label,
        )
    if outcome.message:
        out.write(f"eval-prompts: {outcome.message}\n")
    for text in outcome.reports.values():
        out.write(text + "\n")
    write_reports(outcome, args.backend_dir / "evals")
    return outcome.exit_code


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
