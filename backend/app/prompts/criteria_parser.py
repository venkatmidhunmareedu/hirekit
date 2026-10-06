"""The criteria reply parser (ADR-0010): strict JSON, validated once for the whole proposal.

Everything the database CHECKs would refuse is refused here (kind, weight above zero, five
non-blank levels numbered 0 to 4, a non-blank name), so the Worker never reads a reply field.
The count, weight scale and length caps are proposed numbers that need engineer confirmation
(prompts/criteria/CHANGELOG.md). Every failure raises `SchemaError` with a constant message,
never reply text (tenet 7).
"""

from decimal import Decimal
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError

from app.core.criteria_limits import (
    KINDS as KINDS,
)
from app.core.criteria_limits import (
    LEVELS as LEVELS,
)
from app.core.criteria_limits import (
    MAX_CRITERIA as MAX_CRITERIA,
)
from app.core.criteria_limits import (
    MAX_DESCRIPTOR_CHARS as MAX_DESCRIPTOR_CHARS,
)
from app.core.criteria_limits import (
    MAX_NAME_CHARS as MAX_NAME_CHARS,
)
from app.core.criteria_limits import (
    MAX_WEIGHT as MAX_WEIGHT,
)
from app.core.criteria_limits import (
    MIN_CRITERIA as MIN_CRITERIA,
)
from app.core.criteria_limits import (
    MIN_WEIGHT as MIN_WEIGHT,
)
from app.worker.errors import SchemaError
from app.worker.ports import ProposedCriterion

_MESSAGE: Final = "The criteria reply did not match the schema."


class _Level(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    level: StrictInt
    descriptor: StrictStr


class _Criterion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: StrictStr
    kind: StrictStr
    weight: StrictInt = Field(ge=MIN_WEIGHT, le=MAX_WEIGHT)
    levels: list[_Level]


class _Reply(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    criteria: list[_Criterion] = Field(min_length=MIN_CRITERIA, max_length=MAX_CRITERIA)


def parse_criteria(reply: str) -> list[ProposedCriterion]:
    try:
        items = _Reply.model_validate_json(reply).criteria
    except ValidationError:
        raise SchemaError(_MESSAGE) from None  # the chained error would quote the reply
    proposed = [_proposed(item) for item in items]
    if len({" ".join(p.name.split()).casefold() for p in proposed}) != len(proposed):
        raise SchemaError(_MESSAGE)
    return proposed


def _line(text: str, limit: int) -> str:
    """One non-blank line within `limit`; a newline could forge a criterion in a prompt."""
    text = text.strip()
    if not text or len(text) > limit or len(text.splitlines()) != 1:
        raise SchemaError(_MESSAGE)
    return text


def _proposed(item: _Criterion) -> ProposedCriterion:
    if item.kind not in KINDS or tuple(lv.level for lv in item.levels) != LEVELS:
        raise SchemaError(_MESSAGE)
    a, b, c, d, e = (_line(lv.descriptor, MAX_DESCRIPTOR_CHARS) for lv in item.levels)
    return ProposedCriterion(
        _line(item.name, MAX_NAME_CHARS), item.kind, Decimal(item.weight), (a, b, c, d, e)
    )
