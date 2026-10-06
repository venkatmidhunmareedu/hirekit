"""The residual scan: independent of the passes, it repairs what it finds and counts it.

Contact details, labels and names have patterns of their own, so a defect in one of those cannot
hide in both layers. Titles, pronouns and religion words are different: they read the same word
lists (`data/`) as the passes, so a gap in a list is in both layers. A finding is masked in place
and counted; only a finding that survives its own repair raises `AnonymizationLeakError`. Nothing
here ever puts the leaked string in a message or a log (tenet 7).
"""

import re
from collections import Counter
from pathlib import Path

from app.anonymizer.tokens import (
    AGE,
    DATE,
    EMAIL,
    GENDER,
    NAME,
    PHONE,
    PRONOUN,
    RELIGION,
    TITLE,
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


def _terms(name: str) -> list[str]:
    """The shared word lists in `data/`: read as data, so the scan imports no pass."""
    lines = (Path(__file__).with_name("data") / name).read_text("utf-8").splitlines()
    return [s for line in lines if (s := line.strip()) and s[0] != "#"]


# Brackets count as a boundary here: `[Jane]` and `[her]` are leaks, `[RELIGION]` is not a word.
_RELIGION = re.compile(
    rf"(?<!\w)(?:{'|'.join(map(re.escape, _terms('religion_terms.txt')))})s?(?!\w)", re.IGNORECASE
)
# `Christian` is a first name when it is the candidate's own name part, or when a surname follows
# (a capitalised word that is not an organisation word, or a placeholder such as the `[NAME]` the
# name pass just placed).
_SURNAME_AFTER = re.compile(r"[ \t]+(?:[A-Z][a-z]|\[[A-Z]+\])")
_ORG_AFTER = re.compile(
    r"[ \t]+(?:Youth|Fellowship|Association|Society|Union|Students?|Club|Church|Ministr(?:y|ies)"
    r"|Mission|Group|Community|Choir|Faith|Council|Forum|Centre|Center|University|College|School"
    r"|Medical|Academy|Hospital|Aid)\b"
)
_ALL_CAPS_TOO = frozenset(
    {"mrs", "miss", "madam", "smt", "shri", "kumari", "mme", "mlle", "mister"}
)
_STRICT = frozenset({"lord", "lady"})  # only before a capitalised word or a placeholder
_AFTER = r"(?=\.|[ \t]+(?:[A-Z\[]|or\b)|[ \t]*(?:[,\n]|$))"


def _title_pattern(words: list[str], before: str, after_word: str) -> re.Pattern[str]:
    plain = [re.escape(w) for w in words if w.lower() not in _STRICT]
    plain += [re.escape(w.upper()) for w in words if w.lower() in _ALL_CAPS_TOO]
    strict = [re.escape(w) for w in words if w.lower() in _STRICT]
    return re.compile(
        rf"{before}(?:(?:{'|'.join(plain)}){after_word}\.?{_AFTER}"
        rf"|(?:{'|'.join(strict)}){after_word}(?=[ \t]+[A-Z\[]))",
        re.MULTILINE,
    )


_TITLE = _title_pattern(_terms("titles.txt"), r"(?<!\w)", r"(?!\w)")
_PRONOUN = re.compile(r"(?<!\w)(?:he|him|his|himself|she|her|hers|herself)(?!\w)", re.IGNORECASE)
_PLACEHOLDERS = frozenset(
    {"[NAME]", "[EMAIL]", "[PHONE]", "[URL]", "[LOCATION]", "[ADDRESS]", "[PRONOUN]", "[TITLE]",
     "[DATE]", "[AGE]", "[RELIGION]", "[GENDER]"}
)  # fmt: skip
_WORD = re.compile(r"\w+")
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
    found += [
        Replacement(m.start(), m.end(), RELIGION, "religion")
        for m in _RELIGION.finditer(text)
        if not _is_first_name(text, m, variants)
    ]
    found += [Replacement(m.start(), m.end(), TITLE, "gender") for m in _TITLE.finditer(text)]
    found += [Replacement(m.start(), m.end(), PRONOUN, "gender") for m in _PRONOUN.finditer(text)]
    return found + _name_hits(text, variants)


def _is_first_name(text: str, m: re.Match[str], variants: frozenset[str]) -> bool:
    if m.group().lower() != "christian":
        return False
    if "christian" in variants:
        return True  # the name loop masks it as a name
    return (
        m.group() == "Christian"
        and _SURNAME_AFTER.match(text, m.end()) is not None
        and _ORG_AFTER.match(text, m.end()) is None
    )


def _name_hits(text: str, variants: frozenset[str]) -> list[Replacement]:
    """Every whole-word variant, found in one pass over the text whatever the variant count.

    One-word variants (the many email-derived ones) are looked up per word; the few that hold a
    hyphen or a space go in one alternation. A regex with a branch per address is quadratic.
    """
    words = {v for v in variants if re.fullmatch(r"\w+", v)}
    spans = [(m.start(), m.end()) for m in _WORD.finditer(text) if m.group().lower() in words]
    if rest := sorted(variants - words, key=len, reverse=True):
        multi = re.compile(rf"(?<!\w)(?:{'|'.join(map(re.escape, rest))})(?!\w)", re.IGNORECASE)
        spans += [(m.start(), m.end()) for m in multi.finditer(text)]
    return [
        Replacement(a, b, NAME, "name")
        for a, b in spans
        if text[max(a - 1, 0) : b + 1] not in _PLACEHOLDERS
    ]
