"""
Audit log tamper-proofing with hash chains.

Each audit event includes a hash of the previous event, creating a chain
that detects any modification or deletion of audit records.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from loguru import logger


def compute_event_hash(event: dict[str, Any], previous_hash: str = "") -> str:
    """Compute SHA-256 hash for an audit event chained to previous.

    The hash covers a canonical JSON representation of the event's key fields
    concatenated with the hash of the preceding event.

    Args:
        event: Audit event dictionary containing at least ``action``,
            ``user_id``, ``timestamp``, and ``detail`` keys.
        previous_hash: Hash of the immediately preceding event in the chain.
            Empty string for the first event.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    canonical = json.dumps(
        {
            "prev": previous_hash,
            "action": event.get("action", ""),
            "user_id": event.get("user_id"),
            "timestamp": event.get("timestamp", ""),
            "detail": event.get("detail", ""),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify_audit_chain(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify the integrity of a sequence of audit events.

    Each event is expected to carry a ``chain_hash`` field that was computed
    via :func:`compute_event_hash` at insertion time.  This function walks the
    list, recomputes each hash, and reports the first mismatch (if any).

    Args:
        events: Ordered list of audit event dicts (oldest first).

    Returns:
        A dict with keys ``valid`` (bool), ``checked`` (int),
        ``broken_at`` (int or None), and ``message`` (str).
    """
    if not events:
        return {"valid": True, "checked": 0, "broken_at": None, "message": "empty chain"}

    prev_hash = ""
    for i, event in enumerate(events):
        expected = compute_event_hash(event, prev_hash)
        stored_hash = event.get("chain_hash", "")
        if stored_hash and stored_hash != expected:
            logger.warning(
                "Audit chain broken at event {}: expected {}..., got {}...",
                i,
                expected[:16],
                stored_hash[:16],
            )
            return {
                "valid": False,
                "checked": i + 1,
                "broken_at": i,
                "message": (
                    f"chain broken at event {i}: "
                    f"expected {expected[:16]}..., got {stored_hash[:16]}..."
                ),
            }
        prev_hash = expected

    return {
        "valid": True,
        "checked": len(events),
        "broken_at": None,
        "message": "chain intact",
    }
