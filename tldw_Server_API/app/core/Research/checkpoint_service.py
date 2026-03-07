"""Checkpoint patching helpers for deep research review steps."""

from __future__ import annotations

from typing import Any


def _merge_values(existing: Any, patch: Any) -> Any:
    if isinstance(existing, dict) and isinstance(patch, dict):
        merged = dict(existing)
        for key, value in patch.items():
            merged[key] = _merge_values(merged.get(key), value)
        return merged
    return patch


def apply_checkpoint_patch(
    *,
    proposed_payload: dict[str, Any],
    patch_payload: dict[str, Any],
) -> dict[str, Any]:
    """Apply a user patch to a proposed checkpoint payload."""
    merged = dict(proposed_payload)
    for key, value in patch_payload.items():
        merged[key] = _merge_values(merged.get(key), value)
    return merged
