"""The residual scan: independent of the passes, it repairs and counts, and raises only if its
own repair fails. It never puts what it found into a message (tenet 7)."""

import ast
from pathlib import Path

import pytest

from app.anonymizer import verify
from app.anonymizer.pipeline import Anonymized, _run
from app.anonymizer.tokens import NameSet, Replacement
from app.anonymizer.verify import AnonymizationLeakError, check
from tests.timeout_helper import run_with_timeout


def scan_only(raw: str) -> Anonymized:
    """No passes, so every finding below comes from the residual scan alone."""
    return _run(raw, ())


JANE = NameSet("Jane Doe", frozenset({"jane", "doe"}))


def test_the_scan_repairs_an_email_and_counts_it() -> None:
    result = scan_only("Reach me at jane.doe@example.com for details.")
    assert result.text.value == "Reach me at [EMAIL] for details."
    assert result.report.repaired == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Phone: +1 (555) 123-4567", "Phone: [PHONE]"),
        ("Call 555.123.4567 now", "Call [PHONE] now"),
        ("See https://example.com/in/jane-doe.", "See [URL]."),
        ("Site www.janedoe.dev/portfolio, thanks", "Site [URL], thanks"),
        ("Site janedoe.com ok", "Site [URL] ok"),
        ("Twitter @janedoe", "Twitter [URL]"),
        ("DOB: 12/03/1990", "DOB: [DATE]"),
        ("Born: 12 March 1990", "Born: [DATE]"),
        ("Age: 34 years", "Age: [AGE]"),
        ("Gender: Female", "Gender: [GENDER]"),
        ("Sex: M", "Sex: [GENDER]"),
        ("Religion: Hindu", "Religion: [RELIGION]"),
    ],
)
def test_the_scan_repairs_each_class_it_covers(raw: str, expected: str) -> None:
    result = scan_only(raw)
    assert result.text.value == expected
    assert result.report.repaired == 1


def test_year_ranges_and_numbers_that_are_evidence_are_kept() -> None:
    raw = "2018 - 2021, 2015-2018, 2019 2020 2021. Cut cost by 1,200,000 over 12 months. v3.12.1"
    assert scan_only(raw).text.value == raw


def test_the_scan_masks_a_discovered_name_part_and_counts_it() -> None:
    out, repaired = check("Jane Doe wrote this", "Jane Doe wrote this", JANE)
    assert out == "[NAME] [NAME] wrote this"
    assert repaired == 2


def test_a_name_part_inside_a_word_or_a_placeholder_is_not_a_hit() -> None:
    out, repaired = check(
        "x", "Janet [NAME] doesn't ask", NameSet("Jane Doe", frozenset({"jane", "doe"}))
    )
    assert (out, repaired) == ("Janet [NAME] doesn't ask", 0)


def test_the_scan_checks_an_email_local_part_even_when_no_name_was_found() -> None:
    normalized = "Mail: jane.doe@example.com\nJane Doe built a payments service."
    text = "Mail: [EMAIL]\nJane Doe built a payments service."
    out, repaired = check(normalized, text, NameSet())
    assert out == "Mail: [EMAIL]\n[NAME] [NAME] built a payments service."
    assert repaired == 2


def test_a_generic_mailbox_name_does_not_mask_ordinary_words() -> None:
    raw = "Mail: info@example.com\nRan the info desk and the contact centre."
    assert scan_only(raw).text.value == "Mail: [EMAIL]\nRan the info desk and the contact centre."


def test_the_scan_raises_only_when_its_own_repair_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(text: str, replacements: list[Replacement]) -> tuple[str, list[Replacement]]:
        return text, replacements

    monkeypatch.setattr(verify, "apply_replacements", broken)
    with pytest.raises(AnonymizationLeakError) as caught:
        scan_only("Mail jane@example.com")
    leaks = caught.value.details["leaks"]
    assert isinstance(leaks, dict)
    assert "contact" in leaks


