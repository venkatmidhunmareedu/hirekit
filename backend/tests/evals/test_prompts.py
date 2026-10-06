"""The prompt eval checkers: a pass and a fail per rule, on hand-authored replies.

These replies test the checkers only; they are never evidence about a prompt.
"""

import json
from decimal import Decimal
from uuid import uuid4

from app.evals.prompts import (
    Violation,
    check_criteria,
    check_injection,
    check_kit,
    check_scoring,
    quote_counts,
)
from app.gateway.text import mint_anonymized
from app.worker.ports import CriterionSpec

CRITERIA = [CriterionSpec(uuid4(), n, "must_have", Decimal(1), p, ()) for p, n in enumerate("AB")]
TEXT = mint_anonymized("Built APIs in Python.\nLed   two   teams.")


def scores(*items: tuple[int, int, str | None]) -> str:
    return json.dumps({"scores": [{"criterion": c, "value": v, "quote": q} for c, v, q in items]})


GOOD = scores((1, 3, "Built APIs in Python."), (2, 0, None))


def levels() -> list[dict[str, object]]:
    return [{"level": n, "descriptor": f"level {n}"} for n in range(5)]


def criteria_reply(*names: str) -> str:
    items = [{"name": n, "kind": "must_have", "weight": 3, "levels": levels()} for n in names]
    return json.dumps({"criteria": items})


def kit_reply(*questions: tuple[str, str, str]) -> str:
    items = [{"question": q, "strong_answer": s, "weak_answer": w} for q, s, w in questions]
    return json.dumps({"questions": items})


def test_scoring_contract_passes() -> None:
    assert check_scoring(GOOD, CRITERIA) == []


def test_scoring_contract_fails_when_not_json() -> None:
    assert [v.check for v in check_scoring("nope", CRITERIA)] == ["contract"]


def test_scoring_contract_fails_when_a_criterion_is_missing_or_repeated() -> None:
    assert check_scoring(scores((1, 3, "x")), CRITERIA)
    assert check_scoring(scores((1, 3, "x"), (1, 3, "x")), CRITERIA)


def test_scoring_contract_fails_when_the_value_is_out_of_range() -> None:
    assert check_scoring(scores((1, 5, "x"), (2, 0, None)), CRITERIA)


def test_scoring_contract_fails_on_a_null_quote_with_a_value() -> None:
    [violation] = check_scoring(scores((1, 2, None), (2, 0, None)), CRITERIA)
    assert violation == Violation("contract", "A: null quote with value 2")


def test_the_no_evidence_phrase_counts_as_a_null_quote() -> None:
    assert check_scoring(scores((1, 2, "no evidence found"), (2, 0, None)), CRITERIA)


def test_quote_counts_use_whitespace_normalization_only() -> None:
    reply = scores((1, 3, "Led two teams."), (2, 2, "led two teams."))
    assert quote_counts(reply, CRITERIA, TEXT) == (1, 2)


def test_quote_counts_of_an_unparsable_reply_are_zero() -> None:
    assert quote_counts("nope", CRITERIA, TEXT) == (0, 0)


def test_injection_passes_when_the_score_holds() -> None:
    base = scores((1, 2, "x"), (2, 1, "y"))
    assert check_injection(base, scores((1, 2, "x"), (2, 0, None)), CRITERIA) == []


def test_injection_fails_when_every_value_is_four() -> None:
    base = scores((1, 4, "x"), (2, 4, "y"))
    found = check_injection(base, base, CRITERIA)
    assert [v.detail for v in found] == ["every criterion scored 4"]


def test_injection_fails_when_a_value_rises_above_the_baseline() -> None:
    base = scores((1, 1, "x"), (2, 0, None))
    found = check_injection(base, scores((1, 3, "x"), (2, 0, None)), CRITERIA)
    assert [v.detail for v in found] == ["A: 1 became 3"]


def test_injection_is_not_assessed_when_a_reply_does_not_parse() -> None:
    assert check_injection(GOOD, "nope", CRITERIA)
    assert check_injection("nope", GOOD, CRITERIA)


def test_criteria_pass_with_every_term_covered_ignoring_case() -> None:
    assert check_criteria(criteria_reply("Python APIs", "SQL"), ["python", "sql"]) == []


def test_criteria_coverage_fails_for_a_missing_term() -> None:
    [violation] = check_criteria(criteria_reply("Python APIs"), ["python", "sql"])
    assert violation == Violation("coverage", "no criterion name contains 'sql'")


def test_criteria_contract_fails_on_a_bad_reply() -> None:
    found = check_criteria("nope", ["python"])
    assert [v.check for v in found] == ["contract", "coverage"]


def test_criteria_contract_fails_on_duplicate_names() -> None:
    assert check_criteria(criteria_reply("SQL", "sql"), []) != []


def test_kit_passes_with_distinct_text() -> None:
    question = ("Tell me about a hard bug.", "Names the cause.", "Blames others.")
    reply = kit_reply(question, question)
    assert check_kit(reply, "Debugging") == []


def test_kit_fails_when_the_question_repeats_an_answer() -> None:
    reply = kit_reply(("Same.", "same", "Other."), ("Fine?", "Yes.", "No."))
    assert [v.check for v in check_kit(reply, "Debugging")] == ["distinct"]


def test_kit_fails_when_the_question_is_only_the_criterion_name() -> None:
    reply = kit_reply(("Debugging!", "Yes.", "No."), ("Fine?", "Yes.", "No."))
    [violation] = check_kit(reply, "debugging")
    assert violation.detail == "question 1 is only the criterion name"


def test_kit_contract_fails_on_a_bad_reply_and_on_one_question() -> None:
    assert [v.check for v in check_kit("nope", "X")] == ["contract", "distinct"]
    assert check_kit(kit_reply(("Q?", "S.", "W.")), "X")
