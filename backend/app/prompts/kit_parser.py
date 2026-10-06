"""The kit reply parser (ADR-0010): strict JSON, 2 to 3 questions for the one criterion asked.

Refuses what the `questions` CHECK would (a blank question, strong or weak answer). The count and
length caps are proposed numbers that need engineer confirmation (prompts/kit/CHANGELOG.md).
Every failure raises `SchemaError` with a constant message, never reply text (tenet 7).
"""

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError

from app.worker.errors import SchemaError
from app.worker.ports import ProposedQuestion

MIN_QUESTIONS: Final = 2
MAX_QUESTIONS: Final = 3
MAX_QUESTION_CHARS: Final = 300
MAX_ANSWER_CHARS: Final = 500
_MESSAGE: Final = "The kit reply did not match the schema."


class _Question(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question: StrictStr
    strong_answer: StrictStr
    weak_answer: StrictStr


class _Reply(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    questions: list[_Question] = Field(min_length=MIN_QUESTIONS, max_length=MAX_QUESTIONS)


def parse_kit(reply: str) -> list[ProposedQuestion]:
    try:
        items = _Reply.model_validate_json(reply).questions
    except ValidationError:
        raise SchemaError(_MESSAGE) from None  # the chained error would quote the reply
    return [
        ProposedQuestion(
            _text(i.question, MAX_QUESTION_CHARS),
            _text(i.strong_answer, MAX_ANSWER_CHARS),
            _text(i.weak_answer, MAX_ANSWER_CHARS),
        )
        for i in items
    ]


def _text(text: str, limit: int) -> str:
    text = text.strip()
    if not text or len(text) > limit:
        raise SchemaError(_MESSAGE)
    return text
