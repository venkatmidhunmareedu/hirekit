"""GatewayRequest validates its own values and clamps max_tokens."""

import pytest

from app.gateway.errors import InvalidRequestError
from app.gateway.text import AnonymizedText, JobDescriptionText
from app.gateway.types import MAX_TOKENS_CAP, PURPOSE_INPUT, GatewayRequest
from tests.gateway.helpers import make_request


def test_max_tokens_above_cap_is_clamped_to_1500() -> None:
    """AC-US-02-001-3."""
    assert make_request(max_tokens=100_000).clamped_max_tokens == 1500


def test_max_tokens_at_or_below_cap_passes_unchanged() -> None:
    """AC-US-02-001-3, the pair."""
    assert make_request(max_tokens=1500).clamped_max_tokens == 1500
    assert make_request(max_tokens=200).clamped_max_tokens == 200
    assert MAX_TOKENS_CAP == 1500


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_tokens": 0},
        {"max_tokens": -5},
        {"schema_retry": 2},
        {"schema_retry": -1},
        {"prompt_version": "  "},
    ],
)
def test_invalid_request_fields_raise_invalid_request(overrides: dict[str, int | str]) -> None:
    with pytest.raises(InvalidRequestError):
        make_request(**overrides)  # type: ignore[arg-type]  # deliberately bad values


def test_a_purpose_outside_the_four_raises_invalid_request() -> None:
    good = make_request()
    with pytest.raises(InvalidRequestError, match="purpose"):
        GatewayRequest(
            purpose="chat",  # type: ignore[arg-type]  # deliberately bad value
            role_id=None,
            prompt_version="v1",
            system=good.system,
            input=good.input,
            max_tokens=10,
            schema_retry=0,
        )


def test_schema_retry_above_one_is_rejected() -> None:
    """REQ-023, the limit pair: 0 and 1 are valid, 2 is not."""
    assert make_request(schema_retry=0).schema_retry == 0
    assert make_request(schema_retry=1).schema_retry == 1
    with pytest.raises(InvalidRequestError):
        make_request(schema_retry=2)


def test_every_purpose_maps_to_one_input_class() -> None:
    """AC-US-00-005-4: resume purposes take AnonymizedText, the rest take a job description."""
    assert PURPOSE_INPUT["scoring"] is AnonymizedText
    assert PURPOSE_INPUT["eval"] is AnonymizedText
    assert PURPOSE_INPUT["criteria"] is JobDescriptionText
    assert PURPOSE_INPUT["kit"] is JobDescriptionText
