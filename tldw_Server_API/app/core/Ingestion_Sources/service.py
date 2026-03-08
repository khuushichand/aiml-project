from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.Ingestion_Sources.models import (
    SINK_TYPES,
    SOURCE_POLICIES,
    SOURCE_TYPES,
)
from tldw_Server_API.app.core.exceptions import IngestionSourceValidationError


def _normalize_choice(value: Any, *, field_name: str, allowed: frozenset[str], default: str | None = None) -> str:
    raw = str(value if value is not None else default or "").strip().lower()
    if raw not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise IngestionSourceValidationError(
            f"Unsupported {field_name} '{raw}'. Allowed values: {allowed_values}"
        )
    return raw


def normalize_source_payload(data: dict[str, Any]) -> dict[str, Any]:
    source_type = _normalize_choice(
        data.get("source_type"),
        field_name="source_type",
        allowed=SOURCE_TYPES,
    )
    sink_type = _normalize_choice(
        data.get("sink_type"),
        field_name="sink_type",
        allowed=SINK_TYPES,
    )
    policy = _normalize_choice(
        data.get("policy"),
        field_name="policy",
        allowed=SOURCE_POLICIES,
        default="canonical",
    )
    enabled_raw = data.get("enabled")
    enabled = True if enabled_raw is None else bool(enabled_raw)
    return {
        "source_type": source_type,
        "sink_type": sink_type,
        "policy": policy,
        "enabled": enabled,
    }
