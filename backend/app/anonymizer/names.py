"""Find the candidate's name in their own document, then remove it and its variants.

`discover` reads a `Name:` field, the header block or the email address; `mask_names` removes the
full name, every part that is not an ordinary word, initials and nicknames. A part that is also a
common word (`Will`, `Rose`, `Young`) is masked in name positions only, so "I will lead a young
team" stays whole. Every discovered value goes through `re.escape` before it becomes a pattern and
is capped at 80 characters, so a name can never be a regex. Patterns are bounded; the adversarial
test runs them on 150,000-character inputs.
"""

import re
from functools import cache
from pathlib import Path

from app.anonymizer.tokens import NAME, NameSet, Replacement

MAX_NAME_CHARS = 80
_DATA = Path(__file__).with_name("data")
_WORD = r"[^\W\d_]+(?:['\u2019.-][^\W\d_]+)*"
_PARTICLES = frozenset(
    {"van", "der", "den", "de", "del", "della", "di", "da", "dos", "du", "la", "le", "von"}
    | {"bin", "bint", "al", "el", "ibn", "ter", "ten"}
)
_EMAIL = re.compile(r"(?<![\w.+%-])([\w.+%-]+)@[\w-]+(?:\.[\w-]+)*")
_LOCAL_SPLIT = re.compile(r"[._+%\d-]+")
_GENERIC_MAILBOXES = frozenset(
    {"info", "mail", "email", "contact", "admin", "hello", "hr", "jobs", "career", "careers",
     "sales", "support", "office", "team", "work", "dev", "me"}
)  # fmt: skip
_SEGMENT_SPLIT = re.compile(r"[|\u2022\u00b7\u2013\u2014/]| {2,}")
_FIELD = re.compile(
    r"^[ \t]*(?:candidate[ \t]+|full[ \t]+)?name[ \t]*:[ \t]*+([^\n]+)", re.I | re.M
)
_CANDIDATE_FIELD = re.compile(r"^[ \t]*candidate[ \t]*:[ \t]*+([^\n]+)", re.I | re.M)
_SIGNOFF = re.compile(
    r"^[ \t]*(?:best regards|kind regards|warm regards|regards|yours sincerely|sincerely|thanks)"
    r"[ \t]*,?[ \t]*\n+[ \t]*+([^\n]+)",
    re.I | re.M,
)
_LETTERS = re.compile(r"[^\W\d_]+")
_NICK_WORD = r"[A-Z][a-z]{1,11}"
_NICK_SUFFIX = re.compile(rf"[ \t]*[(\"\u201c']{_NICK_WORD}[)\"\u201d']\s*$")
_NICK_PHRASE = re.compile(
    r"(?:\b(?:is|am|was|also|usually|often|commonly)[ \t]+called|\b[Kk]nown[ \t]+as|\b[Nn]icknamed"
    r"|\bgo(?:es)?[ \t]+by|\bcalls?[ \t]+(?:me|her|him|them)"
    r"|\b(?:[Ff]riends|[Cc]olleagues|[Ee]veryone|[Pp]eople)[ \t]+use)"
    rf"[ \t]+[\"'\u201c(]?({_NICK_WORD})\b"
    rf"|\b({_NICK_WORD})[ \t]+to[ \t]+(?:my|her|his|their)[ \t]+(?:friends|colleagues|team)"
)
_HEADER_LINES = 5


@cache
def _words(filename: str) -> frozenset[str]:
    lines = (_DATA / filename).read_text(encoding="utf-8").splitlines()
    return frozenset(s.lower() for line in lines if (s := line.strip()) and s[0] != "#")


@cache
def _nickname_groups() -> tuple[frozenset[str], ...]:
    lines = (_DATA / "nicknames.txt").read_text(encoding="utf-8").splitlines()
    return tuple(
        frozenset(line.lower().split())
        for line in lines
        if line.strip()[:1] != "#" and line.strip()
    )


