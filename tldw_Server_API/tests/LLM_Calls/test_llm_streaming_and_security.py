import json
from typing import List

import pytest


class _DummyResponse:
    def __init__(self, lines: List[bytes]):
        self._lines = lines
        self._closed = False
        self.status_code = 200

    def iter_lines(self):
        for line in self._lines:
            yield line

    def raise_for_status(self):
        return None

    def close(self):
        self._closed = True


class _DummySession:
    def __init__(self, lines: List[bytes] = None, exc: Exception = None):
        self._lines = lines or []
        self._exc = exc
        self.closed = False

    def post(self, *args, **kwargs):
        if self._exc is not None:
            raise self._exc
        return _DummyResponse(self._lines)

    def close(self):
        self.closed = True


def test_google_stream_emits_done_once(monkeypatch):
    # Arrange: stub config and session to simulate two SSE lines: one data chunk and one [DONE]
    from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as m

    monkeypatch.setattr(
        m, "load_and_log_configs",
        lambda: {
            'google_api': {
                'api_key': 'test-key',
                'model': 'gemini-1.5-flash-latest',
                'streaming': True,
            }
        },
    )

    first_chunk = {
        "candidates": [
            {"content": {"parts": [{"text": "hello"}]}}
        ]
    }
    lines = [
        f"data: {json.dumps(first_chunk)}".encode("utf-8"),
        b"data: [DONE]",
    ]

    monkeypatch.setattr(m, "create_session_with_retries", lambda *a, **k: _DummySession(lines))

    # Act: call google chat with streaming enabled
    gen = m.chat_with_google(
        input_data=[{"role": "user", "content": "hi"}],
        streaming=True,
    )
    chunks = list(gen)

    # Assert: ensure only one [DONE]
    done_count = sum(1 for c in chunks if c.strip().lower() == "data: [done]")
    assert done_count == 1, f"Expected exactly one [DONE], got {done_count}. Chunks: {chunks}"


def test_huggingface_headers_are_masked(monkeypatch):
    # Arrange: capture debug calls by monkeypatching the logger's debug method
    from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as m

    secret = "sk-ABCDEF1234567890"
    monkeypatch.setattr(
        m, "load_and_log_configs",
        lambda: {
            'huggingface_api': {
                'api_key': secret,
                'api_base_url': 'https://api-inference.huggingface.co/v1',
            }
        },
    )

    # Make network call fail after logging so we don't reach the real network
    monkeypatch.setattr(m, "create_session_with_retries", lambda *a, **k: _DummySession(exc=RuntimeError("stop")))

    captured_debug = []

    def _fake_debug(msg, *args, **kwargs):
        captured_debug.append(str(msg))

    # Monkeypatch the loguru logger used in the module
    monkeypatch.setattr(m.logging, "debug", _fake_debug)

    # Act: invoke; ignore the intentional failure after header logging
    try:
        m.chat_with_huggingface(
            input_data=[{"role": "user", "content": "hi"}],
            streaming=False,
            model="test/Model-Stub",
        )
    except Exception:
        pass

    # Assert: debug output contains masked headers and not the secret key
    joined = "\n".join(captured_debug)
    assert "HuggingFace Headers:" in joined
    assert secret not in joined
    assert "***" in joined
