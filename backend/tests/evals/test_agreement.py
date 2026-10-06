"""Agreement evaluation over hand-built results."""

from collections.abc import Sequence

import pytest

from app.evals.agreement import evaluate_agreement
from app.evals.run import CriterionScore, ResumeResult


def make(resume_id: str, values: dict[str, int | None], status: str = "scored") -> ResumeResult:
    scores = tuple(
        CriterionScore(
            n, "failed" if v is None else status, v, None if v is None else f"q-{n}", None
        )
        for n, v in values.items()
    )
    return ResumeResult(resume_id, "rola", "text", scores)


def run_of(
    pairs: Sequence[tuple[int, int | None]],
) -> tuple[list[ResumeResult], dict[str, dict[str, int]]]:
    """One resume per (label, score) pair with one criterion named C."""
    results = [make(f"r{i:02d}", {"C": s}) for i, (_, s) in enumerate(pairs)]
    labels = {f"r{i:02d}": {"C": lab} for i, (lab, _) in enumerate(pairs)}
    return results, labels


def test_perfect_run_passes() -> None:
    results, labels = run_of([(i % 5, i % 5) for i in range(10)])
    out = evaluate_agreement(results, labels)
    assert out.passed
    assert out.exact == 1.0
    assert out.within_one == 1.0
    assert out.kappa == 1.0
    assert out.off_rows == ()
    assert out.failed == 0
    assert out.no_evidence == 0


def test_exactly_at_threshold_passes() -> None:
    # 8 of 10 within one (80 percent): two rows are 3 points off.
    results, labels = run_of([(2, 2)] * 8 + [(4, 1)] * 2)
    out = evaluate_agreement(results, labels)
    assert out.within_one == 0.8
    assert out.passed


def test_just_under_threshold_fails() -> None:
    results, labels = run_of([(2, 2)] * 79 + [(4, 1)] * 21)
    out = evaluate_agreement(results, labels)
    assert out.within_one == 0.79
    assert not out.passed


def test_custom_threshold() -> None:
    results, labels = run_of([(2, 2)] * 9 + [(4, 1)])
    assert not evaluate_agreement(results, labels, threshold=0.95).passed


def test_failed_score_is_a_miss_and_counted() -> None:
    results, labels = run_of([(2, 2)] * 4 + [(3, None)])
    out = evaluate_agreement(results, labels)
    assert out.within_one == 0.8
    assert out.failed == 1
    assert out.missing == 1
    assert out.off_rows == ()


def test_no_evidence_rows_counted() -> None:
    results = [make("r00", {"C": 0}, status="no_evidence"), make("r01", {"C": 2})]
    out = evaluate_agreement(results, {"r00": {"C": 0}, "r01": {"C": 2}})
    assert out.no_evidence == 1


def test_off_rows_list_more_than_one_point_with_quote() -> None:
    results, labels = run_of([(2, 3), (4, 1)])
    out = evaluate_agreement(results, labels)
    assert len(out.off_rows) == 1
    row = out.off_rows[0]
    assert (row.resume_id, row.criterion, row.label, row.score, row.quote) == (
        "r01",
        "C",
        4,
        1,
        "q-C",
    )


def test_per_criterion_breakdown() -> None:
    results = [make("a", {"X": 1, "Y": 0}), make("b", {"X": 3, "Y": 4})]
    labels = {"a": {"X": 1, "Y": 3}, "b": {"X": 3, "Y": 4}}
    out = evaluate_agreement(results, labels)
    by_name = {c.name: c for c in out.per_criterion}
    assert by_name["X"].exact == 1.0
    assert by_name["X"].within_one == 1.0
    assert by_name["Y"].exact == 0.5
    assert by_name["Y"].within_one == 0.5


def test_label_without_result_raises() -> None:
    results, labels = run_of([(1, 1)])
    labels["ghost"] = {"C": 1}
    with pytest.raises(ValueError, match="ghost"):
        evaluate_agreement(results, labels)


def test_result_without_label_raises() -> None:
    results, labels = run_of([(1, 1), (2, 2)])
    del labels["r01"]
    with pytest.raises(ValueError, match="r01"):
        evaluate_agreement(results, labels)


def test_criterion_without_label_raises() -> None:
    results = [make("a", {"X": 1, "Y": 1})]
    with pytest.raises(ValueError, match="a"):
        evaluate_agreement(results, {"a": {"X": 1}})
