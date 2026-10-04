"""The residual scan: independent of the passes, it repairs and counts, and raises only if its
own repair fails. It never puts what it found into a message (tenet 7)."""

import ast
import re
from pathlib import Path

import pytest

from app.anonymizer import verify
from app.anonymizer.pipeline import Anonymized, _run
from app.anonymizer.tokens import NAME, NameSet, Replacement
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
    out, repaired = check("x", "Janet doesn't ask", JANE)
    assert (out, repaired) == ("Janet doesn't ask", 0)


def test_a_name_variant_equal_to_a_placeholder_word_leaves_the_placeholder_alone() -> None:
    word = NAME.strip("[]").lower()
    out, repaired = check("x", f"{NAME} and {word.capitalize()}", NameSet("X Y", frozenset({word})))
    assert (out, repaired) == (f"{NAME} and {NAME}", 1)


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


def _letters(i: int) -> str:
    return "".join(chr(97 + (i // 26**k) % 26) for k in range(4))


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
        "Mr " + "\t" * n + "x",
        "Christian " * (n // 10),
        "Mrs." * (n // 4),
        "[her]" * (n // 5),
        " ".join(f"{_letters(i)}@x.io" for i in range(18_000)),
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
        "Miss a deadline? Misses and Mrsx are words",
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


def test_a_repair_cannot_create_a_finding_on_the_second_scan() -> None:
    from app.anonymizer.pipeline import anonymize

    raw = (
        "Anna Young\nanna.young@mail.com\nBackend engineer\n"
        "References: Christian Young, Engineering Manager"
    )
    result = anonymize(raw)
    assert "Christian [NAME]" in result.text.value


@pytest.mark.parametrize(
    "raw",
    [
        "MRS. PRIYA RAO\nBackend engineer",
        "Smt. Rao and Shri Rao, Sri Rao, Kumari Rao",
        "Mme Rao, Mlle Rao, Mister Rao, Lady Rao, Lord Rao, Sir Rao",
        "MISS Rao and MADAM Rao",
    ],
)
def test_titles_are_masked_in_any_case_by_the_pass_and_the_scan(raw: str) -> None:
    from app.anonymizer.pipeline import anonymize

    for text in (anonymize(raw).text.value, scan_only(raw).text.value):
        assert not re.search(
            r"(?i)\b(?:mrs|smt|shri|sri|kumari|mme|mlle|mister|lady|lord|sir)\b", text
        )
        assert not re.search(r"(?i)\b(?:miss|madam)\b", text)
    assert anonymize(raw).report.repaired == 0


@pytest.mark.parametrize(
    "raw",
    [
        "MS in computer science; MR imaging",
        "Lord of the Rings fan; the lady of the house; sir, thank you",
        "Miss a deadline; Misses; Mrsx; Sri Lanka office",
    ],
)
def test_ambiguous_titles_and_lookalikes_are_kept(raw: str) -> None:
    from app.anonymizer.pipeline import anonymize

    assert anonymize(raw).text.value == raw.replace("Sri Lanka", "[LOCATION]")


def test_christian_is_a_name_only_for_the_candidate_or_before_a_surname() -> None:
    from app.anonymizer.pipeline import anonymize

    raw = (
        "Priya Rao\nVolunteer, Christian Aid, 2019-2021\nChristian Medical College Vellore\n"
        "Texas Christian University"
    )
    value = anonymize(raw).text.value
    assert "Christian" not in value
    own = anonymize("Christian Smith\nBackend engineer\nChristian led the team")
    assert own.text.value == "[NAME]\nBackend engineer\n[NAME] led the team"
    assert own.report.repaired == 0


def test_the_scan_exempts_christian_only_as_the_candidates_own_variant() -> None:
    out, _ = check("x", "Christian Aid", NameSet())
    assert out == "[RELIGION] Aid"
    out, _ = check("x", "Christian Smith", NameSet())
    assert out == "Christian Smith"
    out, _ = check("x", "Christian left", NameSet("Christian Lee", frozenset({"christian"})))
    assert out == "[NAME] left"


@pytest.mark.parametrize(
    "raw",
    ["Baha\u2019i youth", "Bah\u00e1\u2019\u00ed youth", "Bah\u00e1'\u00ed youth", "Bahai youth"],
)
def test_bahai_spellings_are_masked_by_the_pass(raw: str) -> None:
    from app.anonymizer.pipeline import anonymize

    result = anonymize(raw)
    assert result.text.value == "[RELIGION] youth"
    assert result.report.repaired == 0


@pytest.mark.parametrize("raw", ["Built a cloud-agnostic platform", "A vendor-agnostic design"])
def test_hyphen_compounds_with_a_belief_word_are_unchanged(raw: str) -> None:
    from app.anonymizer.pipeline import anonymize

    assert anonymize(raw).text.value == raw
