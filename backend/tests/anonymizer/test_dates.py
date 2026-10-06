"""The dates pass: birth dates, ages and graduation dates go; employment dates stay."""

import subprocess
import sys
from pathlib import Path

import pytest

from app.anonymizer import anonymize
from app.anonymizer.dates import mask_dates
from app.anonymizer.pipeline import PASSES


def out(raw: str) -> str:
    result = anonymize(raw)
    assert result.report.repaired == 0, "the pass left something for the residual scan"
    return result.text.value


def test_the_pass_is_registered() -> None:
    assert mask_dates in PASSES


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("DOB: 12/03/1990", "DOB: [DATE]"),
        ("Date of Birth: 03-12-1990", "Date of Birth: [DATE]"),
        ("Born 12 March 1990 in a town", "Born [DATE] in a town"),
        ("Born: March 12, 1990", "Born: [DATE]"),
        ("DOB 1990-03-12", "DOB [DATE]"),
        ("D.O.B: 12.03.90", "D.O.B: [DATE]"),
        ("Born on 5th Sept 1988", "Born on [DATE]"),
        ("Born: sometime in spring", "Born: [DATE]"),
        ("Shipped on 12 March 2021", "Shipped on [DATE]"),
    ],
)
def test_a_date_of_birth_in_each_of_six_formats_is_masked(raw: str, expected: str) -> None:
    assert out(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Age: 34", "Age: [AGE]"),
        ("AGE : 34 years | Python", "AGE : [AGE] | Python"),
        ("A 34 years old engineer", "A [AGE] engineer"),
        ("A 34-year-old engineer", "A [AGE] engineer"),
        ("A 34 yrs old engineer", "A [AGE] engineer"),
        ("Engineer aged 34", "Engineer [AGE]"),
        ("At the age of 34 I moved", "At the [AGE] I moved"),
    ],
)
def test_a_stated_age_in_each_phrasing_is_masked(raw: str, expected: str) -> None:
    assert out(raw) == expected


def test_graduation_years_in_the_education_section_are_masked() -> None:
    raw = (
        "Education\n"
        "B.Tech, Computer Science, 2012 - 2016\n"
        "Higher secondary, 05/2010\n"
        "\n"
        "Experience\n"
        "Acme Logistics, 2018 - 2021\n"
        "Graduated in May 2016 with honours\n"
        "Class of 2016, batch of 2012\n"
        "Taught at State University 2019 - 2020\n"
    )
    assert out(raw) == (
        "Education\n"
        "B.Tech, Computer Science, [DATE] - [DATE]\n"
        "Higher secondary, [DATE]\n"
        "\n"
        "Experience\n"
        "Acme Logistics, 2018 - 2021\n"
        "Graduated in [DATE] with honours\n"
        "Class of [DATE], batch of [DATE]\n"
        "Taught at State University [DATE] - [DATE]\n"
    )


def test_employment_dates_are_kept() -> None:
    raw = (
        "Experience\nAcme Logistics, Jan 2018 - Mar 2021\nGlobex 03/2015 - 12/2017\n"
        "Built it in 2019. Python 3.12.1, v1.2.34, 1,200,000 users, p95 900 ms, 3.14.0\n"
    )
    assert out(raw) == raw


def test_dates_adversarial_input_finishes_quickly() -> None:
    """A regex runs in C and cannot be interrupted, so the proof is a subprocess with a timeout."""
    code = (
        "from app.anonymizer.dates import mask_dates\n"
        "from app.anonymizer.tokens import NameSet\n"
        "n = 150_000\n"
        "for s in ['1/' * (n // 2), '1 ' * (n // 2), 'march ' * (n // 6), 'Born ' * (n // 5),"
        " 'DOB:' + ' ' * n, 'age:' * (n // 4), '12 ' * (n // 3), 'graduated ' * (n // 10),"
        " 'Education\\n' + 'University 2012\\n' * (n // 16), '1990-' * (n // 5), '9' * n,"
        " 'aged ' * (n // 5), '1-' * (n // 2)]:\n"
        "    mask_dates(s, NameSet())\n"
    )
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-c", code],
        check=True,
        timeout=60,
        cwd=Path(__file__).parents[2],
    )
