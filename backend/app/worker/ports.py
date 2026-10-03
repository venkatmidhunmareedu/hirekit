"""The ports the Worker calls: signatures only, each implemented by a component with its own design.

The two text loaders are implemented where the text is minted (`app.anonymizer.load_anonymized`,
and the job-description package once it exists), so no other module ever builds a text class
(tenet 2). Extraction, anonymization and the prompt libraries are sync: handlers run them in a
thread. docs/design/worker-lld.md section 3.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.gateway.text import AnonymizedText, JobDescriptionText, PromptText


@dataclass(frozen=True, slots=True)
class CriterionSpec:
    """One live criterion with its rubric: `(level, descriptor)` pairs, level 0 to 4."""

    id: UUID
    name: str
    kind: str
    weight: Decimal
    position: int
    rubric: tuple[tuple[int, str], ...]


@dataclass(frozen=True, slots=True)
class ParsedScore:
    """One criterion's value from a parsed reply, before the quote is verified."""

    criterion_id: UUID
    value: int
    quote: str | None


@dataclass(frozen=True, slots=True)
class ProposedCriterion:
    """A criterion the model proposed for a Draft role; `levels` holds the descriptors 0 to 4."""

    name: str
    kind: str
    weight: Decimal
    levels: tuple[str, str, str, str, str]


@dataclass(frozen=True, slots=True)
class ProposedQuestion:
    """One interview question the model proposed for one criterion."""

    question_text: str
    strong_answer: str
    weak_answer: str


class Extractor(Protocol):
    """Resume bytes to raw text; raises `ExtractionError` for a scan, a corrupt file or no text."""

    def extract(self, data: bytes, media_type: str) -> str: ...


class Anonymizer(Protocol):
    """Raw text to the only text the model may see, and the name found (or None)."""

    def anonymize(self, raw: str) -> tuple[AnonymizedText, str | None]: ...


class ScoringPrompt(Protocol):
    def build(self, criteria: list[CriterionSpec]) -> PromptText: ...


class ScoreParser(Protocol):
    """Raises `SchemaError` on any deviation from the strict schema (REQ-023)."""

    def parse(self, reply: str, criteria: list[CriterionSpec]) -> list[ParsedScore]: ...


class QuoteVerifier(Protocol):
    """Whitespace normalization only, no fuzzy match (REQ-020)."""

    def verify(self, quote: str, text: AnonymizedText) -> bool: ...


class CriteriaPrompt(Protocol):
    def build(self) -> PromptText: ...

    def parse(self, reply: str) -> list[ProposedCriterion]: ...


class KitPrompt(Protocol):
    def build(self, criterion: CriterionSpec) -> PromptText: ...

    def parse(self, reply: str) -> list[ProposedQuestion]: ...


class AnonymizedLoader(Protocol):
    """Stored anonymized text back into an `AnonymizedText`; implemented by `app.anonymizer`."""

    async def __call__(self, session: AsyncSession, candidate_id: UUID) -> AnonymizedText: ...


class JobDescriptionLoader(Protocol):
    """A role's job description (and, for a kit, one criterion) as `JobDescriptionText`.

    Never candidate data. Implemented by the job-description package, which does not exist yet.
    """

    async def __call__(
        self, session: AsyncSession, role_id: UUID, criterion: CriterionSpec | None = None
    ) -> JobDescriptionText: ...
