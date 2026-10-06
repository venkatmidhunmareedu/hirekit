"""The criteria prompt: the registry's `criteria` version; the reply parser is `parse_criteria`.

The job description travels as the gateway's `input` (user turn), so the prompt takes no
variables and never holds job-description or candidate text.
"""

from app.gateway.text import PromptText
from app.prompts.criteria_parser import parse_criteria
from app.prompts.registry import Prompt, load_prompt, render
from app.worker.ports import ProposedCriterion


class CriteriaPromptBuilder:
    """Implements `CriteriaPrompt`."""

    def __init__(self, prompt: Prompt | None = None) -> None:
        self._prompt = prompt or load_prompt("criteria")

    @property
    def prompt_version(self) -> str:
        return self._prompt.prompt_version

    def build(self) -> PromptText:
        return render(self._prompt, {})

    def parse(self, reply: str) -> list[ProposedCriterion]:
        return parse_criteria(reply)
