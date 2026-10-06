"""Agreement metrics between labels and scores, pure stdlib.

Inputs are two equal-length sequences on the 0..4 scale; a score may be None, which is a
`failed` row (no value). A None score is a miss in `exact_agreement` and `within_one_agreement`
(the denominator stays the full count), and is excluded from kappa, which needs two values;
`Metrics.missing` reports how many rows were excluded so none is dropped silently.
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Metrics:
    """A metric value, the rows it was computed on and the rows with no score left out."""

    value: float
    used: int
    missing: int


def _check(labels: Sequence[int], scores: Sequence[int | None], levels: int) -> None:
    if not labels and not scores:
        raise ValueError("empty input")
    if len(labels) != len(scores):
        raise ValueError("labels and scores must have the same length")
    for v in (*labels, *(s for s in scores if s is not None)):
        if not 0 <= v < levels:
            raise ValueError(f"value {v} is outside 0..{levels - 1}")


def _share_within(
    labels: Sequence[int], scores: Sequence[int | None], gap: int, levels: int
) -> float:
    _check(labels, scores, levels)
    hits = sum(
        1 for lab, s in zip(labels, scores, strict=True) if s is not None and abs(lab - s) <= gap
    )
    return hits / len(labels)


def exact_agreement(labels: Sequence[int], scores: Sequence[int | None]) -> float:
    """Share of rows where the score equals the label; a None score is a miss."""
    return _share_within(labels, scores, 0, 5)


def within_one_agreement(labels: Sequence[int], scores: Sequence[int | None]) -> float:
    """Share of rows where the score is within one level of the label; a None score is a miss."""
    return _share_within(labels, scores, 1, 5)


def quadratic_weighted_kappa(
    labels: Sequence[int], scores: Sequence[int | None], levels: int = 5
) -> Metrics:
    """Quadratic weighted kappa on the rows that have a score; `missing` counts the rest.

    kappa = 1 - sum(w * observed) / sum(w * expected) with w = (i - j)^2. Raises ValueError
    when no row has a score. When the expected disagreement is zero, both sides sit on one
    shared level, so every pair is identical and the value is 1.0.
    """
    _check(labels, scores, levels)
    pairs = [(lab, s) for lab, s in zip(labels, scores, strict=True) if s is not None]
    if not pairs:
        raise ValueError("no scored rows to compare")
    n = len(pairs)
    observed = sum((lab - s) ** 2 for lab, s in pairs) / n
    label_counts = [0] * levels
    score_counts = [0] * levels
    for lab, s in pairs:
        label_counts[lab] += 1
        score_counts[s] += 1
    expected = sum(
        label_counts[i] * score_counts[j] * (i - j) ** 2
        for i in range(levels)
        for j in range(levels)
    ) / (n * n)
    value = 1.0 if expected == 0 else 1 - observed / expected
    return Metrics(value, n, len(labels) - n)
