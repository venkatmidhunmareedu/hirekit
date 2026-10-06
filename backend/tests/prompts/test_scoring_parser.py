import json
from decimal import Decimal
from uuid import uuid4

import pytest

from app.prompts.scoring_parser import ScoreReplyParser
from app.worker.errors import SchemaError
from app.worker.ports import CriterionSpec, ParsedScore, ScoreParser

PARSER: ScoreParser = ScoreReplyParser()
CRITERIA = [CriterionSpec(uuid4(), f"c{i}", "must_have", Decimal(1), i, ()) for i in (1, 2)]


def body(*items: dict[str, object]) -> str:
    return json.dumps({"scores": list(items)})


def item(pos: object, value: object = 2, quote: object = "built it") -> dict[str, object]:
    return {"criterion": pos, "value": value, "quote": quote}


def test_valid_reply_maps_positions_to_ids_in_criteria_order() -> None:
    out = PARSER.parse(body(item(2, 4, "b"), item(1, 1, "a")), CRITERIA)
    assert out == [ParsedScore(CRITERIA[0].id, 1, "a"), ParsedScore(CRITERIA[1].id, 4, "b")]


def test_null_quote_and_the_alias_both_mean_no_evidence() -> None:
    for sentinel in (None, "no evidence found", "  No   Evidence\nFound "):
        out = PARSER.parse(body(item(1, 0, sentinel), item(2, 0, None)), CRITERIA)
        assert out[0].quote is None


def test_null_quote_with_a_non_zero_value_is_accepted_by_the_parser() -> None:
    out = PARSER.parse(body(item(1, 3, None), item(2, 0, None)), CRITERIA)
    assert out[0] == ParsedScore(CRITERIA[0].id, 3, None)


def test_a_quote_that_merely_contains_the_sentinel_is_kept() -> None:
    out = PARSER.parse(body(item(1, 2, "no evidence found here"), item(2)), CRITERIA)
    assert out[0].quote == "no evidence found here"


@pytest.mark.parametrize(
    "reply",
    [
        body(item(1)),  # missing 2
        body(item(1), item(1)),  # duplicate
        body(item(1), item(2), item(3)),  # unknown
        body(item(0), item(1)),  # position 0
        body(item(1), item(True)),  # bool position
        body(item(1, 5), item(2)),  # above range
        body(item(1, -1), item(2)),  # below range
        body(item(1, True), item(2)),  # bool value
        body(item(1, 2.0), item(2)),  # float value
        body(item(1, "2"), item(2)),  # string value
        body(item(1, 2, 7), item(2)),  # non-string quote
        body(item(1, 2, "  "), item(2)),  # blank quote
        body({"criterion": 1, "value": 2}, item(2)),  # quote key missing
        body({**item(1), "why": "x"}, item(2)),  # extra item key
        json.dumps({"scores": [item(1), item(2)], "note": "x"}),  # extra top key
        json.dumps([item(1), item(2)]),  # not an object
        '{"scores": []}',
        "```json\n" + body(item(1), item(2)) + "\n```",  # fence
        "Here you go: " + body(item(1), item(2)),  # prose before
        body(item(1), item(2)) + " Hope this helps",  # prose after
        "not json",
        "",
        body(item(1), item(2))[:-5],  # truncated
    ],
)
def test_any_deviation_raises_schema_error(reply: str) -> None:
    with pytest.raises(SchemaError):
        PARSER.parse(reply, CRITERIA)


def test_the_error_never_carries_reply_text() -> None:
    leak = "LEAK-RESUME-QUOTE"
    with pytest.raises(SchemaError) as err:
        PARSER.parse(body(item(1, 9, leak), item(2)), CRITERIA)
    assert leak not in str(err.value)
    assert err.value.__cause__ is None
    assert err.value.__suppress_context__
