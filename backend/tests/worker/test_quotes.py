"""The quote verifier: whitespace normalization only, never fuzzy (REQ-020)."""

from app.gateway.text import mint_anonymized
from app.worker.ports import QuoteVerifier
from app.worker.quotes import WhitespaceQuoteVerifier
from tests.timeout_helper import run_with_timeout

NBSP = chr(0xA0)
CURLY = chr(0x2019)
TEXT = (
    "Led a team of five engineers.\nBuilt the [NAME] billing service  in Go.\n"
    f"{NBSP}Shipped on time."
)


def _verify(quote: str, text: str = TEXT) -> bool:
    return WhitespaceQuoteVerifier().verify(quote, mint_anonymized(text))


def test_verifier_satisfies_the_port() -> None:
    verifier: QuoteVerifier = WhitespaceQuoteVerifier()
    assert isinstance(verifier.verify("x", mint_anonymized("x")), bool)


def test_exact_substring_is_verified() -> None:
    assert _verify("Led a team of five engineers.") is True


def test_whitespace_runs_in_the_quote_collapse() -> None:
    assert _verify("Led   a \t team\n\nof five") is True


def test_whitespace_runs_in_the_text_collapse() -> None:
    assert _verify("billing service in Go.") is True


def test_quote_spanning_a_line_break_in_the_text_is_verified() -> None:
    assert _verify("five engineers. Built the") is True


def test_no_break_space_collapses_like_a_space() -> None:
    assert _verify("in Go. Shipped on time.") is True


def test_surrounding_whitespace_on_the_quote_is_stripped() -> None:
    assert _verify("  \n Shipped on time.\n ") is True


def test_different_case_is_not_verified() -> None:
    assert _verify("led a team of five engineers.") is False


def test_changed_word_is_not_verified() -> None:
    assert _verify("Led a team of six engineers.") is False


def test_extra_word_is_not_verified() -> None:
    assert _verify("Led a large team of five engineers.") is False


def test_missing_word_is_not_verified() -> None:
    assert _verify("Led a team of engineers.") is False


def test_smart_quote_is_not_verified_against_a_straight_quote() -> None:
    assert _verify(f"it{CURLY}s done", "it's done") is False
    assert _verify("it's done", f"it{CURLY}s done") is False


def test_empty_quote_is_not_verified() -> None:
    assert _verify("") is False


def test_whitespace_only_quote_is_not_verified() -> None:
    assert _verify(f" \n\t{NBSP} ") is False


def test_quote_across_a_placeholder_is_verified_when_literal() -> None:
    assert _verify("the [NAME] billing") is True


def test_quote_that_drops_a_placeholder_is_not_verified() -> None:
    assert _verify("the billing service") is False


def test_quote_longer_than_the_text_is_not_verified() -> None:
    assert _verify(TEXT + " and more") is False


def test_whole_text_is_verified() -> None:
    assert _verify(TEXT) is True


def test_every_substring_of_the_normalized_text_is_verified() -> None:
    normalized = " ".join(TEXT.split())
    for start in range(len(normalized)):
        for end in range(start + 1, len(normalized) + 1, 3):
            cut = normalized[start:end]
            if cut.strip():
                assert _verify(cut) is True, cut


def test_a_substring_with_one_character_changed_is_never_verified() -> None:
    text = "Led a team of five engineers at Acme."
    for start in range(0, len(text) - 6, 2):
        cut = text[start : start + 6]
        if cut != cut.strip():
            continue
        for i in range(len(cut)):
            changed = cut[:i] + ("#" if cut[i] != "#" else "%") + cut[i + 1 :]
            assert _verify(changed, text) is False, changed


def _quotes_adversarial_input_finishes_quickly() -> None:
    from app.gateway.text import mint_anonymized
    from app.worker.quotes import WhitespaceQuoteVerifier

    v = WhitespaceQuoteVerifier()
    for unit in ["a ", "a \n\u00a0 ", "ab", " "]:
        text = mint_anonymized((unit * 500_000)[:500_000])
        for quote in [("a " * 5_000), "a" * 10_000, "ab" * 5_000 + "c", " " * 10_000]:
            assert isinstance(v.verify(quote, text), bool)


def test_quotes_adversarial_input_finishes_quickly() -> None:
    """Linear in the input: a subprocess with a hard timeout proves it."""
    run_with_timeout(_quotes_adversarial_input_finishes_quickly, 30)
