"""The contact pass: emails, phone numbers, links and handles. None of it is evidence, so all goes.

Its patterns are its own; the residual scan in `verify.py` has separate, broader ones, so one
defect cannot hide in both. Every pattern is bounded (no nested unbounded quantifier), so the
adversarial test finishes on 150,000-character inputs.
"""

import re

from app.anonymizer.tokens import EMAIL, PHONE, URL, NameSet, Replacement

_EMAIL = re.compile(r"(?<![\w.+%-])[\w.+%-]+@[\w-]+(?:\.[\w-]+)*")
_END = r"[^\s<>]*[^\s<>.,;:)\]]"  # a link ends on a character that is not sentence punctuation
_URL = re.compile(
    rf"\b(?:https?|ftp)://{_END}"
    rf"|\bwww\.{_END}"
    rf"|(?<![\w.@-])[\w-]+(?:\.[\w-]+)*\.com\b(?:/{_END})?"
    rf"|(?<![\w.@-])[\w-]+(?:\.[\w-]+)*\.(?:io|dev|me|net|org|co|ai|in|app)/{_END}",
    re.IGNORECASE,
)
_HANDLE = re.compile(r"(?<![\w.@])@[A-Za-z_]\w{1,30}")
# `Twitter: janedoe`; the value must end its field, so `GitHub: Open source work` is kept.
_HANDLE_FIELD = re.compile(
    r"\b(?:twitter|github|gitlab|linkedin|instagram|telegram|skype|discord)[ \t]*+:[ \t]*+"
    r"(?P<value>[\w.-]{2,40})(?=[ \t]*+(?:$|[|,;]))",
    re.IGNORECASE | re.MULTILINE,
)
# Seven or more digits with separators, an opening bracket or plus allowed; a run made only of
# years (2018 - 2021) is evidence.
_PHONE = re.compile(r"(?<![\w+])[+(]{0,2}\d(?:[ \t.()-]{0,2}\d){6,}+")
_YEAR = re.compile(r"(?:19|20)\d\d")


def contact(text: str, names: NameSet) -> list[Replacement]:
    """Replacements for every email, phone number, link and handle in `text`."""
    found = [Replacement(m.start(), m.end(), EMAIL, "contact") for m in _EMAIL.finditer(text)]
    for pattern in (_URL, _HANDLE):
        found += [Replacement(m.start(), m.end(), URL, "contact") for m in pattern.finditer(text)]
    found += [
        Replacement(m.start("value"), m.end("value"), URL, "contact")
        for m in _HANDLE_FIELD.finditer(text)
    ]
    found += [
        Replacement(m.start(), m.end(), PHONE, "contact")
        for m in _PHONE.finditer(text)
        if not all(_YEAR.fullmatch(g) for g in re.findall(r"\d+", m.group()))
    ]
    return found
