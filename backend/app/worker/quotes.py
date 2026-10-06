"""The quote check: a score keeps a quote only if code finds it in the anonymized text (REQ-020).

Whitespace normalization only: runs of whitespace (newlines and no-break spaces included)
collapse to one space on both sides and the quote is stripped. No case folding, no punctuation
or unicode folding, no partial or fuzzy match. Linear: one pass per side, then `in`.
"""

from app.gateway.text import AnonymizedText


def _collapse(value: str) -> str:
    return " ".join(value.split())


def quote_in_text(quote: str, text: AnonymizedText) -> bool:
    """True when the whitespace-normalized quote is a literal substring of the normalized text."""
    needle = _collapse(quote)
    return bool(needle) and needle in _collapse(text.value)


class WhitespaceQuoteVerifier:
    """The `QuoteVerifier` the scoring step uses."""

    def verify(self, quote: str, text: AnonymizedText) -> bool:
        return quote_in_text(quote, text)
