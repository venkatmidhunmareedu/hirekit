"""The three text classes that may reach the model (tenet 2).

Each is a real class, checked with `isinstance` inside `Gateway.complete`. The
constructor refuses to run without the module-private sentinel, so
`AnonymizedText("raw")` fails at runtime; only the `mint_*` functions supply it,
and each is imported by exactly one producer (enforced by `test_boundaries.py`).
The text is never printed: `repr` and `str` show a length, not the content.
"""

from typing import final


class _Mint:
    """Type of the sentinel; a caller cannot build one by accident."""


_MINT = _Mint()


class _Text:
    """A frozen wrapper around one string, built only through a `mint_*` function."""

    __slots__ = ("value",)
    value: str

    def __init__(self, value: str, _mint: object) -> None:
        if _mint is not _MINT:
            msg = f"{type(self).__name__} can only be built by its producer through mint_*"
            raise TypeError(msg)
        object.__setattr__(self, "value", value)

    def __setattr__(self, name: str, value: object) -> None:
        msg = f"{type(self).__name__} is immutable"
        raise AttributeError(msg)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {len(self.value)} chars>"

    __str__ = __repr__


@final
class AnonymizedText(_Text):
    """A resume after the anonymizer removed identity signals."""

    __slots__ = ()


@final
class JobDescriptionText(_Text):
    """A job description, and for a kit the approved criteria; never candidate data."""

    __slots__ = ()


@final
class PromptText(_Text):
    """A fixed prompt template with role criteria filled in; never resume text."""

    __slots__ = ()


def mint_anonymized(text: str) -> AnonymizedText:
    """Wrap the anonymizer's output. Imported only by `app.anonymizer`."""
    return AnonymizedText(text, _MINT)


def mint_job_description(text: str) -> JobDescriptionText:
    """Wrap a job description. Imported only by `app.jobs.job_description`."""
    return JobDescriptionText(text, _MINT)


def mint_prompt(text: str) -> PromptText:
    """Wrap a built prompt. Imported only by `app.prompts`."""
    return PromptText(text, _MINT)
