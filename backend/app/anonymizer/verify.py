"""The residual scan: independent of the passes, it repairs what it finds and counts it.

It uses its own, broader patterns and shares no pattern with any pass, so one defect cannot hide in
both. A finding is masked in place and counted; only a finding that survives its own repair raises
`AnonymizationLeakError`. Nothing here ever puts the leaked string in a message or a log (tenet 7).
"""

import re
from collections import Counter

from app.anonymizer.tokens import (
    AGE,
    DATE,
    EMAIL,
    GENDER,
    NAME,
    PHONE,
    RELIGION,
    URL,
    Kind,
    NameSet,
    Replacement,
    apply_replacements,
)
from app.core.errors import DomainError

# Every pattern starts behind a lookbehind and has no nested unbounded quantifier, so each run of
# input is scanned once (the adversarial test runs them on 150,000-character inputs).
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@\w[\w.-]*")
_HANDLE = re.compile(r"(?<![\w.@])@[A-Za-z_]\w{1,30}")
_URL = re.compile(
    r"\bhttps?://[^\s<>]*[^\s<>.,;:)\]]"
    r"|\bwww\.[^\s<>]*[^\s<>.,;:)\]]"
    r"|(?<![\w.-])[\w-]+(?:\.[\w-]+)*\.com\b(?:/[^\s<>]*[^\s<>.,;:)\]])?",
    re.IGNORECASE,
)
# Seven or more digits with separators; a run made only of years (2018 - 2021) is evidence.
_PHONE = re.compile(r"(?<![\w+])\+?\d(?:[ \t.()-]{0,2}\d){6,}+")
_YEAR = re.compile(r"(?:19|20)\d\d")
_LABEL = re.compile(
    r"\b(?P<label>dob|date of birth|born|age|sex|gender|religion)[ \t]*+:[ \t]*+"
    r"(?P<value>(?!\[[A-Z]+\])(?:(?![|;]| {2})[^\n]){1,40})",
    re.IGNORECASE,
)
_LABEL_TOKEN: dict[str, tuple[str, Kind]] = {
    "dob": (DATE, "age"),
    "date of birth": (DATE, "age"),
    "born": (DATE, "age"),
    "age": (AGE, "age"),
    "sex": (GENDER, "gender"),
    "gender": (GENDER, "gender"),
    "religion": (RELIGION, "religion"),
}
_LOCAL_SPLIT = re.compile(r"[._+\d-]+")
# ponytail: a mailbox word that is also a common word (`will.young@`) is masked everywhere here;
# the common-word rule (name positions only) arrives with names.py, work item 3.
_GENERIC_MAILBOXES = frozenset(
    {"info", "mail", "email", "contact", "admin", "hello", "hr", "jobs", "career", "careers",
     "sales", "support", "office", "team", "work", "dev", "me"}
)  # fmt: skip


class AnonymizationLeakError(DomainError):
    """A removed class is still present after the repair. Carries counts by kind, never text."""

    status_code = 500
    code = "anonymization_leak"

    def __init__(self, leaks: Counter[str]) -> None:
        super().__init__(
            "This resume could not be made anonymous, so it was not sent to the model.",
            details={"leaks": dict(leaks)},
        )


def check(normalized: str, text: str, names: NameSet) -> tuple[str, int]:
    """Scan `text`, mask what is found and scan again; return the text and the repair count.

    `normalized` is the input the passes saw: the scan reads email local parts from it, so a name
    is caught even when discovery found none.
    """
    found = _scan(text, _name_variants(normalized, names))
    if not found:
        return text, 0
    repaired, applied = apply_replacements(text, found)
    leaks = _scan(repaired, _name_variants(normalized, names))
    if leaks:
        raise AnonymizationLeakError(Counter(r.kind for r in leaks))
    return repaired, len(applied)


def _name_variants(normalized: str, names: NameSet) -> frozenset[str]:
    from_mail = {
        part
        for m in _EMAIL.finditer(normalized)
        for part in _LOCAL_SPLIT.split(m.group().split("@")[0].lower())
        if len(part) >= 3 and part.isalpha() and part not in _GENERIC_MAILBOXES
    }
    return names.variants | from_mail


def _scan(text: str, variants: frozenset[str]) -> list[Replacement]:
    found = [Replacement(m.start(), m.end(), EMAIL, "contact") for m in _EMAIL.finditer(text)]
    found += [Replacement(m.start(), m.end(), URL, "contact") for m in _URL.finditer(text)]
    found += [Replacement(m.start(), m.end(), URL, "contact") for m in _HANDLE.finditer(text)]
    found += [
        Replacement(m.start(), m.end(), PHONE, "contact")
        for m in _PHONE.finditer(text)
        if not all(_YEAR.fullmatch(g) for g in re.findall(r"\d+", m.group()))
    ]
    for m in _LABEL.finditer(text):
        token, kind = _LABEL_TOKEN[m.group("label").lower()]
        found.append(Replacement(m.start("value"), m.end("value"), token, kind))
    for v in sorted(variants):
        part = re.compile(rf"(?<![\w\[]){re.escape(v)}(?![\w\]])", re.IGNORECASE)
        found += [Replacement(m.start(), m.end(), NAME, "name") for m in part.finditer(text)]
    return found
