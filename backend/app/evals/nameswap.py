"""Name-swap evaluation: a base resume and its swapped twin must score within one point."""

import difflib
from collections.abc import Sequence
from dataclasses import dataclass

from app.evals.run import ResumeResult
from app.seed.data import SeedPair

MAX_DIFF_LINES = 60


@dataclass(frozen=True, slots=True)
class CriterionDifference:
    criterion: str
    base: int | None
    swap: int | None


@dataclass(frozen=True, slots=True)
class PairOutcome:
    pair_id: str
    base_id: str
    swap_id: str
    passed: bool
    identical_text: bool
    differences: tuple[CriterionDifference, ...]
    text_diff: str  # empty unless the pair failed


@dataclass(frozen=True, slots=True)
class NameSwapResult:
    passed: bool
    pairs: tuple[PairOutcome, ...]
    identical_count: int


def _differs(base: int | None, swap: int | None) -> bool:
    if base is None or swap is None:
        return base is not swap
    return abs(base - swap) > 1


def _text_diff(base: ResumeResult, swap: ResumeResult) -> str:
    lines = list(
        difflib.unified_diff(
            base.anonymized_text.splitlines(),
            swap.anonymized_text.splitlines(),
            fromfile=base.resume_id,
            tofile=swap.resume_id,
            lineterm="",
        )
    )
    if len(lines) > MAX_DIFF_LINES:
        lines = [*lines[:MAX_DIFF_LINES], f"... {len(lines) - MAX_DIFF_LINES} more diff lines"]
    return "\n".join(lines)


def evaluate_name_swap(
    results: Sequence[ResumeResult], pairs: Sequence[SeedPair]
) -> NameSwapResult:
    """Compare each pair per criterion by name; passed when every pair passes."""
    by_id = {r.resume_id: r for r in results}
    outcomes: list[PairOutcome] = []
    for pair in pairs:
        for rid in (pair.base_id, pair.swap_id):
            if rid not in by_id:
                raise ValueError(f"{rid}: no result for pair {pair.origin_pair}")
        base, swap = by_id[pair.base_id], by_id[pair.swap_id]
        b = {s.name: s.value for s in base.scores}
        w = {s.name: s.value for s in swap.scores}
        if set(b) != set(w):
            raise ValueError(f"{pair.origin_pair}: criteria of base and swap differ")
        diffs = tuple(CriterionDifference(n, b[n], w[n]) for n in sorted(b) if _differs(b[n], w[n]))
        outcomes.append(
            PairOutcome(
                pair.origin_pair,
                pair.base_id,
                pair.swap_id,
                not diffs,
                base.anonymized_text == swap.anonymized_text,
                diffs,
                _text_diff(base, swap) if diffs else "",
            )
        )
    return NameSwapResult(
        all(o.passed for o in outcomes),
        tuple(outcomes),
        sum(o.identical_text for o in outcomes),
    )
