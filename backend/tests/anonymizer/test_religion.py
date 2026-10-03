"""The religion pass: a stated religion and religion words go; languages and skills stay."""

import subprocess
import sys
from pathlib import Path

import pytest

from app.anonymizer import anonymize
from app.anonymizer.pipeline import PASSES
from app.anonymizer.religion import mask_religion


def out(raw: str) -> str:
    result = anonymize(raw)
    assert result.report.repaired == 0, "the pass left something for the residual scan"
    return result.text.value


def test_the_pass_is_registered() -> None:
    assert mask_religion in PASSES


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Religion: Hindu", "Religion: [RELIGION]"),
        ("RELIGION : Roman Catholic | Python", "RELIGION : [RELIGION] | Python"),
        ("Religion: Prefer not to say", "Religion: [RELIGION]"),
        (
            "Member of the Catholic Youth Association",
            "Member of the [RELIGION] Youth Association",
        ),
        ("President, Sikh Students Society", "President, [RELIGION] Students Society"),
        ("Volunteer, Hindus and Jains for Food", "Volunteer, [RELIGION] and [RELIGION] for Food"),
        ("Active in the christian union", "Active in the [RELIGION] union"),
        ("Baha'i youth group lead", "[RELIGION] youth group lead"),
        ("Islamic Studies tutor", "[RELIGION] Studies tutor"),
        ("Christian Fellowship treasurer", "[RELIGION] Fellowship treasurer"),
    ],
)
def test_stated_religion_and_affiliations_are_masked(raw: str, expected: str) -> None:
    assert out(raw) == expected


def test_languages_cultural_skills_and_look_alike_words_are_kept() -> None:
    raw = (
        "Languages: Hindi, Urdu, Arabic, Hebrew, Sanskrit. Temple University, Church & Dwight, "
        "Jainsen Corp, Christians. Wrote the Sunnyvale plan.\nChristian Weber referred me."
    )
    expected = raw.replace("Christians", "[RELIGION]")
    assert out(raw) == expected


def test_religion_adversarial_input_finishes_quickly() -> None:
    """A regex runs in C and cannot be interrupted, so the proof is a subprocess with a timeout."""
    code = (
        "from app.anonymizer.religion import mask_religion\n"
        "from app.anonymizer.tokens import NameSet\n"
        "n = 150_000\n"
        "for s in ['hindu' * (n // 5), 'Christian ' * (n // 10), 'religion:' * (n // 9),"
        " 'hare ' * (n // 5), 'jew ' * (n // 4), 'a' * n, 'Christian Z' * (n // 11)]:\n"
        "    mask_religion(s, NameSet())\n"
    )
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-c", code],
        check=True,
        timeout=60,
        cwd=Path(__file__).parents[2],
    )
