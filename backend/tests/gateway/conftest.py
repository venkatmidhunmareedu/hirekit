"""Gateway test setup: replay mode, no CI variable, and no .env file, whatever the machine has."""

import pytest


@pytest.fixture(autouse=True)
def _replay_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """A gateway test never starts in live mode by accident (tenet 5)."""
    monkeypatch.setenv("MODEL_MODE", "replay")
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
