"""Tests for the audio chat WebSocket streaming endpoint."""

import asyncio
import base64
import json
import time
from types import SimpleNamespace
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional

import pytest

from tldw_Server_API.app.api.v1.endpoints import audio


class DummyWebSocket:
    """In-memory WebSocket stub used for audio chat WebSocket tests."""

    def __init__(self, messages: Iterable[Dict[str, Any] | str]) -> None:
        self.headers: Dict[str, str] = {}
        self.query_params: Dict[str, str] = {}
        self.client = SimpleNamespace(host="127.0.0.1")
        self._messages: List[str] = [
            json.dumps(m) if isinstance(m, dict) else m for m in messages
        ]
        self.sent_bytes: List[bytes] = []
        self.sent_json: List[Dict[str, Any]] = []
        self.accepted: bool = False
        self.closed: bool = False
        self.close_code: Optional[int] = None
        self.close_calls: List[int] = []

    async def accept(self) -> None:
        """Mark the WebSocket as accepted."""
        self.accepted = True

    async def receive_text(self) -> str:
        """Return the next queued text frame, or raise when exhausted."""
        if not self._messages:
            raise RuntimeError("No more messages")  # noqa: TRY003
        return self._messages.pop(0)

    async def send_bytes(self, data: bytes) -> None:
        """Record bytes sent over the WebSocket."""
        self.sent_bytes.append(data)

    async def send_json(self, payload: Dict[str, Any]) -> None:
        """Record JSON payloads sent over the WebSocket."""
        self.sent_json.append(payload)

    async def close(self, code: int = 1000, reason: Optional[str] = None) -> None:  # noqa: ARG002
        """Record the close code and mark the WebSocket as closed."""
        self.close_calls.append(code)
        if not self.closed:
            self.close_code = code
        self.closed = True


class _DummyTranscriber:
    """Minimal streaming transcriber stub used in audio chat WebSocket tests."""

    def __init__(self, config: Any) -> None:  # noqa: ARG002
        self.reset_called = False

    def initialize(self) -> None:
        """Simulate transcriber initialization."""
        return None

    async def process_audio_chunk(self, audio_bytes: bytes) -> Dict[str, Any]:  # noqa: ARG002
        """Return a fixed partial transcription payload."""
        return {"type": "partial", "text": "hi"}

    def get_full_transcript(self) -> str:
        """Return a fixed full transcript."""
        return "hello world"

    def reset(self) -> None:
        """Record that reset was called."""
        self.reset_called = True


class _DummyVAD:
    """Simple VAD stub that never triggers an auto-commit."""

    available: bool = True
    unavailable_reason: Optional[str] = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
        self.last_trigger_at = time.time()

    def observe(self, audio_bytes: bytes) -> bool:  # noqa: ARG002
        """Update the last trigger timestamp and return False (no commit)."""
        self.last_trigger_at = time.time()
        return False


