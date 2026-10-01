"""The USD 8 limit and the arithmetic around it. Pure: no database, no network.

Limits live in code, not configuration (HLD section 12): changing one needs an ADR and a
migration of `chk_budget_spent_cap`. Amounts are `Decimal` rounded up to six places, so a
cost is never under-counted.
"""

import math
from decimal import ROUND_UP, Decimal
from typing import Final, Literal

BUDGET_LIMIT_USD: Final = Decimal(8)
MAX_TOKENS_CAP: Final = 1500
# The longest input `model_actions_allowed` plans for: about one long resume.
WORST_CASE_INPUT_CHARS: Final = 30_000

_MICRO = Decimal("0.000001")
_PER_MILLION = Decimal(1_000_000)

ModelMode = Literal["replay", "live"]


def _cost(input_tokens: int, output_tokens: int, price_in: Decimal, price_out: Decimal) -> Decimal:
    raw = (Decimal(input_tokens) * price_in + Decimal(output_tokens) * price_out) / _PER_MILLION
    return raw.quantize(_MICRO, rounding=ROUND_UP)


def reserve_amount(max_tokens: int, chars: int, price_in: Decimal, price_out: Decimal) -> Decimal:
    """Most a call can cost: `max_tokens` of output plus an input estimate of chars / 3 tokens.

    `chars` counts the system prompt and the input together. Dividing by 3 over-counts
    tokens (assumption, docs/design/gateway-lld.md section 10), which is the safe side.
    """
    return _cost(math.ceil(chars / 3), max_tokens, price_in, price_out)


def actual_cost(
    input_tokens: int, output_tokens: int, price_in: Decimal, price_out: Decimal
) -> Decimal:
    """What a finished call cost, from the token counts the provider reported."""
    return _cost(input_tokens, output_tokens, price_in, price_out)


def model_actions_allowed(
    mode: ModelMode, spent: Decimal | None, price_in: Decimal, price_out: Decimal
) -> bool:
    """May the Api start a model action now?

    Always in replay mode (replay never draws on the budget, so a recorded spend must not
    block the demo). In live mode only while one worst-case reservation still fits under
    the limit. A missing budget row counts as nothing spent.
    """
    if mode == "replay":
        return True
    worst = reserve_amount(MAX_TOKENS_CAP, WORST_CASE_INPUT_CHARS, price_in, price_out)
    return (spent or Decimal(0)) + worst <= BUDGET_LIMIT_USD
