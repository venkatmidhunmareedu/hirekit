"""The contact pass: emails, phones, links and handles go; years, versions and skills stay."""

import subprocess
import sys
from pathlib import Path

import pytest

from app.anonymizer import anonymize
from app.anonymizer.contact import contact
from app.anonymizer.pipeline import PASSES
from app.anonymizer.tokens import EMAIL, PHONE, URL, NameSet


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Mail jane.doe@example.com now", f"Mail {EMAIL} now"),
        ("jane+jobs@mail.co.uk.", f"{EMAIL}."),
        ("JANE_DOE@Example.COM", EMAIL),
        ("Phone: +1 (555) 123-4567", f"Phone: {PHONE}"),
        ("Call (555) 123-4567 today", f"Call {PHONE} today"),
        ("+91 98765 43210", PHONE),
        ("020 7946 0958", PHONE),
        ("555.123.4567", PHONE),
        ("5551234567", PHONE),
        ("(see https://example.com/in/jane?x=1).", f"(see {URL})."),
        ("HTTP://Example.org/a_b,c", URL),
        ("www.janedoe.dev", URL),
        ("linkedin.com/in/jane-doe", URL),
        ("Code: github.com/janedoe/repo.", f"Code: {URL}."),
        ("janedoe.io/portfolio", URL),
        ("Find me at @janedoe", f"Find me at {URL}"),
        ("Twitter: janedoe", f"Twitter: {URL}"),
        ("GitHub: janedoe | Python", f"GitHub: {URL} | Python"),
    ],
)
def test_emails_phones_urls_and_handles_are_masked_in_every_form(raw: str, expected: str) -> None:
    result = anonymize(raw)
    assert result.text.value == expected
    assert result.report.repaired == 0, "the pass left something for the residual scan"


@pytest.mark.parametrize(
    "raw",
    [
        "Built it in 2018 - 2021 and 2018-2021.",
        "Cut p95 latency from 900 ms to 120 ms, saving 1,200,000 requests.",
        "Skills: Node.js, Vue.js, ASP.NET, Python 3.14.2",
        "GitHub: Open source work on Python tools",
        "Reach me by email",
        "Tags: a@, @, 12 34 56",
    ],
)
def test_years_versions_skills_and_plain_words_are_kept(raw: str) -> None:
    assert anonymize(raw).text.value == raw


def test_the_pass_is_registered_and_returns_contact_replacements() -> None:
    assert contact in PASSES
    found = contact("a@b.com +44 7700 900123", NameSet())
    assert [(r.token, r.kind) for r in found] == [(EMAIL, "contact"), (PHONE, "contact")]


def test_contact_adversarial_input_finishes_quickly() -> None:
    """A regex runs in C and cannot be interrupted, so the proof is a subprocess with a timeout."""
    code = (
        "from app.anonymizer.contact import contact\n"
        "from app.anonymizer.tokens import NameSet\n"
        "n = 150_000\n"
        "for s in ['+' * n, '(1' * (n // 2), '1.' * (n // 2), '1 ' * (n // 2), 'a@b.' * (n // 4),"
        " 'a@' + 'b' * n, 'x.com' * (n // 5), 'github.com/' * (n // 11), '@a' * (n // 2),"
        " 'twitter:' * (n // 8), 'a.' * (n // 2) + '@', 'http://' * (n // 7), 'a-' * (n // 2)]:\n"
        "    contact(s, NameSet())\n"
    )
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-c", code],
        check=True,
        timeout=60,
        cwd=Path(__file__).parents[2],
    )
