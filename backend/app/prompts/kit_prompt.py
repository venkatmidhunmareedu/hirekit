"""The kit prompt: the registry's `kit` version with one criterion and its rubric filled in.

The job description travels as the gateway's `input`; the criterion (name, kind, rubric levels)
is the only variable. Never resume text. The reply parser is `parse_kit`.
"""

from app.gateway.text import PromptText
from app.prompts.kit_parser import parse_kit
from app.prompts.registry import Prompt, load_prompt, render
from app.worker.ports import CriterionSpec, ProposedQuestion


class KitPromptBuilder:
    """Implements `KitPrompt`."""

    def __init__(self, prompt: Prompt | None = None) -> None:
        self._prompt = prompt or load_prompt("kit")

    @property
    def prompt_version(self) -> str:
        return self._prompt.prompt_version

    def build(self, criterion: CriterionSpec) -> PromptText:
        levels = "\n".join(f"   {level}: {text}" for level, text in criterion.rubric)
        return render(self._prompt, {"criterion": f"{criterion.name} ({criterion.kind})\n{levels}"})

    def parse(self, reply: str) -> list[ProposedQuestion]:
        return parse_kit(reply)
