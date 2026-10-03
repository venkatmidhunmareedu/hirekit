"""The religion pass: a `Religion:` field and every religion word on `data/religion_terms.txt`.

An affiliation keeps its shape (`Member of the [RELIGION] Youth Association`); only the religion
word goes. `Christian` is also a first name, so a capitalised `Christian` followed by another
capitalised word that is not an organisation word is left to the name pass.
The scan in `verify.py` has its own label pattern, so a gap in the field is repaired and counted.
"""

import re
from pathlib import Path

from app.anonymizer.tokens import RELIGION, NameSet, Replacement

_TERMS = sorted(
    (
        s
        for line in (Path(__file__).with_name("data") / "religion_terms.txt")
        .read_text("utf-8")
        .splitlines()
        if (s := line.strip()) and s[0] != "#"
    ),
    key=len,
    reverse=True,
)
_WORD = re.compile(
    rf"(?<![\w\[])(?:{'|'.join(re.escape(t) for t in _TERMS)})s?(?![\w\]])", re.IGNORECASE
)
_FIELD = re.compile(r"\breligion[ \t]*+:[ \t]*+(?P<value>(?!\[)[^\n|;]{1,40})", re.IGNORECASE)
_ORG_WORD = re.compile(
    r"[ \t]+(?:Youth|Fellowship|Association|Society|Union|Students?|Club|Church|Ministry|Mission"
    r"|Group|Community|Choir|Faith|Council|Forum|Centre|Center)\b"
)
_CAPITALISED_WORD = re.compile(r"[ \t]+[A-Z][a-z]")


def mask_religion(text: str, names: NameSet) -> list[Replacement]:
    """Replacements for every stated religion and religion word in `text`."""
    found = [
        Replacement(m.start(), m.end(), RELIGION, "religion")
        for m in _WORD.finditer(text)
        if not _is_a_first_name(text, m)
    ]
    for m in _FIELD.finditer(text):
        end = m.start("value") + len(m.group("value").rstrip())
        found.append(Replacement(m.start("value"), end, RELIGION, "religion"))
    return found


def _is_a_first_name(text: str, m: re.Match[str]) -> bool:
    word = m.group()
    return (
        word == "Christian"
        and _CAPITALISED_WORD.match(text, m.end()) is not None
        and _ORG_WORD.match(text, m.end()) is None
    )
