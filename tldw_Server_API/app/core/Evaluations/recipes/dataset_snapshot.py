"""Dataset snapshot helpers for recipe runs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


def build_dataset_snapshot_ref(dataset_id: str, dataset_version: str | int) -> str:
    """Build a stable dataset snapshot reference."""
    return f"{dataset_id}@v{dataset_version}"


def build_dataset_content_hash(payload: Any) -> str:
    """Build a deterministic content hash for a dataset payload."""
    serialized = json.dumps(
        _normalize_json_payload(payload),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalize_json_payload(value: Any, *, path: str = "payload") -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, nested_value in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} contains a non-string key, which is not JSON serializable.")
            normalized[key] = _normalize_json_payload(nested_value, path=f"{path}.{key}")
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _normalize_json_payload(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise TypeError(f"{path} contains a value of type {type(value).__name__}, which is not JSON serializable.")


@dataclass(frozen=True)
class DatasetSnapshot:
    """Immutable view of the dataset identity captured at run time."""

    dataset_id: str
    dataset_version: str | int
    snapshot_ref: str | None = None
    content_hash: str | None = None
