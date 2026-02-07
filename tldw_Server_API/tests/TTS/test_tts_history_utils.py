import hashlib
import hmac

import pytest

from tldw_Server_API.app.core.TTS.utils import (
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
