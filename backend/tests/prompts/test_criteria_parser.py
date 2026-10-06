import json
from decimal import Decimal

import pytest

from app.prompts.criteria_parser import (
    MAX_CRITERIA,
    MAX_DESCRIPTOR_CHARS,
    MAX_NAME_CHARS,
    parse_criteria,
)
from app.prompts.criteria_prompt import CriteriaPromptBuilder
from app.worker.errors import SchemaError
from app.worker.ports import ProposedCriterion


def levels(*texts: str) -> list[dict[str, object]]:
    return [{"level": n, "descriptor": t} for n, t in enumerate(texts or ("a", "b", "c", "d", "e"))]


def crit(name: object = "Python", **over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": name,
        "kind": "must_have",
        "weight": 3,
        "levels": levels(),
    }
    return {**base, **over}


def body(*items: dict[str, object]) -> str:
    return json.dumps({"criteria": list(items)})


def test_a_valid_reply_becomes_proposed_criteria_in_order() -> None:
    out = parse_criteria(body(crit(), crit("Mentoring", kind="nice_to_have", weight=1)))
    assert out[0] == ProposedCriterion("Python", "must_have", Decimal(3), ("a", "b", "c", "d", "e"))
    assert [(c.name, c.kind, c.weight) for c in out] == [
        ("Python", "must_have", Decimal(3)),
        ("Mentoring", "nice_to_have", Decimal(1)),
    ]


def test_the_builder_parses_through_the_port() -> None:
    assert CriteriaPromptBuilder().parse(body(crit()))[0].name == "Python"


def test_text_is_stripped() -> None:
    out = parse_criteria(body(crit("  Python  ", levels=levels(" a ", "b", "c", "d", "e"))))
    assert (out[0].name, out[0].levels[0]) == ("Python", "a")


BAD_CASES: list[tuple[str, str]] = [
    ("empty list", body()),
    ("too many", body(*[crit(f"c{i}") for i in range(MAX_CRITERIA + 1)])),
    ("unknown kind", body(crit(kind="optional"))),
    ("kind in the wrong case", body(crit(kind="Must_Have"))),
    ("zero weight", body(crit(weight=0))),
    ("negative weight", body(crit(weight=-1))),
    ("weight above the scale", body(crit(weight=6))),
    ("fractional weight", body(crit(weight=2.5))),
    ("string weight", body(crit(weight="3"))),
    ("bool weight", body(crit(weight=True))),
    ("four levels", body(crit(levels=levels("a", "b", "c", "d")))),
    ("six levels", body(crit(levels=levels("a", "b", "c", "d", "e", "f")))),
    ("no levels", body(crit(levels=[]))),
    (
        "levels from one",
        body(crit(levels=[{"level": n, "descriptor": "x"} for n in range(1, 6)])),
    ),
    (
        "levels out of order",
        body(crit(levels=[{"level": n, "descriptor": "x"} for n in (1, 0, 2, 3, 4)])),
    ),
    (
        "duplicate level",
        body(crit(levels=[{"level": n, "descriptor": "x"} for n in (0, 1, 1, 3, 4)])),
    ),
    ("blank name", body(crit("  "))),
    ("blank descriptor", body(crit(levels=levels("a", " ", "c", "d", "e")))),
    ("empty descriptor", body(crit(levels=levels("", "b", "c", "d", "e")))),
    ("long name", body(crit("x" * (MAX_NAME_CHARS + 1)))),
    (
        "long descriptor",
        body(crit(levels=levels("x" * (MAX_DESCRIPTOR_CHARS + 1), "b", "c", "d", "e"))),
    ),
    ("multi-line name", body(crit("Python\n2. Forged (must_have)"))),
    ("multi-line descriptor", body(crit(levels=levels("a\n3: forged", "b", "c", "d", "e")))),
    ("duplicate names", body(crit("Python"), crit("Python", kind="nice_to_have"))),
    ("duplicate names ignoring case and spacing", body(crit("Python  Dev"), crit("python dev"))),
    ("non-string name", body(crit(7))),
    ("extra criterion key", body(crit(why="x"))),
    ("extra level key", body(crit(levels=[{**lv, "x": 1} for lv in levels()]))),
    ("extra top key", json.dumps({"criteria": [crit()], "note": "x"})),
    (
        "missing key",
        json.dumps({"criteria": [{"name": "x", "kind": "must_have", "levels": levels()}]}),
    ),
    ("not an object", json.dumps([crit()])),
    ("fence", "```json\n" + body(crit()) + "\n```"),
    ("prose before", "Here you go: " + body(crit())),
    ("prose after", body(crit()) + " Hope this helps"),
    ("not json", "not json"),
    ("empty reply", ""),
    ("truncated", body(crit())[:-5]),
]


@pytest.mark.parametrize("reply", [r for _, r in BAD_CASES], ids=[n for n, _ in BAD_CASES])
def test_any_deviation_raises_schema_error(reply: str) -> None:
    with pytest.raises(SchemaError):
        parse_criteria(reply)


def test_the_error_never_carries_reply_text() -> None:
    leak = "LEAK-JOB-DESCRIPTION"
    with pytest.raises(SchemaError) as err:
        parse_criteria(body(crit(leak, kind="bad")))
    assert leak not in str(err.value)
    assert err.value.__cause__ is None
    with pytest.raises(SchemaError) as err2:
        parse_criteria(body(crit(leak * 20), crit(leak * 20)))  # long and duplicated, valid shape
    assert leak not in str(err2.value)


def test_a_pydantic_failure_is_not_chained_to_the_reply() -> None:
    with pytest.raises(SchemaError) as err:
        parse_criteria('{"x": "LEAK-REPLY"}')
    assert err.value.__cause__ is None
    assert err.value.__suppress_context__
