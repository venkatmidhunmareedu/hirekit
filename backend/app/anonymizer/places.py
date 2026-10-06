"""The places pass: postal codes, street addresses and gazetteer places.

Unambiguous places (most cities, countries, states) are masked anywhere. A word that is also a
skill, a job word, a name or an employer (`Mobile`, `Reading`, `Phoenix`, `Jakarta`, `Nice`,
`Split`, `Bath`, `Jersey`, `Victoria`; `data/ambiguous_places.txt`) is masked only when
capitalised and in a place context, and never inside an employer named there (`Bank of
America`). The rest of a school or employer name stays, so `University of Madras` becomes
`University of [LOCATION]`. Coverage is bounded by the checked-in lists; a small town or a
misspelling can survive.
"""

import re
from bisect import bisect_left, bisect_right
from itertools import pairwise
from pathlib import Path

from app.anonymizer.tokens import ADDRESS, LOCATION, NameSet, Replacement

_DATA = Path(__file__).with_name("data")


def _lines(filename: str) -> list[str]:
    raw = (_DATA / filename).read_text(encoding="utf-8").splitlines()
    return [s.replace(".", "") for line in raw if (s := line.strip()) and s[0] != "#"]


GAZETTEER = frozenset(w for f in ("countries.txt", "states.txt", "cities.txt") for w in _lines(f))
_AMBIGUOUS_LINES = _lines("ambiguous_places.txt")
KEEP = frozenset(s.removeprefix("keep:").strip() for s in _AMBIGUOUS_LINES if s.startswith("keep:"))
AMBIGUOUS = frozenset(s for s in _AMBIGUOUS_LINES if not s.startswith("keep:"))
_MAX_WORDS = 5

_WORD = re.compile(r"[^\W\d_]+(?:['\u2019-][^\W\d_]+)*")
_GAP = re.compile(r"\.?[ \t]+")
_STATES = (
    "AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH"
    "|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY"
)
# Not IN, OR, ME, OK or HI: after a comma those are ordinary words (`, OR`, `, ME`).
_ABBR_ALONE = "|".join(a for a in _STATES.split("|") if a not in {"IN", "OR", "ME", "OK", "HI"})
_CODE = (
    r"\d{5}(?:-\d{4})?|\d{3}[ \t]?\d{3}"
    r"|[A-Z]\d[A-Z][ \t]?\d[A-Z]\d|[A-Z]{1,2}\d[A-Z\d]?[ \t]?\d[A-Z]{2}"
)
_POSTAL = re.compile(
    rf"(?<=, )(?:{_STATES})[ \t]+\d{{5}}(?:-\d{{4}})?\b"  # Austin, CA 94105
    r"|\b[A-Z]{1,2}\d[A-Z\d]?[ \t]?\d[A-Z]{2}\b"  # SW1A 1AA
    r"|\b[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ \t]?\d[ABCEGHJ-NPRSTV-Z]\d\b"  # M5V 3L9
    rf"|(?<=[a-z], )(?:{_ABBR_ALONE})\b(?=[ \t]*(?:$|[,.\n]))"  # Austin, TX
)
_LABELLED_CODE = re.compile(
    rf"\b(?:zip|postal|post|pin)[ \t]*(?:code)?[ \t]*[:\-]?[ \t]*(?P<code>{_CODE})\b", re.IGNORECASE
)
_PIN = re.compile(r"\b[A-Z][a-z]{2,}[ \t]*[,-][ \t]*(?P<pin>[1-9]\d{2}[ \t]?\d{3})\b")
_STREET = re.compile(
    r"\b\d{1,5},?[ \t]+(?:[A-Z][\w.'-]*[ \t]+){1,4}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Place|Pl"
    r"|Square|Sq|Terrace|Highway|Hwy|Nagar|Marg)\b\.?"
    r"|\bP\.?O\.?[ \t]+Box[ \t]+\d+\b"
)
_PREPOSITION = re.compile(
    r"\b(?:in|at|from|near|based in|located in|lives? in|living in|relocat\w*(?: to)?)[ \t]+$",
    re.IGNORECASE,
)
_PLACE_FOLLOWER = re.compile(
    r"[ \t]*(?:$|[,.;:)\-\u2013|/]|[A-Z\d]"
    r"|(?:and|or|but|where|since|for|with|as|until|from|on|at|in|during|before|after)\b)"
)
_LABEL = re.compile(
    r"^[ \t]*(?:current[ \t]+)?(?:location|address|city|residence|hometown)[ \t]*[:\-]?[ \t]*$",
    re.IGNORECASE,
)
_CONTACT_LINE = re.compile(r"@|\+?\d[\d ()-]{8,}")
_HEADER_LINES = 5
_WINDOW = 200


