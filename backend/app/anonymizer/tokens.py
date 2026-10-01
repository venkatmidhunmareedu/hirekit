"""The fixed placeholders, the replacement and name-set types, and the one place text is edited.

Placeholders are fixed strings, so two inputs that differ only in a removed value give identical
output (the name-swap eval); one never carries the length, shape or first letter of its value.
"""

from bisect import bisect_left
from dataclasses import dataclass, field
from typing import Literal

NAME = "[NAME]"
EMAIL = "[EMAIL]"
PHONE = "[PHONE]"
URL = "[URL]"
LOCATION = "[LOCATION]"
ADDRESS = "[ADDRESS]"
PRONOUN = "[PRONOUN]"
TITLE = "[TITLE]"
DATE = "[DATE]"
AGE = "[AGE]"
RELIGION = "[RELIGION]"
GENDER = "[GENDER]"

Kind = Literal["name", "gender", "age", "religion", "location", "contact"]


@dataclass(frozen=True, slots=True)
class Replacement:
    """Replace `text[start:end]` with `token`; `kind` is the field it protects."""

    start: int
    end: int
    token: str
    kind: Kind


@dataclass(frozen=True, slots=True)
class NameSet:
    """The candidate's name as found in their own document: `full` for the reveal, and the
    lowercase `variants` (parts, nicknames, reversed forms) every pass and the scan look for."""

    full: str | None = None
    variants: frozenset[str] = field(default_factory=frozenset)


def apply_replacements(text: str, replacements: list[Replacement]) -> tuple[str, list[Replacement]]:
    """Rebuild `text` once. Of two overlapping matches the longer one's token wins (the earlier
    start on a tie); a match that only partly overlaps is merged into it, so no part of either
    survives. Returns the new text and the replacements applied, in text order.
    """
    kept: list[Replacement] = []  # disjoint, sorted by start
    starts: list[int] = []
    for r in sorted(replacements, key=lambda r: (r.start - r.end, r.start)):
        # Kept ones are at least as long as `r`, so only the nearest on each side can overlap it.
        lo = bisect_left(starts, r.start)
        near = range(max(lo - 1, 0), min(lo + 1, len(kept)))
        hit = [n for n in near if r.start < kept[n].end and kept[n].start < r.end]
        if not hit:
            kept.insert(lo, r)
            starts.insert(lo, r.start)
            continue
        if all(kept[n].start <= r.start and r.end <= kept[n].end for n in hit):
            continue
        owner = max((kept[n] for n in hit), key=lambda k: k.end - k.start)
        merged = Replacement(
            min(r.start, kept[hit[0]].start),
            max(r.end, kept[hit[-1]].end),
            owner.token,
            owner.kind,
        )
        kept[hit[0] : hit[-1] + 1] = [merged]
        starts[hit[0] : hit[-1] + 1] = [merged.start]
    out: list[str] = []
    pos = 0
    for r in kept:
        out.extend((text[pos : r.start], r.token))
        pos = r.end
    out.append(text[pos:])
    return "".join(out), kept
