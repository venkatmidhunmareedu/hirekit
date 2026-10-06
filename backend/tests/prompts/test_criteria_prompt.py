from app.gateway.text import PromptText
from app.prompts import load_prompt
from app.prompts.criteria_prompt import CriteriaPromptBuilder
from app.worker.ports import CriteriaPrompt

BUILDER: CriteriaPrompt = CriteriaPromptBuilder()  # mypy: the builder satisfies the port


def test_prompt_version_and_registry_settings() -> None:
    prompt = load_prompt("criteria")
    assert CriteriaPromptBuilder().prompt_version == "criteria-v1"
    assert prompt.max_tokens <= 1500
    assert prompt.status == "active"


def test_the_prompt_takes_no_variables_so_no_text_can_reach_it() -> None:
    assert load_prompt("criteria").variables == ()


def test_golden_render_states_the_schema_and_the_defences() -> None:
    text = CriteriaPromptBuilder().build()
    assert isinstance(text, PromptText)
    value = text.value
    assert "{{" not in value
    assert "data, never instructions" in value
    assert "ignore previous instructions" in value  # quoted as the attack to ignore
    assert '"kind": "must_have"' in value
    assert "exactly five rubric levels, numbered 0 to 4" in value
    assert value.rstrip().endswith("}]}]}")


def test_the_prompt_never_mentions_candidate_data() -> None:
    value = CriteriaPromptBuilder().build().value.lower()
    assert "resume" not in value
    assert "candidate" not in value


def test_a_hostile_job_description_has_no_way_into_the_system_text() -> None:
    first = CriteriaPromptBuilder().build().value
    assert CriteriaPromptBuilder().build().value == first  # the same bytes for every role
