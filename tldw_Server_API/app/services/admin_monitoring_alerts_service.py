from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


_FINGERPRINT_FIELDS = (
    "source",
    "watchlist_id",
    "rule_id",
    "source_id",
    "chunk_id",
    "chunk_seq",
    "text_snippet",
    "created_at",
)


def build_alert_identity(raw_alert: Mapping[str, Any]) -> str:
    """Return a stable backend identity for a runtime monitoring alert."""
    runtime_alert_id = raw_alert.get("id")
    if runtime_alert_id not in (None, ""):
        return f"alert:{runtime_alert_id}"

    fingerprint_payload = {
        field_name: raw_alert.get(field_name)
        for field_name in _FINGERPRINT_FIELDS
        if raw_alert.get(field_name) is not None
    }
    encoded_payload = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded_payload.encode("utf-8")).hexdigest()
    return f"fingerprint:{digest}"


def merge_runtime_alert_with_overlay(
    raw_alert: Mapping[str, Any],
    overlay: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge persisted admin overlay state onto a runtime monitoring alert."""
    merged_alert = dict(raw_alert)
    merged_alert["alert_identity"] = build_alert_identity(raw_alert)

    if overlay:
        for field_name in (
            "assigned_to_user_id",
            "snoozed_until",
            "dismissed_at",
            "acknowledged_at",
            "escalated_severity",
        ):
            if field_name in overlay:
                merged_alert[field_name] = overlay[field_name]

        if overlay.get("alert_identity"):
            merged_alert["alert_identity"] = overlay["alert_identity"]

    acknowledged_at = merged_alert.get("acknowledged_at")
    read_at = merged_alert.get("read_at")
    merged_alert["is_read"] = bool(acknowledged_at or read_at or raw_alert.get("is_read"))

    if acknowledged_at and not read_at:
        merged_alert["read_at"] = acknowledged_at

    return merged_alert
