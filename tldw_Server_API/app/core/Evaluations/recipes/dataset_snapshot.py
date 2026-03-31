"""Dataset snapshot helpers for recipe runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


def build_dataset_snapshot_ref(dataset_id: str, dataset_version: str | int) -> str:
    """Build a stable dataset snapshot reference."""
    return f"{dataset_id}@v{dataset_version}"


def build_dataset_content_hash(payload: Any) -> str:
    """Build a deterministic content hash for a dataset payload."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DatasetSnapshot:
    """Immutable view of the dataset identity captured at run time."""

    dataset_id: str
    dataset_version: str | int
    snapshot_ref: str | None = None
    content_hash: str | None = None
