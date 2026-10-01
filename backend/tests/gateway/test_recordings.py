"""RecordingStore reads and writes one file per key and finds a recording for the same input."""

from pathlib import Path

import pytest

from app.gateway.errors import RecordingCorruptError
from app.gateway.recordings import RecordingStore
from app.gateway.types import RecordedResponse, Recording

KEY_A = "a" * 64
KEY_B = "b" * 64
INPUT = "c" * 64


def recording(key: str = KEY_A, *, schema_retry: int = 0, input_sha: str = INPUT) -> Recording:
    return Recording(
        key_version=1,
        request_key=key,
        input_sha256=input_sha,
        model="m",
        prompt_version="v1",
        schema_retry=schema_retry,
        purpose="scoring",
        response=RecordedResponse(
            text="{}", input_tokens=10, output_tokens=5, finish_reason="stop"
        ),
    )


def test_put_then_get_round_trips(tmp_path: Path) -> None:
    store = RecordingStore(tmp_path)
    store.put(recording())
    assert store.get(KEY_A) == recording()


def test_get_missing_returns_none(tmp_path: Path) -> None:
    assert RecordingStore(tmp_path).get(KEY_A) is None
    assert RecordingStore(tmp_path / "does-not-exist").get(KEY_A) is None


def test_put_creates_the_directory_and_leaves_no_temp_files(tmp_path: Path) -> None:
    directory = tmp_path / "recordings"
    RecordingStore(directory).put(recording())
    assert [p.name for p in directory.iterdir()] == [f"{KEY_A}.json"]


def test_put_writes_stable_sorted_json_for_clean_diffs(tmp_path: Path) -> None:
    RecordingStore(tmp_path).put(recording())
    text = (tmp_path / f"{KEY_A}.json").read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert text.index('"input_sha256"') < text.index('"request_key"')


def test_schema_retry_one_has_its_own_recording(tmp_path: Path) -> None:
    """REQ-023, decisions.md conflict 2: the retry after malformed output is a separate file."""
    store = RecordingStore(tmp_path)
    store.put(recording(KEY_A, schema_retry=0))
    store.put(recording(KEY_B, schema_retry=1))
    first, retry = store.get(KEY_A), store.get(KEY_B)
    assert first is not None
    assert retry is not None
    assert (first.schema_retry, retry.schema_retry) == (0, 1)


def test_find_stale_finds_a_recording_for_the_same_input(tmp_path: Path) -> None:
    """AC-US-02-003-3: a changed prompt is reported, not just a missing key."""
    store = RecordingStore(tmp_path)
    store.put(recording(KEY_A))
    assert store.find_stale(INPUT, exclude_key=KEY_B) == KEY_A


def test_find_stale_returns_none_when_nothing_matches(tmp_path: Path) -> None:
    store = RecordingStore(tmp_path)
    store.put(recording(KEY_A, input_sha="d" * 64))
    assert store.find_stale(INPUT, exclude_key=KEY_B) is None
    assert store.find_stale(INPUT, exclude_key=KEY_B) is None
    assert RecordingStore(tmp_path / "missing").find_stale(INPUT, exclude_key=KEY_B) is None


def test_find_stale_ignores_the_requested_key_itself(tmp_path: Path) -> None:
    store = RecordingStore(tmp_path)
    store.put(recording(KEY_A))
    assert store.find_stale(INPUT, exclude_key=KEY_A) is None


def test_find_stale_skips_corrupt_files_and_the_ledger(tmp_path: Path) -> None:
    (tmp_path / "spend-ledger.json").write_text('{"cumulative_live_usd": "0"}')
    (tmp_path / f"{KEY_B}.json").write_text("not json")
    assert RecordingStore(tmp_path).find_stale(INPUT, exclude_key=KEY_A) is None


def test_corrupt_recording_raises(tmp_path: Path) -> None:
    (tmp_path / f"{KEY_A}.json").write_text("{broken")
    with pytest.raises(RecordingCorruptError):
        RecordingStore(tmp_path).get(KEY_A)


def test_recording_under_the_wrong_file_name_raises(tmp_path: Path) -> None:
    body = recording(KEY_B).model_dump_json()
    (tmp_path / f"{KEY_A}.json").write_text(body)
    with pytest.raises(RecordingCorruptError, match="different request key"):
        RecordingStore(tmp_path).get(KEY_A)
