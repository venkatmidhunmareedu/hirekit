"""Swapping the candidate's name (and what derives from it) must not change the anonymized text."""

from pathlib import Path

import pytest

from app.anonymizer import anonymize

TEMPLATE = (Path(__file__).parent / "fixtures" / "resume_template.txt").read_text(encoding="utf-8")

PAIRS = [
    ("Jane", "Doe", "Priya", "Raman"),
    ("Mohammed", "Al-Farsi", "Emily", "Clark"),
    ("Wei", "Zhang", "Olivia", "Brown"),
    ("Oluwaseun", "Adeyemi", "Hannah", "Schmidt"),
    ("Aisha", "Khan", "Liam", "Murphy"),
    ("Ravi", "Shankar", "Sofia", "Rossi"),
    ("Chen", "Li", "Anna", "Kowalski"),
    ("Robert", "Hale", "Bob", "Stone"),
]


def render(first: str, last: str, city: str = "Chennai", he_she: str = "She") -> str:
    full = f"{first} {last}"
    return TEMPLATE.format(
        name=full,
        first=first,
        last=last,
        email=f"{first}.{last}@example.com".lower().replace("-", ""),
        phone="+91 98765 43210",
        city=city,
        slug=f"{first}-{last}".lower(),
        he_she=he_she,
    )


def test_swapping_the_candidate_name_gives_byte_identical_anonymized_text() -> None:
    a = anonymize(render("Jane", "Doe"))
    b = anonymize(render("Priya", "Raman"))
    assert a.text.value == b.text.value
    assert a.report.repaired == b.report.repaired == 0
    assert (a.identity_name, b.identity_name) == ("Jane Doe", "Priya Raman")


@pytest.mark.parametrize(("first_a", "last_a", "first_b", "last_b"), PAIRS)
def test_swapping_the_name_across_origins_and_genders_gives_identical_text(
    first_a: str, last_a: str, first_b: str, last_b: str
) -> None:
    a = anonymize(render(first_a, last_a))
    b = anonymize(render(first_b, last_b, he_she="He"))
    assert a.text.value == b.text.value
    for part in (first_a, last_a, first_b, last_b):
        assert part.lower() not in a.text.value.lower().replace("al-farsi", "")
