"""The scoring prompt: the registry's `scoring` version with the role's criteria filled in.

Only the system text is built here. The anonymized resume travels as the gateway's `input`
(the user turn), so it never enters a prompt template; the prompt declares it data.
"""

from app.gateway.text import PromptText
from app.prompts.registry import Prompt, load_prompt, render
from app.worker.ports import CriterionSpec


def _block(position: int, criterion: CriterionSpec) -> str:
    levels = "\n".join(f"   {level}: {text}" for level, text in criterion.rubric)
    return f"{position}. {criterion.name} ({criterion.kind})\n{levels}"


class ScoringPromptBuilder:
    """Implements `ScoringPrompt`. Numbers criteria 1..N in list order; the parser maps back."""

    def __init__(self, prompt: Prompt | None = None) -> None:
        self._prompt = prompt or load_prompt("scoring")

    @property
    def prompt_version(self) -> str:
        return self._prompt.prompt_version

    def build(self, criteria: list[CriterionSpec]) -> PromptText:
        text = "\n".join(_block(i, c) for i, c in enumerate(criteria, start=1))
        return render(self._prompt, {"criteria": text})
