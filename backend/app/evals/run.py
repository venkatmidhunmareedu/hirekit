"""Score the seed resumes through the real pipeline: file bytes, extract, anonymize, score.

The scoring step is `score_text`, the same function the Worker calls, so the evals cannot drift
from production. Criterion ids are uuid5 of the role slug and criterion name, so a rebuild gives
the same prompt text and the same recording keys on every run. Sequential on purpose: the
budget and the logs stay simple. A `RecordingMissingError` is never caught here.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.anonymizer import anonymize
from app.extraction import ResumeExtractor
from app.prompts.scoring_parser import ScoreReplyParser
from app.prompts.scoring_prompt import ScoringPromptBuilder
from app.seed.candidates import MEDIA_TYPES
from app.seed.data import SeedData, SeedRole
from app.worker.handlers.scoring import ScoringGateway, score_text
from app.worker.ports import CriterionSpec
from app.worker.quotes import WhitespaceQuoteVerifier

NAMESPACE = uuid5(NAMESPACE_URL, "https://hirekit.invalid/evals")


@dataclass(frozen=True, slots=True)
class CriterionScore:
    """One criterion's outcome: `status` is scored, no_evidence or failed; failed has no value."""

    name: str
    status: str
    value: int | None
    quote: str | None
    flag_reason: str | None


@dataclass(frozen=True, slots=True)
class ResumeResult:
    resume_id: str
    role_slug: str
    anonymized_text: str
    scores: tuple[CriterionScore, ...]


def criterion_specs(role: SeedRole) -> list[CriterionSpec]:
    """The role's criteria as the scoring step takes them; ids are the same on every run."""
    return [
        CriterionSpec(
            uuid5(NAMESPACE, f"{role.slug}/{c.name}"),
            c.name,
            c.kind,
            c.weight,
            position,
            tuple(enumerate(c.levels)),
        )
        for position, c in enumerate(role.criteria)
    ]


async def score_resume(
    gateway: ScoringGateway,
    *,
    role: SeedRole,
    resume_id: str,
    content: bytes,
    media_type: str,
) -> ResumeResult:
    """Extract, anonymize and score one resume file against its role's criteria."""
    raw = await asyncio.to_thread(ResumeExtractor().extract, content, media_type)
    anonymized = await asyncio.to_thread(anonymize, raw)
    specs = criterion_specs(role)
    builder = ScoringPromptBuilder()
    rows = await score_text(
        gateway,
        role_id=None,  # call_log.role_id is a foreign key; an eval call has no role (schema.sql)
        prompt_version=builder.prompt_version,
        system=builder.build(specs),
        criteria=specs,
        text=anonymized.text,
        parser=ScoreReplyParser(),
        verifier=WhitespaceQuoteVerifier(),
    )
    names = {s.id: s.name for s in specs}
    return ResumeResult(
        resume_id,
        role.slug,
        anonymized.text.value,
        tuple(
            CriterionScore(names[r.criterion_id], r.status, r.model_score, r.quote, r.flag_reason)
            for r in rows
        ),
    )


def _built_file(resumes_dir: Path, resume_id: str) -> tuple[Path, str]:
    found = [p for ext in MEDIA_TYPES if (p := resumes_dir / f"{resume_id}.{ext}").is_file()]
    if len(found) != 1:
        raise ValueError(
            f"{resume_id}: expected one .pdf or .docx in {resumes_dir}, found {len(found)}"
        )
    return found[0], MEDIA_TYPES[found[0].suffix[1:]]


async def run_scoring(
    seed: SeedData, gateway: ScoringGateway, *, seed_root: Path
) -> list[ResumeResult]:
    """Score every seed resume, sorted by id, from the built file beside its text."""
    results: list[ResumeResult] = []
    for resume_id in sorted(seed.resumes):
        role = next(r for r in seed.roles if resume_id.startswith(f"{r.slug}-"))
        path, media_type = _built_file(seed_root / "resumes", resume_id)
        results.append(
            await score_resume(
                gateway,
                role=role,
                resume_id=resume_id,
                content=path.read_bytes(),
                media_type=media_type,
            )
        )
    return results