class _DummyRegistry:
    """Simple in-memory metrics registry stub."""

    def __init__(self) -> None:
        self.records: List[tuple[str, str, Any, Optional[Dict[str, Any]]]] = []
        self.registered: List[Any] = []

    def increment(self, name: str, value: int = 1, labels: Optional[Dict[str, Any]] = None) -> None:
        """Record an increment call."""
        self.records.append(("inc", name, value, labels))

    def observe(self, name: str, value: float, labels: Optional[Dict[str, Any]] = None) -> None:
        """Record an observe call."""
        self.records.append(("obs", name, value, labels))

    def register_metric(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
        """Record that a metric registration was requested."""
        self.registered.append(args)


class _DummyTTSService:
    """TTS service stub that yields a fixed sequence of chunks."""

    def __init__(self, chunks: Iterable[bytes]) -> None:
        """Initialize the stub with a fixed sequence of chunks."""
        self._chunks = list(chunks)

    async def generate_speech(self, *args: Any, **kwargs: Any) -> AsyncIterator[bytes]:  # noqa: ARG002
        """Yield preconfigured audio chunks."""
        for chunk in self._chunks:
            yield chunk


async def _llm_stub(**kwargs: Any) -> AsyncIterator[str]:  # noqa: ARG002
    """Stubbed streaming LLM generator returning a short response."""

    async def _gen() -> AsyncIterator[str]:
        yield 'data: {"choices":[{"delta":{"content":"hey "}}]}\n\n'
        yield 'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
        yield "data: [DONE]\n\n"

    return _gen()


@pytest.fixture(autouse=True)
def mock_audio_ws_dependencies(monkeypatch: pytest.MonkeyPatch) -> _DummyRegistry:
    """Fixture that sets up common mocks for audio streaming WebSocket tests."""

    async def _auth(*_args: Any, **_kwargs: Any) -> tuple[bool, int]:
        return True, 1

    async def _can_start_stream(_user_id: int) -> tuple[bool, Optional[str]]:
        return True, None

    async def _finish_stream(_user_id: int) -> None:
        return None

    async def _allow_minutes(_uid: int, _minutes: float) -> tuple[bool, Optional[float]]:
        return True, None

    async def _add_minutes(_uid: int, _minutes: float) -> None:
        return None

    async def _hb(_uid: int) -> None:
        return None

    monkeypatch.setattr(audio, "_audio_ws_authenticate", _auth)
    monkeypatch.setattr(audio, "can_start_stream", _can_start_stream)
    monkeypatch.setattr(audio, "finish_stream", _finish_stream)
    monkeypatch.setattr(audio, "check_daily_minutes_allow", _allow_minutes)
    monkeypatch.setattr(audio, "add_daily_minutes", _add_minutes)
    monkeypatch.setattr(audio, "heartbeat_stream", _hb)
    monkeypatch.setattr(audio, "UnifiedStreamingTranscriber", _DummyTranscriber)
    monkeypatch.setattr(audio, "SileroTurnDetector", _DummyVAD)
    monkeypatch.setattr(audio, "chat_api_call_async", _llm_stub)
    monkeypatch.setattr(audio, "get_api_keys", lambda: {"stub": "fake"})

    registry = _DummyRegistry()
    monkeypatch.setattr(audio, "get_metrics_registry", lambda: registry)

    return registry


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audio_chat_ws_streams_llm_and_tts(monkeypatch: pytest.MonkeyPatch) -> None:
    audio_payload = base64.b64encode(b"abc").decode("ascii")
    messages = [
        {
            "type": "config",
            "stt": {"model": "parakeet"},
            "llm": {"provider": "stub", "model": "stub-model"},
            "tts": {"voice": "af_heart", "format": "pcm"},
        },
        {"type": "audio", "data": audio_payload},
        {"type": "commit"},
        {"type": "stop"},
    ]
    ws = DummyWebSocket(messages)

    async def _get_tts_service():
        return _DummyTTSService([b"tts1", b"tts2"])

    monkeypatch.setattr(audio, "get_tts_service", _get_tts_service)

    await audio.websocket_audio_chat_stream(ws, token=None)

    # Assert LLM delta and transcript were sent
    assert any(msg.get("type") == "full_transcript" for msg in ws.sent_json)
    assert any(msg.get("type") == "llm_delta" for msg in ws.sent_json)
    assert any(msg.get("type") == "tts_done" for msg in ws.sent_json)
    assert ws.sent_bytes == [b"tts1", b"tts2"]
    assert ws.closed is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audio_chat_ws_quota_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    audio_payload = base64.b64encode(b"abc").decode("ascii")
    ws = DummyWebSocket(
        [
            {"type": "config", "stt": {"model": "parakeet"}, "llm": {"model": "stub"}, "tts": {"format": "mp3"}},
            {"type": "audio", "data": audio_payload},
        ]
    )

    async def _check_minutes(uid: int, minutes: float) -> tuple[bool, Optional[float]]:  # noqa: ARG002
        return False, None

    monkeypatch.setattr(audio, "check_daily_minutes_allow", _check_minutes)

    monkeypatch.setattr(audio, "get_tts_service", lambda: _DummyTTSService([b"x"]))

    await audio.websocket_audio_chat_stream(ws, token=None)

    quota_errors = [msg for msg in ws.sent_json if msg.get("error_type") == "quota_exceeded"]
    assert quota_errors, "Expected quota_exceeded message"
    # Close code should reflect quota policy (default 4003 unless env flips to 1008)
    assert ws.close_code in {4003, 1008}
    assert ws.closed is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audio_chat_ws_records_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    audio_payload = base64.b64encode(b"abcd").decode("ascii")
    ws = DummyWebSocket(
        [
            {
                "type": "config",
                "stt": {"model": "parakeet", "sample_rate": 16000},
                "llm": {"provider": "stub", "model": "stub-model"},
                "tts": {"voice": "af_heart", "format": "mp3"},
            },
            {"type": "audio", "data": audio_payload},
            {"type": "commit"},
            {"type": "stop"},
        ]
    )

    class QueueStub:
        """Queue stub that simulates initial overflow and then enqueues items."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
            self.items = []
            self.first_full = True

        def put_nowait(self, item: Any) -> None:
            if self.first_full:
                self.first_full = False
                raise asyncio.QueueFull
            self.items.append(item)

        async def put(self, item: Any) -> None:
            self.items.append(item)

        async def get(self) -> Any:
            while not self.items:
                await asyncio.sleep(0)
            return self.items.pop(0)

        def get_nowait(self) -> Any:
            if not self.items:
                raise asyncio.QueueEmpty
            return self.items.pop(0)

    class Registry:
        """Metrics registry stub used to capture increments and observations."""

        def __init__(self) -> None:
            self.increments = []
            self.observes = []
            self.registered = []

        def increment(self, name: str, value: int = 1, labels: Optional[Dict[str, Any]] = None) -> None:
            self.increments.append((name, value, labels or {}))

        def observe(self, name: str, value: float, labels: Optional[Dict[str, Any]] = None) -> None:
            self.observes.append((name, value, labels or {}))

        def register_metric(self, *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
            self.registered.append(args)

    reg = Registry()

    async def _allow_minutes(uid: int, minutes: float) -> tuple[bool, float]:  # noqa: ARG002
        return True, 10.0

    async def _get_tts_service():
        class _Service:
            async def generate_speech(self, *args: Any, **kwargs: Any) -> AsyncIterator[bytes]:  # noqa: ARG002
                reg.observe(
                    "voice_to_voice_seconds",
                    0.5,
                    labels={"provider": "stub", "route": kwargs.get("voice_to_voice_route", "")},
                )
                yield b"a"
                yield b"b"

        return _Service()

    monkeypatch.setattr(audio, "check_daily_minutes_allow", _allow_minutes)
    monkeypatch.setattr(audio, "get_tts_service", _get_tts_service)
    monkeypatch.setattr(audio, "get_metrics_registry", lambda: reg)

    # Ensure WS helper uses the same registry
    import tldw_Server_API.app.core.Streaming.streams as streams

    monkeypatch.setattr(streams, "get_metrics_registry", lambda: reg)

    monkeypatch.setattr(
        audio,
        "asyncio",
        SimpleNamespace(
            Queue=QueueStub,
            QueueFull=asyncio.QueueFull,
            QueueEmpty=asyncio.QueueEmpty,
            create_task=asyncio.create_task,
            wait=asyncio.wait,
            wait_for=asyncio.wait_for,
            FIRST_EXCEPTION=asyncio.FIRST_EXCEPTION,
            sleep=asyncio.sleep,
        ),
    )

    await audio.websocket_audio_chat_stream(ws, token=None)

    assert any(name == "audio_stream_underruns_total" for name, _, _ in reg.increments)
    assert any(name == "voice_to_voice_seconds" for name, _, _ in reg.observes)
    assert ws.closed is True
