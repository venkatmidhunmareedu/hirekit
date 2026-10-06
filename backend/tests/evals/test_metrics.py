"""Agreement metrics over (label, score) pairs on the 0..4 scale; None is a failed row."""

import pytest

from app.evals.metrics import (
    Metrics,
    exact_agreement,
    quadratic_weighted_kappa,
    within_one_agreement,
)


def test_perfect_agreement() -> None:
    labels = [0, 1, 2, 3, 4]
    assert exact_agreement(labels, labels) == 1.0
    assert within_one_agreement(labels, labels) == 1.0
    assert quadratic_weighted_kappa(labels, labels) == Metrics(1.0, 5, 0)


def test_all_off_by_one() -> None:
    labels, scores = [0, 1, 2, 3], [1, 2, 3, 4]
    assert exact_agreement(labels, scores) == 0.0
    assert within_one_agreement(labels, scores) == 1.0
    # observed 4/4 = 1; expected 56/16/16 * ... = 3.5; kappa = 1 - 1/3.5 = 5/7
    assert quadratic_weighted_kappa(labels, scores).value == pytest.approx(5 / 7)


def test_total_disagreement_gives_kappa_minus_one() -> None:
    labels, scores = [0, 4, 0, 4], [4, 0, 4, 0]
    assert exact_agreement(labels, scores) == 0.0
    assert within_one_agreement(labels, scores) == 0.0
    assert quadratic_weighted_kappa(labels, scores).value == pytest.approx(-1.0)


def test_worked_example() -> None:
    # labels [0,1,2,3,4,2], scores [0,2,2,3,3,2], N = 6, 5 levels, weight (i-j)^2 / 16.
    # Observed: two pairs differ by 1, so the sum of squared gaps is 2 and 2 / 6 per resume.
    # Label counts {0:1, 1:1, 2:2, 3:1, 4:1}, score counts {0:1, 2:3, 3:2}.
    # Expected: sum of count_l[i] * count_s[j] * (i-j)^2 = 34 (score 0) + 30 (score 2)
    # + 32 (score 3) = 96, divided by N^2 = 36 gives 96 / 36.
    # kappa = 1 - (2 / 6) / (96 / 36) = 1 - 12 / 96 = 0.875
    labels, scores = [0, 1, 2, 3, 4, 2], [0, 2, 2, 3, 3, 2]
    assert exact_agreement(labels, scores) == pytest.approx(4 / 6)
    assert within_one_agreement(labels, scores) == 1.0
    kappa = quadratic_weighted_kappa(labels, scores)
    assert kappa.value == pytest.approx(0.875)
    assert (kappa.used, kappa.missing) == (6, 0)


def test_a_none_score_is_a_miss_in_agreement_and_excluded_from_kappa() -> None:
    labels, scores = [0, 2, 4, 1], [0, 2, None, 1]
    assert exact_agreement(labels, scores) == 0.75
    assert within_one_agreement(labels, scores) == 0.75
    assert quadratic_weighted_kappa(labels, scores) == Metrics(1.0, 3, 1)


def test_identical_single_level_is_kappa_one() -> None:
    # Expected disagreement is zero here; that only happens when every pair is identical.
    assert quadratic_weighted_kappa([2, 2, 2], [2, 2, 2]) == Metrics(1.0, 3, 0)


def test_empty_input_is_refused() -> None:
    for call in (exact_agreement, within_one_agreement, quadratic_weighted_kappa):
        with pytest.raises(ValueError, match="empty"):
            call([], [])


def test_kappa_with_every_score_missing_is_refused() -> None:
    with pytest.raises(ValueError, match="no scored rows"):
        quadratic_weighted_kappa([1, 2], [None, None])


def test_unequal_lengths_and_out_of_range_values_are_refused() -> None:
    with pytest.raises(ValueError, match="same length"):
        exact_agreement([1], [1, 2])
    with pytest.raises(ValueError, match="outside"):
        quadratic_weighted_kappa([5], [1])