def _phrase_hits(text: str, phrases: frozenset[str]) -> list[tuple[int, int, str]]:
    """(start, end, key) of every phrase of up to five words, longest first, in one scan."""
    words = list(_WORD.finditer(text))
    hits: list[tuple[int, int, str]] = []
    i = 0
    while i < len(words):
        for n in range(min(_MAX_WORDS, len(words) - i), 0, -1):
            span = words[i : i + n]
            if any(_GAP.fullmatch(text, a.end(), b.start()) is None for a, b in pairwise(span)):
                continue
            key = " ".join(w.group().lower() for w in span)
            if key in phrases:
                hits.append((span[0].start(), span[-1].end(), key))
                i += n - 1
                break
        i += 1
    return hits


def _header_end(text: str) -> int:
    pos, seen = 0, 0
    for line in text.split("\n"):
        pos += len(line) + 1
        seen += bool(line.strip())
        if seen == _HEADER_LINES:
            break
    return pos


def mask_places(text: str, names: NameSet) -> list[Replacement]:
    """Replacements for every postal code, street address and gazetteer place in `text`."""
    found = [Replacement(m.start(), m.end(), ADDRESS, "location") for m in _STREET.finditer(text)]
    found += [Replacement(m.start(), m.end(), LOCATION, "location") for m in _POSTAL.finditer(text)]
    for pattern, group in ((_LABELLED_CODE, "code"), (_PIN, "pin")):
        found += [
            Replacement(m.start(group), m.end(group), LOCATION, "location")
            for m in pattern.finditer(text)
        ]
    kept = [(s, e) for s, e, _ in _phrase_hits(text, KEEP)]  # disjoint, in text order
    kept_starts = [s for s, _ in kept]
    hits = [h for h in _phrase_hits(text, GAZETTEER) if not _inside(kept, kept_starts, h[0], h[1])]
    sure = [(s, e) for s, e, k in hits if k not in AMBIGUOUS]
    found += [Replacement(s, e, LOCATION, "location") for s, e in sure]
    anchors = _Anchors(found)
    header_end = _header_end(text)
    found += [
        Replacement(s, e, LOCATION, "location")
        for s, e, k in hits
        if k in AMBIGUOUS
        and text[s].isupper()
        and _in_place_context(text, s, e, anchors, header_end)
    ]
    return found


def _inside(spans: list[tuple[int, int]], starts: list[int], start: int, end: int) -> bool:
    i = bisect_right(starts, start) - 1
    return i >= 0 and end <= spans[i][1]


def _in_place_context(text: str, start: int, end: int, anchors: _Anchors, header_end: int) -> bool:
    # A window, not the whole line: one giant line must not make every hit scan all of it.
    floor, ceiling = max(start - _WINDOW, 0), min(end + _WINDOW, len(text))
    line_start = text.rfind("\n", floor, start) + 1 or floor
    line_end = text.find("\n", end, ceiling)
    line_end = ceiling if line_end < 0 else line_end
    prefix, suffix = text[line_start:start], text[end:line_end]
    if _PREPOSITION.search(prefix[-30:]) and _PLACE_FOLLOWER.match(suffix):
        return True
    if _LABEL.match(prefix) or (not prefix.strip() and _label_above(text, line_start)):
        return True
    if line_start < header_end and _CONTACT_LINE.search(text[line_start:line_end]):
        return True
    before = re.search(r"[ \t]*,[ \t]*$", prefix)
    if before and (line_start + before.start()) in anchors.ends:
        return True
    after = re.match(r"[ \t]*,[ \t]*", suffix)
    return after is not None and anchors.starts_at(end + after.end())


def _label_above(text: str, line_start: int) -> bool:
    above = text[max(line_start - _WINDOW, 0) : line_start].rstrip("\n").rsplit("\n", 1)[-1]
    return _LABEL.match(above) is not None


class _Anchors:
    """Where the places already found start and end, for the comma-list context."""

    def __init__(self, found: list[Replacement]) -> None:
        self.ends = {r.end for r in found}
        self._starts = sorted(r.start for r in found)

    def starts_at(self, pos: int) -> bool:
        i = bisect_left(self._starts, pos)
        return i < len(self._starts) and self._starts[i] == pos
