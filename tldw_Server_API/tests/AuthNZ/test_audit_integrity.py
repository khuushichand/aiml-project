"""Tests for audit log tamper-proofing (hash chain)."""
from __future__ import annotations

import pytest

from tldw_Server_API.app.core.AuthNZ.audit_integrity import (
    compute_event_hash,
    verify_audit_chain,
)


def _make_event(action: str, user_id: int, timestamp: str, detail: str = "") -> dict:
    return {
        "action": action,
        "user_id": user_id,
        "timestamp": timestamp,
        "detail": detail,
    }


def _build_chain(events: list[dict]) -> list[dict]:
    """Build a valid hash chain for a list of events."""
    prev_hash = ""
    chained: list[dict] = []
    for event in events:
        h = compute_event_hash(event, prev_hash)
        chained.append({**event, "chain_hash": h})
        prev_hash = h
    return chained


class TestComputeEventHash:
    def test_deterministic(self):
        event = _make_event("login", 1, "2026-01-01T00:00:00Z")
        h1 = compute_event_hash(event)
        h2 = compute_event_hash(event)
        assert h1 == h2

    def test_different_actions_produce_different_hashes(self):
        e1 = _make_event("login", 1, "2026-01-01T00:00:00Z")
        e2 = _make_event("logout", 1, "2026-01-01T00:00:00Z")
        assert compute_event_hash(e1) != compute_event_hash(e2)

    def test_chaining_changes_hash(self):
        event = _make_event("login", 1, "2026-01-01T00:00:00Z")
        h_no_prev = compute_event_hash(event, "")
        h_with_prev = compute_event_hash(event, "abc123")
        assert h_no_prev != h_with_prev

    def test_hash_is_hex_sha256(self):
        event = _make_event("login", 1, "2026-01-01T00:00:00Z")
        h = compute_event_hash(event)
        assert len(h) == 64
        int(h, 16)  # Should not raise

    def test_missing_fields_handled(self):
        # Event with no keys at all should still produce a valid hash
        h = compute_event_hash({})
        assert len(h) == 64


class TestVerifyAuditChain:
    def test_empty_chain_is_valid(self):
        result = verify_audit_chain([])
        assert result["valid"] is True
        assert result["checked"] == 0
        assert result["broken_at"] is None

    def test_single_event_valid(self):
        events = _build_chain([_make_event("login", 1, "2026-01-01T00:00:00Z")])
        result = verify_audit_chain(events)
        assert result["valid"] is True
        assert result["checked"] == 1

    def test_multi_event_valid(self):
        raw = [
            _make_event("login", 1, "2026-01-01T00:00:00Z"),
            _make_event("view", 1, "2026-01-01T00:01:00Z"),
            _make_event("logout", 1, "2026-01-01T00:02:00Z"),
        ]
        events = _build_chain(raw)
        result = verify_audit_chain(events)
        assert result["valid"] is True
        assert result["checked"] == 3

    def test_tampered_event_detected(self):
        raw = [
            _make_event("login", 1, "2026-01-01T00:00:00Z"),
            _make_event("view", 1, "2026-01-01T00:01:00Z"),
            _make_event("logout", 1, "2026-01-01T00:02:00Z"),
        ]
        events = _build_chain(raw)
        # Tamper with the second event's action
        events[1]["action"] = "delete"
        result = verify_audit_chain(events)
        assert result["valid"] is False
        assert result["broken_at"] == 1

    def test_deleted_event_detected(self):
        raw = [
            _make_event("login", 1, "2026-01-01T00:00:00Z"),
            _make_event("view", 1, "2026-01-01T00:01:00Z"),
            _make_event("logout", 1, "2026-01-01T00:02:00Z"),
        ]
        events = _build_chain(raw)
        # Remove the middle event -- the third event's chain_hash won't match
        del events[1]
        result = verify_audit_chain(events)
        assert result["valid"] is False
        assert result["broken_at"] == 1

    def test_events_without_chain_hash_pass(self):
        """Events without stored chain_hash are treated as unverified (not broken)."""
        events = [
            _make_event("login", 1, "2026-01-01T00:00:00Z"),
            _make_event("view", 1, "2026-01-01T00:01:00Z"),
        ]
        result = verify_audit_chain(events)
        assert result["valid"] is True
        assert result["checked"] == 2

    def test_first_event_tampered(self):
        raw = [
            _make_event("login", 1, "2026-01-01T00:00:00Z"),
            _make_event("view", 1, "2026-01-01T00:01:00Z"),
        ]
        events = _build_chain(raw)
        events[0]["action"] = "hacked"
        result = verify_audit_chain(events)
        assert result["valid"] is False
        assert result["broken_at"] == 0
