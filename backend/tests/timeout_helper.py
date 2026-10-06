"""Run a function in a separate process under a hard timeout.

A regex runs in C and cannot be interrupted in-process, so the only proof that
it does not backtrack catastrophically is a child process that is killed on
time. The target must be a module-level function so the spawned child can import it.
"""

import multiprocessing
from collections.abc import Callable

import pytest


def run_with_timeout(target: Callable[[], None], seconds: float) -> None:
    """Fail the test if the target raises, exits non-zero or outlives the timeout."""
    process = multiprocessing.get_context("spawn").Process(target=target)
    process.start()
    process.join(seconds)
    if process.is_alive():
        process.kill()
        process.join()
        pytest.fail(f"{target.__name__} still running after {seconds}s, killed")
    assert process.exitcode == 0, f"{target.__name__} exited with code {process.exitcode}"
