"""The replay key: a SHA-256 of the normalized request, the model and the prompt version.

Every text is NFC-normalized and its newlines converted to LF before hashing, and
the JSON is UTF-8, so a CRLF checkout or another Unicode form of the same text gives
the same key on any machine. `role_id`, timestamps and run ids are never part of it.
"""

import hashlib
import json
import unicodedata

KEY_VERSION = 1
TEMPERATURE = 0


def normalize(text: str) -> str:
    """NFC form with LF newlines: the form every hashed text takes."""
    return unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")


def _sha256(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def request_key(
    *,
    model: str,
    prompt_version: str,
    schema_retry: int,
    max_tokens: int,
    system: str,
    input_text: str,
) -> str:
    """The key of one request. `max_tokens` is the clamped value that is sent."""
    return _sha256(
        {
            "key_version": KEY_VERSION,
            "model": model,
            "prompt_version": prompt_version,
            "schema_retry": schema_retry,
            "max_tokens": max_tokens,
            "temperature": TEMPERATURE,
            "system": normalize(system),
            "input": normalize(input_text),
        }
    )


def input_sha256(*, purpose: str, schema_retry: int, input_text: str) -> str:
    """Hash of the input alone, so a miss can say a recording exists under another prompt."""
    return _sha256(
        {
            "key_version": KEY_VERSION,
            "purpose": purpose,
            "schema_retry": schema_retry,
            "input": normalize(input_text),
        }
    )
