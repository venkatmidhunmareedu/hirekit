"""The pipeline shell: normalization, limits, replacement application and the report."""

import pytest

from app.anonymizer import Anonymized, anonymize
from app.anonymizer.pipeline import (
    ANONYMIZER_VERSION,
    MAX_INPUT_CHARS,
    InputTooLargeError,
    _run,
    normalize,
)
from app.anonymizer.tokens import NameSet, Replacement, apply_replacements
from app.gateway.text import AnonymizedText

ZWSP, SHY, BOM, NBSP = chr(0x200B), chr(0xAD), chr(0xFEFF), chr(0xA0)
LIG_FI, LIG_FFI = chr(0xFB01), chr(0xFB03)

RESUME = """Senior Backend Engineer
Built a payments service in Python and PostgreSQL at Acme Logistics, 2018 - 2021.
Led a team of 6 engineers; cut p95 latency from 900 ms to 120 ms.
Skills: Python, FastAPI, SQL, Docker, AWS
"""


@pytest.mark.parametrize("raw", ["", "  \n\t ", ZWSP + SHY + BOM])
def test_an_empty_input_is_refused(raw: str) -> None:
    """The extractor already fails these, so reaching here is a programming error."""
    with pytest.raises(ValueError, match="empty"):
        anonymize(raw)


def test_an_input_over_500000_characters_is_refused_with_a_permanent_error() -> None:
    at_limit = "word " * (MAX_INPUT_CHARS // 5)
    assert len(at_limit) == MAX_INPUT_CHARS
    assert isinstance(anonymize(at_limit), Anonymized)
    with pytest.raises(InputTooLargeError) as caught:
        anonymize(at_limit + "x")
    assert caught.value.message == "This file is too long to process."


def test_the_result_carries_anonymized_text_and_a_clean_report() -> None:
    result = anonymize(RESUME)
    assert isinstance(result.text, AnonymizedText)
    assert result.text.value == RESUME
    assert result.identity_name is None
    assert result.report.name_found is False
    assert result.report.repaired == 0
    assert result.report.masked == {}
    assert result.report.anonymizer_version == ANONYMIZER_VERSION


def test_skills_employers_and_employment_years_are_kept() -> None:
    """AC-US-00-004-7: the evidence survives the shell and the residual scan."""
    assert anonymize(RESUME).text.value == RESUME


def test_a_ligature_a_soft_hyphen_and_a_no_break_space_are_normalized() -> None:
    assert normalize(LIG_FI + "nance" + SHY + " team" + NBSP + "lead" + ZWSP) == "finance team lead"
    assert normalize(LIG_FFI + "ce") == "ffice"


def test_windows_and_unix_newlines_give_the_same_output() -> None:
    unix = anonymize(RESUME).text.value
    assert anonymize(RESUME.replace("\n", "\r\n")).text.value == unix
    assert anonymize(RESUME.replace("\n", "\r")).text.value == unix


def test_a_placeholder_in_the_input_is_left_alone() -> None:
    raw = "Contact: [EMAIL] [PHONE]\nAge: [AGE]\nGender: [GENDER]\n[NAME] built a service."
    result = anonymize(raw)
    assert result.text.value == raw
    assert result.report.repaired == 0


def test_a_pass_replacement_is_applied_and_counted_by_kind() -> None:
    def shout(text: str, names: NameSet) -> list[Replacement]:
        start = text.index("Acme")
        return [Replacement(start, start + 4, "[LOCATION]", "location")]

    result = _run(RESUME, (shout,))
    assert "at [LOCATION] Logistics" in result.text.value
    assert result.report.masked == {"location": 1}


def test_overlapping_matches_keep_the_longest() -> None:
    text = "0123456789"
    long_one = Replacement(0, 10, "[A]", "contact")
    inside = Replacement(5, 7, "[B]", "name")
    assert apply_replacements(text, [inside, long_one]) == ("[A]", [long_one])


def test_a_straddling_match_is_merged_so_no_part_of_either_survives() -> None:
    """Dropping the shorter one would leave the part of it outside the longer one in the text."""
    short = Replacement(0, 3, "[C]", "name")
    long = Replacement(2, 8, "[D]", "contact")
    out, kept = apply_replacements("0123456789", [short, long])
    assert out == "[D]89"
    assert kept == [Replacement(0, 8, "[D]", "contact")]


def test_non_overlapping_matches_are_all_applied_in_order() -> None:
    text = "ab cd ef"
    reps = [Replacement(6, 8, "[Z]", "name"), Replacement(0, 2, "[X]", "name")]
    assert apply_replacements(text, reps)[0] == "[X] cd [Z]"


def test_many_matches_are_applied_quickly() -> None:
    raw = "a@b.co " * 14_000
    result = anonymize(raw)
    assert result.text.value == "[EMAIL] " * 14_000
    assert result.report.repaired == 14_000
