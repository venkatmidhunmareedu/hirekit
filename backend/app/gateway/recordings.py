"""Recorded model replies, one JSON file per request key.

The methods are synchronous file IO; `Gateway.complete` calls them through
`asyncio.to_thread` so the event loop is never blocked.
"""

import json
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from app.gateway.errors import RecordingCorruptError
from app.gateway.types import Recording


class RecordingStore:
    """Reads and writes `<directory>/<request_key>.json`."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def _load(self, path: Path) -> Recording:
        try:
            recording = Recording.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as exc:
            msg = f"recording {path.name} cannot be read"
            raise RecordingCorruptError(msg) from exc
        if path.stem != recording.request_key:
            msg = f"recording {path.name} holds a different request key"
            raise RecordingCorruptError(msg)
        return recording

    def get(self, key: str) -> Recording | None:
        """The recording for `key`, or None when there is none."""
        path = self._path(key)
        if not path.is_file():
            return None
        return self._load(path)

    def put(self, recording: Recording) -> None:
        """Write atomically: a crash leaves the old file or none, never half a file."""
        self.directory.mkdir(parents=True, exist_ok=True)
        body = json.dumps(recording.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        fd, tmp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(body)
            Path(tmp).replace(self._path(recording.request_key))
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def find_stale(self, input_sha256: str, *, exclude_key: str) -> str | None:
        """Key of another recording made for the same input, or None.

        Used only on a miss, to say "changed prompt or model" instead of "never recorded".
        A directory scan is fine for a few hundred files; unreadable files are skipped.
        """
        if not self.directory.is_dir():
            return None
        for path in sorted(self.directory.glob("*.json")):
            if path.stem == exclude_key or path.name == "spend-ledger.json":
                continue
            try:
                recording = self._load(path)
            except RecordingCorruptError:
                continue
            if recording.input_sha256 == input_sha256:
                return recording.request_key
        return None
