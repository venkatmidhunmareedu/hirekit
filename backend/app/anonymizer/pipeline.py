"""`anonymize`: normalize, run the passes, rebuild the text once, verify, mint."""

import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from app.anonymizer.contact import contact
from app.anonymizer.dates import mask_dates
from app.anonymizer.gender import mask_gender
from app.anonymizer.names import discover, mask_names
from app.anonymizer.places import mask_places
from app.anonymizer.religion import mask_religion
from app.anonymizer.tokens import NameSet, Replacement, apply_replacements
from app.anonymizer.verify import check
from app.core.errors import DomainError
from app.gateway.text import AnonymizedText, mint_anonymized

# Bump on every change to a pattern or word list: the replay key hashes the anonymized text, so an
# edit re-keys recordings, and a stored text can be told from a new one (work item 10).
ANONYMIZER_VERSION = 1
MAX_INPUT_CHARS = 500_000

Pass = Callable[[str, NameSet], list[Replacement]]
# Each pass is a pure `text -> list[Replacement]`; the passes are added by work items 2 to 7.
# Of two equal-length matches the earlier pass wins. Dates and places run before contact, so
# `03-12-1990` and `94105-1234` (also phone-shaped runs) are labelled a date and a postal code;
# names run before places, so a candidate called Sofia is a name, not a city.
PASSES: tuple[Pass, ...] = (
    mask_dates,
    mask_names,
    mask_places,
    contact,
    mask_gender,
    mask_religion,
)

_NEWLINES = re.compile(r"\r\n?")


class InputTooLargeError(DomainError):
    """The input is over `MAX_INPUT_CHARS`; the same input fails again, so it is permanent."""

    status_code = 413
    code = "input_too_large"

    def __init__(self) -> None:
        super().__init__("This file is too long to process.")


@dataclass(frozen=True, slots=True)
class AnonymizationReport:
    """Counts only, so it is safe to log (tenet 7)."""

    masked: dict[str, int]
    name_found: bool
    repaired: int
    anonymizer_version: int


@dataclass(frozen=True, slots=True)
class Anonymized:
    text: AnonymizedText
    identity_name: str | None
    report: AnonymizationReport


def normalize(raw: str) -> str:
    """NFKC (ligatures fold), no format characters, plain spaces, `\\n` newlines.

    Matching later runs on this text itself, never on a casefolded copy, so offsets cannot shift.
    """
    text = unicodedata.normalize("NFKC", raw)
    text = "".join(
        " " if unicodedata.category(c) == "Zs" else c
        for c in text
        if unicodedata.category(c) != "Cf"
    )
    return _NEWLINES.sub("\n", text)


def anonymize(raw: str) -> Anonymized:
    """Turn one resume's raw text into the only text the model may see."""
    return _run(raw, PASSES)


def _run(raw: str, passes: tuple[Pass, ...]) -> Anonymized:
    if len(raw) > MAX_INPUT_CHARS:
        raise InputTooLargeError
    text = normalize(raw)
    if not text.strip():
        msg = "cannot anonymize an empty text"
        raise ValueError(msg)
    names = discover(text)
    replacements = [r for p in passes for r in p(text, names)]
    out, applied = apply_replacements(text, replacements)
    out, repaired = check(text, out, names)
    report = AnonymizationReport(
        masked=dict(Counter(r.kind for r in applied)),
        name_found=names.full is not None,
        repaired=repaired,
        anonymizer_version=ANONYMIZER_VERSION,
    )
    return Anonymized(mint_anonymized(out), names.full, report)
