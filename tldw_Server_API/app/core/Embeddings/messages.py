"""
Embeddings stream message schema helpers.

This module provides a lightweight validator for embeddings pipeline payloads
used by DLQ tooling. It intentionally stays permissive to avoid blocking
requeue operations while still catching obviously malformed payloads.
"""

from __future__ import annotations

from typing import Any, Mapping

VALID_STAGES = {"chunking", "embedding", "storage"}


def validate_schema(stage: str, payload: Mapping[str, Any]) -> None:
    """Validate a DLQ payload for a given stage.

    This is a minimal sanity check used by DLQ requeue tooling. It raises
    ValueError for invalid stage values or empty/non-dict payloads. It does not
    attempt to enforce strict schemas for each stage.
    """
    if not isinstance(stage, str):
        raise ValueError("stage must be a string")
    stage_normalized = stage.strip().lower()
    if stage_normalized not in VALID_STAGES:
        raise ValueError(f"invalid stage '{stage}' (expected one of: {', '.join(sorted(VALID_STAGES))})")

    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    if not payload:
        raise ValueError("payload is empty")
