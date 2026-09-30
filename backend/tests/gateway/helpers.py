"""Builders shared by the gateway tests."""

from uuid import UUID

from app.gateway.text import mint_anonymized, mint_job_description, mint_prompt
from app.gateway.types import GatewayRequest, Purpose

ROLE = UUID("10000000-0000-0000-0000-000000000001")


def make_request(
    *,
    purpose: Purpose = "scoring",
    prompt_version: str = "score-v1",
    max_tokens: int = 1000,
    schema_retry: int = 0,
    text: str = "Built a payments service in Python.",
) -> GatewayRequest:
    """A valid request whose input class matches its purpose."""
    resume_input = mint_anonymized(text) if purpose in ("scoring", "eval") else None
    return GatewayRequest(
        purpose=purpose,
        role_id=ROLE,
        prompt_version=prompt_version,
        system=mint_prompt("Score each criterion."),
        input=resume_input or mint_job_description(text),
        max_tokens=max_tokens,
        schema_retry=schema_retry,
    )
