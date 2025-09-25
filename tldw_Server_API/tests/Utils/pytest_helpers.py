"""
pytest_helpers.py

Minimal helper utilities to skip the current pytest test without aborting the whole run.

Usage examples:
- from tests.utils.pytest_helpers import skip_now
  def test_something():
      skip_now("Feature not available on Windows CI")

- from tests.utils.pytest_helpers import skip_unless
  def test_gpu_only():
      has_gpu = detect_gpu()
      skip_unless(has_gpu, "Requires GPU to run")

These helpers simply delegate to pytest.skip, which marks the current test as
skipped and continues with the rest of the test session.
"""
from __future__ import annotations

import pytest


def skip_now(reason: str = "skipped by request") -> None:
    """Skip the current test immediately without failing the test run.

    This wraps pytest.skip(...) to provide a clear, discoverable helper.
    It raises the internal SkipException used by pytest to mark the test
    as skipped and proceed with the rest of the suite.

    Args:
        reason: Human-readable explanation for why the test is skipped.
    """
    pytest.skip(reason)


def skip_unless(condition: bool, reason: str) -> None:
    """Skip the current test unless a condition is true.

    Args:
        condition: If False, skip the test.
        reason: Explanation when the test is skipped.
    """
    if not condition:
        pytest.skip(reason)
