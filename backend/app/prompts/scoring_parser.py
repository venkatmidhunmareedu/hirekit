"""The scoring reply parser (ADR-0010): strict JSON, positions mapped back to criterion ids.

One JSON object and nothing else: no code fence, no prose. Exactly positions 1..N once each.
Every failure raises `SchemaError` with a constant message, never reply text (tenet 7).
"""

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError

from app.worker.errors import SchemaError
from app.worker.ports import CriterionSpec, ParsedScore

_NO_EVIDENCE: Final = "no evidence found"
_MESSAGE: Final = "The scoring reply did not match the schema."


class _Item(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    criterion: StrictInt = Field(ge=1)
    value: StrictInt = Field(ge=0, le=4)
    quote: StrictStr | None


class _Reply(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    scores: list[_Item]


class ScoreReplyParser:
    """Implements `ScoreParser`."""

    def parse(self, reply: str, criteria: list[CriterionSpec]) -> list[ParsedScore]:
        try:
            items = _Reply.model_validate_json(reply).scores
        except ValidationError:
            raise SchemaError(_MESSAGE) from None  # the chained error would quote the reply
        if sorted(i.criterion for i in items) != list(range(1, len(criteria) + 1)):
            raise SchemaError(_MESSAGE)
        by_position = {i.criterion: i for i in items}
        return [
            ParsedScore(c.id, by_position[n].value, _quote(by_position[n].quote))
            for n, c in enumerate(criteria, start=1)
        ]


def _quote(raw: str | None) -> str | None:
    if raw is None or " ".join(raw.split()).casefold() == _NO_EVIDENCE:
        return None
    if not raw.strip():
        raise SchemaError(_MESSAGE)
    return raw
