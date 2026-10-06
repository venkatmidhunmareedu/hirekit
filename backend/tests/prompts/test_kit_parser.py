import json

import pytest

from app.prompts.kit_parser import MAX_ANSWER_CHARS, MAX_QUESTION_CHARS, parse_kit
from app.prompts.kit_prompt import KitPromptBuilder
from app.worker.errors import SchemaError
from app.worker.ports import ProposedQuestion


def q(
    question: object = "Tell me?", strong: object = "good", weak: object = "bad"
) -> dict[str, object]:
    return {"question": question, "strong_answer": strong, "weak_answer": weak}


def body(*items: dict[str, object]) -> str:
    return json.dumps({"questions": list(items)})


def test_a_valid_reply_becomes_proposed_questions_in_order() -> None:
    out = parse_kit(body(q("First?"), q(" Second? ", "s", "w")))
    assert out == [ProposedQuestion("First?", "good", "bad"), ProposedQuestion("Second?", "s", "w")]


def test_the_builder_parses_through_the_port() -> None:
    assert len(KitPromptBuilder().parse(body(q(), q(), q()))) == 3


BAD_CASES: list[tuple[str, str]] = [
    ("no questions", body()),
    ("one question", body(q())),
    ("four questions", body(q(), q(), q(), q())),
    ("blank question", body(q(" "), q())),
    ("blank strong answer", body(q(strong=""), q())),
    ("blank weak answer", body(q(weak="\n"), q())),
    ("long question", body(q("x" * (MAX_QUESTION_CHARS + 1)), q())),
    ("long strong answer", body(q(strong="x" * (MAX_ANSWER_CHARS + 1)), q())),
    ("long weak answer", body(q(weak="x" * (MAX_ANSWER_CHARS + 1)), q())),
    ("non-string question", body(q(5), q())),
    ("null answer", body(q(strong=None), q())),
    ("criterion position key", body({**q(), "criterion": 1}, q())),  # one criterion per call
    ("extra top key", json.dumps({"questions": [q(), q()], "note": "x"})),
    ("missing key", body({"question": "x?", "strong_answer": "y"}, q())),
    ("not an object", json.dumps([q(), q()])),
    ("fence", "```json\n" + body(q(), q()) + "\n```"),
    ("prose before", "Sure: " + body(q(), q())),
    ("prose after", body(q(), q()) + " Enjoy"),
    ("not json", "not json"),
    ("empty reply", ""),
    ("truncated", body(q(), q())[:-4]),
]


@pytest.mark.parametrize("reply", [r for _, r in BAD_CASES], ids=[n for n, _ in BAD_CASES])
def test_any_deviation_raises_schema_error(reply: str) -> None:
    with pytest.raises(SchemaError):
        parse_kit(reply)


def test_the_error_never_carries_reply_text() -> None:
    leak = "LEAK-RUBRIC-TEXT"
    with pytest.raises(SchemaError) as err:
        parse_kit(body(q(leak), q(weak=" ")))
    assert leak not in str(err.value)
    assert err.value.__cause__ is None
    with pytest.raises(SchemaError) as err2:
        parse_kit(body(q(leak * 100), q()))
    assert leak not in str(err2.value)


def test_a_pydantic_failure_is_not_chained_to_the_reply() -> None:
    with pytest.raises(SchemaError) as err:
        parse_kit('{"x": "LEAK-REPLY"}')
    assert err.value.__cause__ is None
    assert err.value.__suppress_context__
