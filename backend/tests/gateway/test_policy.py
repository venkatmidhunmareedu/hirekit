"""Budget policy: reservation arithmetic and whether a model action may start."""

from decimal import Decimal

import pytest

from app.budget.policy import (
    BUDGET_LIMIT_USD,
    MAX_TOKENS_CAP,
    WORST_CASE_INPUT_CHARS,
    actual_cost,
    model_actions_allowed,
    reserve_amount,
)

PRICE_IN = Decimal(1)
PRICE_OUT = Decimal(5)


def test_limit_and_cap_are_the_constants_the_prd_states() -> None:
    assert Decimal(8) == BUDGET_LIMIT_USD
    assert MAX_TOKENS_CAP == 1500


def test_reserve_is_output_at_the_output_price_plus_a_third_of_the_characters_as_input() -> None:
    # 1500 * 5 / 1e6 = 0.0075, and 2400 chars / 3 = 800 tokens * 1 / 1e6 = 0.0008
    assert reserve_amount(1500, 2400, PRICE_IN, PRICE_OUT) == Decimal("0.008300")


def test_reserve_rounds_up_so_a_cost_is_never_under_counted() -> None:
    # 1 output token at 5 USD per million is 0.000005; one input token adds 0.000001
    assert reserve_amount(1, 1, PRICE_IN, PRICE_OUT) == Decimal("0.000006")
    assert reserve_amount(1, 4, Decimal("0.3"), Decimal(0)) == Decimal("0.000001")


def test_actual_cost_uses_the_reported_token_counts() -> None:
    assert actual_cost(1234, 321, PRICE_IN, PRICE_OUT) == Decimal("0.002839")


def test_a_full_reservation_is_about_one_cent() -> None:
    """HLD section 8: about USD 0.01 for 1500 output tokens plus an input estimate."""
    reserve = reserve_amount(1500, 6000, PRICE_IN, PRICE_OUT)
    assert Decimal("0.008") < reserve < Decimal("0.011")


def test_model_actions_allowed_true_in_replay_even_at_7_99_spent() -> None:
    """AC-US-02-002-4, HLD section 16: recorded spend must not block a free demo."""
    assert model_actions_allowed("replay", Decimal("7.99"), PRICE_IN, PRICE_OUT) is True
    assert model_actions_allowed("replay", Decimal(8), PRICE_IN, PRICE_OUT) is True


def test_model_actions_allowed_false_in_live_when_a_reservation_no_longer_fits() -> None:
    worst = reserve_amount(MAX_TOKENS_CAP, WORST_CASE_INPUT_CHARS, PRICE_IN, PRICE_OUT)
    assert model_actions_allowed("live", BUDGET_LIMIT_USD - worst, PRICE_IN, PRICE_OUT) is True
    just_over = BUDGET_LIMIT_USD - worst + Decimal("0.000001")
    assert model_actions_allowed("live", just_over, PRICE_IN, PRICE_OUT) is False
    assert model_actions_allowed("live", BUDGET_LIMIT_USD, PRICE_IN, PRICE_OUT) is False


def test_missing_budget_row_counts_as_zero_spent() -> None:
    """HLD section 16: an absent row must not refuse a demo, nor crash."""
    assert model_actions_allowed("replay", None, PRICE_IN, PRICE_OUT) is True
    assert model_actions_allowed("live", None, PRICE_IN, PRICE_OUT) is True


@pytest.mark.parametrize("spent", [Decimal(0), Decimal("3.5")])
def test_live_is_allowed_with_plenty_of_room(spent: Decimal) -> None:
    assert model_actions_allowed("live", spent, PRICE_IN, PRICE_OUT) is True
