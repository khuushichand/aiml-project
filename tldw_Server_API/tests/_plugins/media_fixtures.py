"""Pytest plugin: media fixtures

Lightweight fixtures for creating temporary media assets used across tests.
Keeps creation/cleanup inside fixture functions to avoid import-time work.
"""

from __future__ import annotations

from typing import Generator
import pytest

from tldw_Server_API.tests.e2e.fixtures import (
    create_test_file,
    create_test_pdf,
    create_test_audio,
    cleanup_test_file,
)


def _yield_file(path: str) -> Generator[str, None, None]:
    try:
        yield path
    finally:
        try:
            cleanup_test_file(path)
        except Exception as e:
            # Visible but non-fatal in tests: cleanup failures shouldn't mask test results
            print(f"[media_fixtures] Warning: failed to cleanup temp file {path}: {e}")


@pytest.fixture
def test_text_file() -> Generator[str, None, None]:  # pragma: no cover - fixture wrapper
    """Provide a path to a temporary text file and clean it up after use."""
    yield from _yield_file(create_test_file("Sample test content\n", suffix=".txt"))


@pytest.fixture
def test_pdf_file() -> Generator[str, None, None]:  # pragma: no cover - fixture wrapper
    """Provide a path to a temporary PDF file and clean it up after use."""
    yield from _yield_file(create_test_pdf())


@pytest.fixture
def test_audio_file() -> Generator[str, None, None]:  # pragma: no cover - fixture wrapper
    """Provide a path to a temporary audio file and clean it up after use."""
    yield from _yield_file(create_test_audio())


__all__ = [
    "test_text_file",
    "test_pdf_file",
    "test_audio_file",
]
