"""Properties replay and the evals depend on: the same input gives the same output, once."""

import pytest

from app.anonymizer import anonymize

PIECES = [
    "Jane Doe",
    "jane.doe@example.com",
    "+1 (555) 123-4567",
    "https://example.com/in/jane",
    "@janedoe",
    "Age: 34",
    "DOB: 12/03/1990",
    "Gender: Female",
    "Religion: Hindu",
    "Python",
    "2018 - 2021",
    "Acme Logistics",
    chr(0xFB01) + "nance",
    chr(0xA0),
    "\r\n",
    "\n",
    " ",
    "[EMAIL]",
    "[NAME]",
    "built a service",
    "p95 latency 900 ms",
]
SEEDS = range(40)


def sample(seed: int) -> str:
    """A fixed mix of signals and plain text per seed; no randomness, so a failure repeats."""
    count = seed % 25 + 2
    return " ".join(PIECES[(seed * 7 + i * i) % len(PIECES)] for i in range(count)) + " x"


@pytest.mark.parametrize("seed", SEEDS)
def test_the_same_input_gives_the_same_output(seed: int) -> None:
    raw = sample(seed)
    first, second = anonymize(raw), anonymize(raw)
    assert first.text.value == second.text.value
    assert first.report == second.report


@pytest.mark.parametrize("seed", SEEDS)
def test_anonymizing_twice_changes_nothing(seed: int) -> None:
    once = anonymize(sample(seed)).text.value
    twice = anonymize(once)
    assert twice.text.value == once
    assert twice.report.repaired == 0