def _plausible(segment: str) -> str | None:
    """`segment` as a full name (two to four Title or UPPER case words), else None."""
    text = " ".join(segment.strip(" \t,.:").split())
    if not text or len(text) >= MAX_NAME_CHARS:
        return None
    words = text.split(" ")
    if words[0].rstrip(".").lower() in _words("titles.txt"):  # `Mr John Smith` is `John Smith`
        words, text = words[1:], " ".join(words[1:])
    real = [w for w in words if w.lower() not in _PARTICLES]
    if not 2 <= len(real) <= 4 or len(words) > 6:
        return None
    if not all(re.fullmatch(_WORD, w) for w in words) or not all(w[0].isupper() for w in real):
        return None
    stop = _words("name_stoplist.txt")
    if text.lower() in stop or any(w.lower() in stop for w in words):
        return None
    return text


def _from_segments(line: str) -> list[str]:
    return [
        name
        for seg in _SEGMENT_SPLIT.split(line)
        if (name := _plausible(_NICK_SUFFIX.sub("", seg)))
    ]


def _email_local(text: str) -> str:
    m = _EMAIL.search(text)
    return m.group(1).lower() if m else ""


def discover(text: str) -> NameSet:
    """The candidate's name as the document states it: a `Name:` field, then the first five
    non-empty lines, then the email local part (`jane.doe@`). An email, when there is one,
    cross-checks a header candidate; with none matching, the first plausible one is kept.
    """
    local = _email_local(text)
    found: list[str] = []
    for m in (*_FIELD.finditer(text), *_CANDIDATE_FIELD.finditer(text)):
        found += _from_segments(m.group(1))
    lines = [ln for ln in text.split("\n") if ln.strip()][:_HEADER_LINES]
    for line in lines:
        found += _from_segments(line)
    full = next((n for n in found if _agrees(n, local)), None)
    if full is None:
        parts = [p for p in _LOCAL_SPLIT.split(local) if p.isalpha() and len(p) >= 2]
        if len(parts) >= 2 and not set(parts) & _GENERIC_MAILBOXES:
            full = " ".join(p.capitalize() for p in parts[:4])
    if full is None and found:
        full = found[0]
    if full is None:
        return NameSet()
    always, _ = split_parts(full)
    return NameSet(full, always)


def _agrees(name: str, local: str) -> bool:
    return not local or any(p in local for p in _tokens(name) if len(p) >= 3)


def _lower(text: str) -> str:
    """Lowercase without the combining dot that `İ` leaves, so `İlkay` becomes `ilkay`."""
    return text.lower().replace("\u0307", "")


def _tokens(name: str) -> list[str]:
    """The lowercase parts of `name` (hyphenated parts apart), particles left out."""
    return [p for p in _LETTERS.findall(_lower(name)) if p not in _PARTICLES]


def stated_nicknames(text: str, full: str) -> frozenset[str]:
    """Single-word nicknames the document states: `known as Fati`, `go by Pri`, `called Ash`,
    `nicknamed Han`, `friends call me Oly`, and `(Em)` or `"Em"` right after the name in the
    header. Title case, two to twelve letters, never a stop-list word. Values are matched later
    through `re.escape`, never as patterns."""
    found = {m.group(1) or m.group(2) for m in _NICK_PHRASE.finditer(text)}
    head = "\n".join([ln for ln in text.split("\n") if ln.strip()][:_HEADER_LINES])
    after = rf"{re.escape(full)}[ \t]*[(\"\u201c']({_NICK_WORD})[)\"\u201d']"
    found |= {m.group(1) for m in re.finditer(after, head)}
    stop = _words("name_stoplist.txt")
    return frozenset(n.lower() for n in found if n.lower() not in stop)


def split_parts(
    full: str, nicknames: frozenset[str] = frozenset()
) -> tuple[frozenset[str], frozenset[str]]:
    """The lowercase words that identify `full`: (masked anywhere, masked in name positions only).

    The second set holds common words and parts under three letters (a stated nickname of two
    letters is masked anywhere unless it is a common word).
    """
    parts = set(_tokens(full)) | nicknames
    first = _tokens(full)[0] if _tokens(full) else ""
    for group in _nickname_groups():
        if first in group:
            parts |= group
    common = _words("common_word_names.txt")
    position_only = {p for p in parts if p in common or (len(p) < 3 and p not in nicknames)}
    return frozenset(parts - position_only), frozenset(position_only)


