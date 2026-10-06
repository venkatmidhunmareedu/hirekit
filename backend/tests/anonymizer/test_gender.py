"""The gender pass: fields, titles and pronouns go; neutral titles and look-alike words stay."""

import pytest

from app.anonymizer import anonymize
from app.anonymizer.gender import mask_gender
from app.anonymizer.pipeline import PASSES
from tests.timeout_helper import run_with_timeout


def out(raw: str) -> str:
    result = anonymize(raw)
    assert result.report.repaired == 0, "the pass left something for the residual scan"
    return result.text.value


def test_the_pass_is_registered() -> None:
    assert mask_gender in PASSES


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Gender: Female", "Gender: [GENDER]"),
        ("SEX : M | Python", "SEX : [GENDER] | Python"),
        ("Sex: Prefer not to say   ", "Sex: [GENDER]   "),
        ("Mr. Rao and Mrs Rao", "[TITLE] Rao and [TITLE] Rao"),
        ("Ms. Chen, Mx Lee", "[TITLE] Chen, [TITLE] Lee"),
        ("Miss Patel", "[TITLE] Patel"),
        ("Dear Sir or Madam,", "Dear [TITLE] or [TITLE],"),
    ],
)
def test_gender_field_and_titles_are_masked(raw: str, expected: str) -> None:
    assert out(raw) == expected


def test_gendered_pronouns_inside_sentences_are_masked() -> None:
    raw = "She led the team and he thanked her. His code, hers too, HIMSELF and herself."
    expected = (
        "[PRONOUN] led the team and [PRONOUN] thanked [PRONOUN]. "
        "[PRONOUN] code, [PRONOUN] too, [PRONOUN] and [PRONOUN]."
    )
    assert out(raw) == expected


def test_neutral_titles_and_the_word_her_inside_another_word_are_kept() -> None:
    raw = (
        "Dr. Okoye and Prof. Lund. Other, there, where, the, hero, chairman, shepherd. "
        "Cut p95 to 900 ms; MS Office; they thanked them. Miss a deadline? Never miss it."
    )
    assert out(raw) == raw


def _gender_adversarial_input_finishes_quickly() -> None:
    from app.anonymizer.gender import mask_gender
    from app.anonymizer.tokens import NameSet

    n = 150_000
    for s in [
        "Mr" * (n // 2),
        "Sir " * (n // 4),
        "Gender:" * (n // 7),
        "sex: " + "a" * n,
        "he " * (n // 3),
        "Miss." * (n // 5),
        "Mr\n" * (n // 3),
        "Ms " * (n // 3),
    ]:
        mask_gender(s, NameSet())


def test_gender_adversarial_input_finishes_quickly() -> None:
    """A regex runs in C and cannot be interrupted, so the proof is a subprocess with a timeout."""
    run_with_timeout(_gender_adversarial_input_finishes_quickly, 60)
