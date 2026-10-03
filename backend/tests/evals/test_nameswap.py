"""Name-swap evaluation over hand-built results."""

import pytest

from app.evals.nameswap import evaluate_name_swap
from app.evals.run import CriterionScore, ResumeResult
from app.seed.data import SeedPair


def make(resume_id: str, values: dict[str, int | None], text: str = "same") -> ResumeResult:
    scores = tuple(
        CriterionScore(n, "failed" if v is None else "scored", v, None, None)
        for n, v in values.items()
    )
    return ResumeResult(resume_id, "rola", text, scores)


PAIR = SeedPair("a-base", "a-swap", "origin-a", ("name",))


def test_identical_scores_and_text_pass() -> None:
    out = evaluate_name_swap([make("a-base", {"X": 2}), make("a-swap", {"X": 2})], [PAIR])
    assert out.passed
    assert out.identical_count == 1
    assert out.pairs[0].identical_text


def test_one_point_difference_passes() -> None:
    out = evaluate_name_swap([make("a-base", {"X": 2}), make("a-swap", {"X": 3})], [PAIR])
    assert out.passed


def test_two_point_difference_fails_with_details_and_diff() -> None:
    results = [
        make("a-base", {"X": 1, "Y": 2}, text="Hello\nCity One\n"),
        make("a-swap", {"X": 3, "Y": 2}, text="Hello\nCity Two\n"),
    ]
    out = evaluate_name_swap(results, [PAIR])
    assert not out.passed
    p = out.pairs[0]
    assert not p.passed
    assert not p.identical_text
    assert [(d.criterion, d.base, d.swap) for d in p.differences] == [("X", 1, 3)]
    assert "-City One" in p.text_diff
    assert "+City Two" in p.text_diff
    assert out.identical_count == 0


def test_failed_vs_scored_is_a_difference_but_both_failed_is_not() -> None:
    one = evaluate_name_swap([make("a-base", {"X": None}), make("a-swap", {"X": 2})], [PAIR])
    assert not one.passed
    both = evaluate_name_swap([make("a-base", {"X": None}), make("a-swap", {"X": None})], [PAIR])
    assert both.passed


def test_diff_is_bounded() -> None:
    big = "\n".join(f"line {i}" for i in range(500))
    results = [
        make("a-base", {"X": 0}, text=big),
        make("a-swap", {"X": 4}, text=big.replace("line", "LINE")),
    ]
    out = evaluate_name_swap(results, [PAIR])
    assert len(out.pairs[0].text_diff.splitlines()) <= 61


def test_every_pair_must_pass() -> None:
    other = SeedPair("b-base", "b-swap", "origin-b", ("email",))
    results = [
        make("a-base", {"X": 2}),
        make("a-swap", {"X": 2}),
        make("b-base", {"X": 0}),
        make("b-swap", {"X": 4}),
    ]
    out = evaluate_name_swap(results, [PAIR, other])
    assert not out.passed
    assert [p.passed for p in out.pairs] == [True, False]


def test_missing_result_raises() -> None:
    with pytest.raises(ValueError, match="a-swap"):
        evaluate_name_swap([make("a-base", {"X": 2})], [PAIR])
