"""The gender pass: `Gender:` and `Sex:` fields, gendered titles and gendered pronouns.

Neutral titles (`Dr`, `Prof`) and gendered nouns (`chairman`) stay: the second is a proxy that
remains (anonymization is a floor, not proof of fairness). The scan in `verify.py` has its own
field pattern, so a gap here is repaired and counted there.
"""

import re
from pathlib import Path

from app.anonymizer.tokens import GENDER, PRONOUN, TITLE, NameSet, Replacement

_TITLES = tuple(
    s
    for line in (Path(__file__).with_name("data") / "titles.txt").read_text("utf-8").splitlines()
    if (s := line.strip()) and s[0] != "#"
)
_TITLE = re.compile(
    rf"(?<![\w\[])(?:{'|'.join(_TITLES)})(?![\w\]])\.?"
    r"(?=\.|[ \t]+(?:[A-Z\[]|or\b)|[ \t]*(?:[,\n]|$))",
    re.MULTILINE,
)
_PRONOUN = re.compile(
    r"(?<![\w\[])(?:he|him|his|himself|she|her|hers|herself)(?![\w\]])", re.IGNORECASE
)
_FIELD = re.compile(r"\b(?:gender|sex)[ \t]*+:[ \t]*+(?P<value>(?!\[)[^\n|;]{1,40})", re.IGNORECASE)


def mask_gender(text: str, names: NameSet) -> list[Replacement]:
    """Replacements for every gender field value, title and pronoun in `text`."""
    found = [Replacement(m.start(), m.end(), TITLE, "gender") for m in _TITLE.finditer(text)]
    found += [Replacement(m.start(), m.end(), PRONOUN, "gender") for m in _PRONOUN.finditer(text)]
    for m in _FIELD.finditer(text):
        value = m.group("value").rstrip()
        found.append(Replacement(m.start("value"), m.start("value") + len(value), GENDER, "gender"))
    return found