def _spans(text: str, known: frozenset[str]) -> list[tuple[int, int]]:
    """Where the candidate's name is expected: the header block, a name field, a signature, and
    any line that holds nothing but the name."""
    spans: list[tuple[int, int]] = []
    pos, seen = 0, 0
    for line in text.split("\n"):
        end = pos + len(line)
        if line.strip() and seen < _HEADER_LINES:
            seen += 1
            spans.append((pos, end))
        words = [w.lower() for w in _LETTERS.findall(line)]
        if (
            words
            and all(w in known or len(w) == 1 for w in words)
            and any(w in known for w in words)
        ):
            spans.append((pos, end))
        pos = end + 1
    for pattern in (_FIELD, _CANDIDATE_FIELD, _SIGNOFF):
        spans += [(m.start(1), m.end(1)) for m in pattern.finditer(text)]
    return spans


def _is_placeholder(text: str, start: int, end: int) -> bool:
    """`[NAME]` and its kin: an earlier run's placeholder is never a name (a candidate Name)."""
    return text[max(start - 1, 0) : start] == "[" and text[end : end + 1] == "]"


def _rx(body: str, flags: int = re.IGNORECASE) -> re.Pattern[str]:
    """`body` as a whole word that is not already part of a word or a placeholder."""
    return re.compile(rf"(?<!\w)(?:{body})(?!\w)", flags)


def _alt(words: list[str] | frozenset[str] | set[str]) -> str:
    """`words` as alternatives, longest first; a hyphen also matches a space (`Mary Ann`)."""
    return "|".join(
        re.escape(w).replace("\\-", "[ -]") for w in sorted(words, key=len, reverse=True)
    )


def mask_names(text: str, names: NameSet) -> list[Replacement]:
    """Replacements for the candidate's name in every form; none when no name was found."""
    if names.full is None or len(names.full) >= MAX_NAME_CHARS:
        return []
    always, position_only = split_parts(names.full, stated_nicknames(text, names.full))
    words = _tokens(names.full)
    found: list[Replacement] = []

    def add(pattern: re.Pattern[str], start: int = 0, end: int | None = None) -> None:
        found.extend(
            Replacement(m.start(), m.end(), NAME, "name")
            for m in pattern.finditer(text, start, len(text) if end is None else end)
            if not _is_placeholder(text, m.start(), m.end())
        )

    hyphenated = {_lower(w) for w in re.findall(_WORD, names.full) if "-" in w}
    add(_rx(r"[ \t\n.]{1,3}".join(_alt([w]) for w in re.findall(_WORD, names.full))))
    if always:
        add(_rx(_alt(always | hyphenated)))
    if len(words) >= 2:
        first, last = re.escape(words[0]), re.escape(words[-1])
        initial = re.escape(words[0][0])
        add(_rx(rf"{last}[ \t]*,[ \t]*{first}"))  # Doe, Jane
        add(_rx(rf"{initial}\.[ \t]*(?:[A-Za-z]\.[ \t]*)?{last}"))  # J. Doe
        add(_rx(rf"{last}[ \t]*,[ \t]*{initial}\.?"))  # Doe, J
    known = always | position_only | frozenset(words)
    for m in _NICK_PHRASE.finditer(text):  # the phrase itself is a name position
        g = 1 if m.group(1) else 2
        if _lower(m.group(g)) in position_only and not _is_placeholder(text, m.start(g), m.end(g)):
            found.append(Replacement(m.start(g), m.end(g), NAME, "name"))
    for start, end in _spans(text, known):
        if position_only:
            add(_rx(_alt(position_only)), start, end)
        if len(words) >= 2:
            letters = [re.escape(w[0].upper()) for w in words]
            add(_rx(r"\.?[ \t]?".join(letters) + r"\.?", 0), start, end)  # JD, J.D.
            add(_rx(rf"{letters[0]}\.?[ \t]+{re.escape(words[-1])}"), start, end)  # J Doe
    return found
