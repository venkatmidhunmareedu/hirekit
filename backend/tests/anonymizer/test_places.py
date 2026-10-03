"""The places pass: postal codes, addresses and gazetteer places go; skills and employers stay."""

import pytest

from app.anonymizer import anonymize
from app.anonymizer.pipeline import PASSES
from app.anonymizer.places import AMBIGUOUS, GAZETTEER, KEEP, mask_places
from tests.timeout_helper import run_with_timeout


def out(raw: str) -> str:
    result = anonymize(raw)
    assert result.report.repaired == 0, "the pass left something for the residual scan"
    return result.text.value


def test_the_pass_is_registered() -> None:
    assert mask_places in PASSES


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Zip: 94105", "Zip: [LOCATION]"),
        ("ZIP: 94105-1234 and 10001", "ZIP: [LOCATION] and 10001"),
        ("Austin, TX 78701", "[LOCATION], [LOCATION]"),
        ("Postal code: 94105-1234", "Postal code: [LOCATION]"),
        ("Postcode SW1A 1AA", "Postcode [LOCATION]"),
        ("Leeds LS1 4AP", "[LOCATION] [LOCATION]"),
        ("Toronto M5V 3L9", "[LOCATION] [LOCATION]"),
        ("Chennai - 600001", "[LOCATION] - [LOCATION]"),
        ("Pin: 560 001", "Pin: [LOCATION]"),
        (
            "Sold 120000 units, 94105 users, order 12345",
            "Sold 120000 units, 94105 users, order 12345",
        ),
    ],
)
def test_postal_codes_in_each_supported_format_are_masked(raw: str, expected: str) -> None:
    assert out(raw) == expected


def test_street_address_city_state_and_country_are_masked() -> None:
    raw = "12 Baker Street, London, England\n350 Fifth Ave, New York, NY 10118, USA\nP.O. Box 42"
    assert (
        out(raw) == "[ADDRESS], [LOCATION], [LOCATION]\n"
        "[ADDRESS], [LOCATION], [LOCATION], [LOCATION]\n[ADDRESS]"
    )


def test_a_school_name_that_reveals_a_place_is_partly_masked() -> None:
    raw = (
        "University of Madras\nBangalore Institute of Technology\nUniversity of Michigan, Ann Arbor"
    )
    assert out(raw) == (
        "University of [LOCATION]\n[LOCATION] Institute of Technology\n"
        "University of [LOCATION], [LOCATION]"
    )


@pytest.mark.parametrize(
    "word",
    ["Mobile", "Reading", "Phoenix", "Jakarta", "Nice", "Split", "Bath", "Jersey", "Victoria"],
)
def test_an_ambiguous_place_word_is_masked_only_in_a_place_context(word: str) -> None:
    kept = [
        f"{word} developer and {word.lower()} apps",
        f"Skills: Python, {word}, SQL",
        f"Built the {word} module for the {word} Framework",
        f"Experience in {word} development",
    ]
    for raw in kept:
        assert out(raw) == raw
    assert out(f"Based in {word}.") == "Based in [LOCATION]."
    assert out(f"Lives in {word} and works remotely") == "Lives in [LOCATION] and works remotely"
    assert out(f"Location: {word}") == "Location: [LOCATION]"
    assert out(f"Address\n{word}") == "Address\n[LOCATION]"
    assert out(f"Paris, {word}") == "[LOCATION], [LOCATION]"
    assert out(f"Name\n{word} | a@b.com") == "Name\n[LOCATION] | [EMAIL]"


def test_employers_that_contain_a_place_word_are_kept() -> None:
    raw = (
        "Analyst at Bank of America, then Texas Instruments and American Express.\n"
        "Lives in Bank of America Tower"
    )
    assert out(raw) == raw


def test_the_ambiguity_list_stays_in_step_with_the_gazetteer() -> None:
    assert AMBIGUOUS <= GAZETTEER
    assert all(any(w in GAZETTEER for w in phrase.split()) for phrase in KEEP)
    assert {
        "mobile",
        "reading",
        "phoenix",
        "jakarta",
        "nice",
        "split",
        "bath",
        "jersey",
    } <= AMBIGUOUS


def _places_adversarial_input_finishes_quickly() -> None:
    from app.anonymizer.places import mask_places
    from app.anonymizer.tokens import NameSet

    n = 150_000
    for s in [
        "1 " * (n // 2),
        "1 Ab " * (n // 5),
        "Main St " * (n // 8),
        "new " * (n // 4),
        "a, " * (n // 3),
        "Mobile, " * (n // 8),
        "in Reading " * (n // 11),
        "12345 " * (n // 6),
        "A1 " * (n // 3),
        "Location:\n" * (n // 10),
        "a" * n,
        "Chennai - 1" * (n // 11),
        "San " * (n // 4),
    ]:
        mask_places(s, NameSet())


def test_places_adversarial_input_finishes_quickly() -> None:
    """A regex runs in C and cannot be interrupted, so the proof is a subprocess with a timeout."""
    run_with_timeout(_places_adversarial_input_finishes_quickly, 60)


@pytest.mark.parametrize("city", ["Tehran", "Dakar"])
def test_large_cities_missing_from_the_first_seed_list_are_masked(city: str) -> None:
    assert (
        out(f"Reza Hosseini\nHead of Support\n{city}, Iran")
        == "[NAME]\nHead of Support\n[LOCATION], [LOCATION]"
    )
    assert out(f"Built a team in {city}.") == "Built a team in [LOCATION]."
