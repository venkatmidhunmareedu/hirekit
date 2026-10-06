"""The criteria limits shared by the model-reply parser and the role API (ADR-0010).

They live here, not in `app.prompts.criteria_parser`, because that module imports the Worker and the
API must not.
"""

from typing import Final

MIN_CRITERIA: Final = 1
MAX_CRITERIA: Final = 8
MIN_WEIGHT: Final = 1
MAX_WEIGHT: Final = 5
MAX_NAME_CHARS: Final = 80
MAX_DESCRIPTOR_CHARS: Final = 200
LEVELS: Final = (0, 1, 2, 3, 4)
KINDS: Final = ("must_have", "nice_to_have")