def test_a_leak_error_and_the_report_carry_counts_never_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(verify, "apply_replacements", lambda text, reps: (text, reps))
    with pytest.raises(AnonymizationLeakError) as caught:
        scan_only("Mail secret.person@example.com")
    assert "secret" not in repr(caught.value.details)
    assert "secret" not in caught.value.message


def test_a_report_holds_counts_only() -> None:
    report = scan_only("Mail secret.person@example.com").report
    assert "secret" not in repr(report)


def test_the_scan_shares_no_code_with_the_passes() -> None:
    """Independence: verify.py imports only the stdlib and tokens, never a pass."""
    tree = ast.parse(Path(verify.__file__).read_text(encoding="utf-8"))
    imported = {
        n.module
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("app.")
    }
    assert imported <= {"app.anonymizer.tokens", "app.core.errors"}


def _adversarial_input_finishes_quickly() -> None:
    from app.anonymizer.pipeline import anonymize

    n = 150_000
    for s in [
        "a" * n,
        "1-" * (n // 2) + "x",
        "a." * (n // 2),
        "@" * n,
        "age " * (n // 4),
        "www." * (n // 4),
        "http://" * (n // 7),
        "1 " * (n // 2),
        "a@" * (n // 2),
    ]:
        anonymize(s)


def test_adversarial_input_finishes_quickly() -> None:
    """A regex runs in C and cannot be interrupted, so the proof is a subprocess with a timeout."""
    run_with_timeout(_adversarial_input_finishes_quickly, 60)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Member of the Hindu society", "Member of the [RELIGION] society"),
        ("He is a CHRISTIAN volunteer", "[PRONOUN] is a [RELIGION] volunteer"),
        ("Hindus and Muslims met", "[RELIGION] and [RELIGION] met"),
        ("Mrs. Rao led the team", "[TITLE] Rao led the team"),
        ("Contact: Mr Smith, Sales", "Contact: [TITLE] Smith, Sales"),
        ("Madam\nchair", "[TITLE]\nchair"),
        ("I led her team and himself", "I led [PRONOUN] team and [PRONOUN]"),
        ("she said HIS plan", "[PRONOUN] said [PRONOUN] plan"),
    ],
)
def test_the_scan_repairs_a_leftover_religion_term_title_or_pronoun(
    raw: str, expected: str
) -> None:
    result = scan_only(raw)
    assert result.text.value == expected
    assert result.report.repaired >= 1


@pytest.mark.parametrize(
    "raw",
    [
        "Cleaned the shell and heritage site, then the other theatre",
        "Miss a deadline? Mister Jones, Misses and Mrsx are words",
        "Christian Smith led the platform team",
        "Led the [RELIGION] society; [TITLE] Rao and [PRONOUN] team, [GENDER] [NAME]",
        "Fluent in Hindi, Urdu and Arabic; Temple University",
    ],
)
def test_clean_text_and_lookalike_words_are_not_reported(raw: str) -> None:
    result = scan_only(raw)
    assert result.text.value == raw
    assert result.report.repaired == 0


def test_the_scan_sees_a_name_inside_square_brackets() -> None:
    out, repaired = check("x", "Spoke to [Jane] and [JANE] and [NAME]", JANE)
    assert out == "Spoke to [[NAME]] and [[NAME]] and [NAME]"
    assert repaired == 2


def test_a_bracketed_lowercase_pronoun_or_religion_term_is_seen() -> None:
    assert scan_only("[her] [hindu]").text.value == "[[PRONOUN]] [[RELIGION]]"


def test_the_seed_resumes_still_scan_clean_through_the_full_pipeline() -> None:
    from app.anonymizer.pipeline import anonymize

    seeds = sorted(Path(__file__).parents[3].joinpath("seed", "resumes").glob("*.txt"))
    assert seeds
    for path in seeds:
        assert anonymize(path.read_text(encoding="utf-8")).report.repaired == 0, path.name
