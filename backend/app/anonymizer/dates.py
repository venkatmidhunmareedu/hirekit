"""The dates pass: dates of birth, stated ages and graduation dates.

Employment dates stay: they are evidence, and a proxy for age that remains (anonymization is a
floor, not proof of fairness). A full day-month-year date is read as a birth date wherever it
stands; a month or a year alone is masked only after a graduation cue or in an education line or
section.
The scan in `verify.py` has its own label patterns, so a gap here is repaired and counted there.
"""

import re

from app.anonymizer.tokens import AGE, DATE, NameSet, Replacement

_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_YEAR = r"(?:19|20)\d\d"
_DAY = r"(?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?"
_FULL_DATE = re.compile(
    rf"(?<![\w.])(?:"
    rf"{_DAY}[ \t]+(?:of[ \t]+)?{_MONTH}\.?,?[ \t]+{_YEAR}"  # 12 March 1990
    rf"|{_MONTH}\.?[ \t]+{_DAY},?[ \t]+{_YEAR}"  # March 12, 1990
    rf"|{_YEAR}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])"  # 1990-03-12
    rf"|\d{{1,2}}[/.-]\d{{1,2}}[/.-]{_YEAR}"  # 12/03/1990, 03-12-1990
    rf"|\d\d[/.-]\d\d[/.-]\d\d"  # 12.03.90
    rf")(?![\w])",
    re.IGNORECASE,
)
# A date inside an education line: a year, a month and year, or numeric month/year.
_PART_DATE = re.compile(
    rf"(?<![\w.])(?:(?:{_MONTH}\.?,?[ \t]+)?{_YEAR}|\d{{1,2}}[/.-]{_YEAR})(?![\w])", re.IGNORECASE
)
_BIRTH_LABEL = re.compile(
    r"\b(?:d\.?o\.?b\.?|date[ \t]+of[ \t]+birth|born(?:[ \t]+on)?)\b[ \t]*+(?::[ \t]*+)?",
    re.IGNORECASE,
)
_VALUE = re.compile(r"(?!\[)[^\n|;]{1,40}")
_AGE_FIELD = re.compile(r"\bage[ \t]*+:[ \t]*+(?P<value>(?!\[)[^\n|;]{1,40})", re.IGNORECASE)
_AGE_PHRASE = re.compile(
    r"\b(?:1[6-9]|[2-9]\d)(?:[ \t]*-[ \t]*|[ \t]+)(?:years?|yrs?)(?:[ \t]*-[ \t]*|[ \t]+)old\b"
    r"|\b(?:aged?|age[ \t]+of)[ \t]+(?:1[6-9]|[2-9]\d)\b",
    re.IGNORECASE,
)
_CUE = re.compile(r"\b(?:graduat(?:ed|ion|ing)|class[ \t]+of|batch[ \t]+of)\b", re.IGNORECASE)
_CUE_REACH = 40
_EDU_HEADING = re.compile(
    r"^[ \t]*(?:education(?:al)?(?:[ \t]+(?:and|&)[ \t]+training|[ \t]+background)?"
    r"|academics?|qualifications?|academic[ \t]+(?:background|qualifications?))[ \t]*:?[ \t]*$",
    re.IGNORECASE,
)
_HEADINGS = frozenset(
    {"experience", "work experience", "employment", "skills", "projects", "certifications",
     "summary", "profile", "objective", "references", "awards", "publications", "languages",
     "interests", "achievements", "work history", "professional experience", "technical skills",
     "personal details", "personal information", "declaration", "hobbies", "volunteering"}
)  # fmt: skip
_EDU_LINE = re.compile(
    r"\b(?:universit(?:y|ies)|college|institute|school|academy|bachelors?|masters?|mba|ph\.?d"
    r"|diploma|b\.?tech|m\.?tech|b\.?sc|m\.?sc|b\.?e|degree|c?gpa)\b",
    re.IGNORECASE,
)


def _is_heading(line: str) -> bool:
    s = line.strip().rstrip(":").strip()
    return 0 < len(s) <= 30 and (
        s.lower() in _HEADINGS or (s.isupper() and not any(c.isdigit() for c in s))
    )


def _education_lines(text: str) -> list[tuple[int, int]]:
    """(start, end) of every line in an education section or that reads like an education line."""
    spans: list[tuple[int, int]] = []
    in_section = False
    pos = 0
    for line in text.split("\n"):
        end = pos + len(line)
        if _EDU_HEADING.match(line):
            in_section = True
        elif in_section and _is_heading(line):
            in_section = False
        elif in_section or _EDU_LINE.search(line):
            spans.append((pos, end))
        pos = end + 1
    return spans


def mask_dates(text: str, names: NameSet) -> list[Replacement]:
    """Replacements for every birth date, stated age and graduation date in `text`."""
    found = [Replacement(m.start(), m.end(), DATE, "age") for m in _FULL_DATE.finditer(text)]
    found += [Replacement(m.start(), m.end(), AGE, "age") for m in _AGE_PHRASE.finditer(text)]
    for m in _AGE_FIELD.finditer(text):
        found.append(
            Replacement(
                m.start("value"), m.start("value") + len(m.group("value").rstrip()), AGE, "age"
            )
        )
    for m in _BIRTH_LABEL.finditer(text):
        colon = ":" in m.group()
        v = _VALUE.match(text, m.end()) if colon else _FULL_DATE.match(text, m.end())
        if v:
            found.append(Replacement(v.start(), v.start() + len(v.group().rstrip()), DATE, "age"))
    for m in _CUE.finditer(text):
        eol = text.find("\n", m.end())
        found += _part_dates(
            text, m.end(), min(len(text) if eol < 0 else eol, m.end() + _CUE_REACH)
        )
    for start, end in _education_lines(text):
        found += _part_dates(text, start, end)
    return found


def _part_dates(text: str, start: int, end: int) -> list[Replacement]:
    return [
        Replacement(m.start(), m.end(), DATE, "age") for m in _PART_DATE.finditer(text, start, end)
    ]
