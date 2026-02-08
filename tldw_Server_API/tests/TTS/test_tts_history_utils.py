import hashlib
import hmac
import json

import pytest

from tldw_Server_API.app.core.TTS.utils import (
    build_tts_segments_payload,
    compute_tts_history_text_hash,
    normalize_tts_history_text,
    tts_history_text_length,
)


def test_normalize_tts_history_text_collapses_whitespace_and_newlines() -> None:
    raw = "  A\tB\r\nC\rD   "
    assert normalize_tts_history_text(raw) == "A B C D"


def test_normalize_tts_history_text_nfkc() -> None:
    # Fullwidth A (NFKC -> ASCII A)
    raw = "\uff21"
    assert normalize_tts_history_text(raw) == "A"


def test_compute_tts_history_text_hash_requires_secret() -> None:
    with pytest.raises(ValueError, match="TTS_HISTORY_HASH_KEY is required"):
        compute_tts_history_text_hash("hello", secret=None)


def test_compute_tts_history_text_hash_matches_hmac() -> None:
    secret = "test-secret"
    text = "  hello\nworld  "
    normalized = normalize_tts_history_text(text)
    expected = hmac.new(secret.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256).hexdigest()
    assert compute_tts_history_text_hash(text, secret=secret) == expected


def test_tts_history_text_length_uses_normalized_text() -> None:
    assert tts_history_text_length("  A   B ") == 3


def _json_size_bytes(value: object) -> int:
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))


def test_build_tts_segments_payload_truncates_over_64kb_and_keeps_failures() -> None:
    segments: list[dict[str, object]] = []
    for idx in range(140):
        segments.append(
            {
                "index": idx,
                "status": "success",
                "attempts": 1,
                "duration_ms": 100,
                "detail": "s" * 640,
            }
        )
    failed_indices = [33, 77, 121]
    for idx in failed_indices:
        segments[idx]["status"] = "failed"
        segments[idx]["error"] = "provider_error"
        segments[idx]["detail"] = "f" * 640

    # Precondition: raw payload is larger than the 64KB cap.
    raw_payload = {
        "segments": segments,
        "summary": {"total": len(segments), "success": 137, "failed": 3, "total_duration_ms": 14000, "max_attempts": 1},
        "truncated": False,
    }
    assert _json_size_bytes(raw_payload) > 64 * 1024

    payload = build_tts_segments_payload(segments)
    assert payload is not None
    assert payload["truncated"] is True
    assert payload["summary"]["total"] == 140
    assert payload["summary"]["failed"] == 3

    kept_segments = payload["segments"]
    kept_failed = {seg["index"] for seg in kept_segments if seg.get("status") == "failed"}
    assert kept_failed == set(failed_indices)
    assert len(kept_segments) < len(segments)
    assert _json_size_bytes(payload) <= 64 * 1024


def test_build_tts_segments_payload_caps_failed_segments_to_most_recent_256() -> None:
    segments = [
        {
            "index": idx,
            "status": "failed",
            "attempts": 2,
            "duration_ms": 50,
            "error": "x" * 20,
        }
        for idx in range(400)
    ]

    payload_400 = {
        "segments": segments,
        "summary": {"total": 400, "success": 0, "failed": 400, "total_duration_ms": 20000, "max_attempts": 2},
        "truncated": False,
    }
    payload_256 = {
        "segments": segments[-256:],
        "summary": payload_400["summary"],
        "truncated": True,
    }
    max_bytes = (int(_json_size_bytes(payload_256)) + int(_json_size_bytes(payload_400))) // 2

    payload = build_tts_segments_payload(segments, max_bytes=max_bytes)
    assert payload is not None
    assert payload["truncated"] is True
    kept = payload["segments"]
    assert len(kept) == 256
    assert kept[0]["index"] == 144
    assert kept[-1]["index"] == 399
    assert payload["summary"]["total"] == 400
    assert payload["summary"]["failed"] == 400


def test_build_tts_segments_payload_adds_most_recent_successes_after_failed() -> None:
    failed_segments = [
        {
            "index": idx,
            "status": "failed",
            "attempts": 2,
            "duration_ms": 50,
            "error": "fail",
        }
        for idx in range(260)
    ]
    success_segments = [
        {
            "index": idx,
            "status": "success",
            "attempts": 1,
            "duration_ms": 50,
            "note": "ok",
        }
        for idx in range(260, 300)
    ]
    segments = failed_segments + success_segments

    failed_only_payload = {"segments": failed_segments[-256:], "summary": {"total": 300, "success": 40, "failed": 260}}
    all_segments_payload = {"segments": segments, "summary": {"total": 300, "success": 40, "failed": 260}}
    low = _json_size_bytes(failed_only_payload)
    high = _json_size_bytes(all_segments_payload)
    max_bytes = low + max(1, (high - low) // 3)

    payload = build_tts_segments_payload(segments, max_bytes=max_bytes)
    assert payload is not None
    assert payload["truncated"] is True

    kept_indices = [int(seg["index"]) for seg in payload["segments"]]
    kept_failures = [idx for idx in kept_indices if idx < 260]
    kept_successes = [idx for idx in kept_indices if idx >= 260]

    assert kept_failures[0] == 4
    assert kept_failures[-1] == 259
    assert kept_successes
    assert kept_successes[-1] == 299
    assert kept_successes == list(range(300 - len(kept_successes), 300))
