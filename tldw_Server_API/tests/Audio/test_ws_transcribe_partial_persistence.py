"""Tests for optional transcript persistence in /audio/stream/transcribe."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tldw_Server_API.app.api.v1.endpoints import audio
from tldw_Server_API.app.api.v1.endpoints.audio import audio_streaming


class DummyWebSocket:
    """Minimal WebSocket stub for direct websocket_transcribe invocation."""

    def __init__(self, query_params: dict[str, str] | None = None) -> None:
        self.headers: dict[str, str] = {}
        self.query_params: dict[str, str] = query_params or {}
        self.client = SimpleNamespace(host="127.0.0.1")
        self.sent_json: list[dict[str, Any]] = []
        self.closed = False
        self.close_code: int | None = None
        self.close_calls: list[int] = []
        self.accepted = False
        self.application_state = None

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent_json.append(payload)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:  # noqa: ARG002
        self.closed = True
        self.close_code = code
        self.close_calls.append(code)


class DummyMediaDB:
    """Tracks connection release calls."""

    def __init__(self) -> None:
        self.release_count = 0

    def release_context_connection(self) -> None:
        self.release_count += 1


@pytest.fixture(autouse=True)
def _mock_transcribe_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch auth/quota dependencies so tests focus on persistence behavior."""

    async def _auth(*_args: Any, **_kwargs: Any) -> tuple[bool, int]:
        return True, 1

    async def _can_start_stream(_user_id: int) -> tuple[bool, str | None]:
        return True, None

    async def _finish_stream(_user_id: int) -> None:
        return None

    async def _allow_minutes(_uid: int, _minutes: float) -> tuple[bool, float | None]:
        return True, None

    async def _add_minutes(_uid: int, _minutes: float) -> None:
        return None

    async def _heartbeat(_uid: int) -> None:
        return None

    monkeypatch.setattr(audio, "_audio_ws_authenticate", _auth)
    monkeypatch.setattr(audio, "can_start_stream", _can_start_stream)
    monkeypatch.setattr(audio, "finish_stream", _finish_stream)
    monkeypatch.setattr(audio, "check_daily_minutes_allow", _allow_minutes)
    monkeypatch.setattr(audio, "add_daily_minutes", _add_minutes)
    monkeypatch.setattr(audio, "heartbeat_stream", _heartbeat)
    monkeypatch.setattr(audio_streaming, "is_multi_user_mode", lambda: False)

    # Force websocket_transcribe to use its simple _BareStream adapter.
    import tldw_Server_API.app.core.Streaming.streams as streams_mod

    class _FailWebSocketStream:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("force bare stream path for tests")

    monkeypatch.setattr(streams_mod, "WebSocketStream", _FailWebSocketStream)


@pytest.mark.asyncio
async def test_stream_transcribe_persists_partial_and_final(monkeypatch: pytest.MonkeyPatch) -> None:
    ws = DummyWebSocket(
        query_params={
            "persist_transcript": "1",
            "persist_partial_transcript": "1",
            "media_id": "42",
        }
    )
    db = DummyMediaDB()
    calls: list[dict[str, Any]] = []

    monkeypatch.setattr(audio_streaming, "_resolve_media_db_for_user", lambda _user: db)

    def _upsert(db_instance, media_id: int, transcription: str, whisper_model: str, created_at=None):  # noqa: ANN001
        calls.append(
            {
                "db": db_instance,
                "media_id": media_id,
                "transcription": transcription,
                "whisper_model": whisper_model,
                "created_at": created_at,
            }
        )
        return {"id": len(calls)}

    monkeypatch.setattr(audio_streaming, "upsert_transcript", _upsert)

    async def _mock_handle(
        _websocket,
        config,
        *,
        on_audio_seconds=None,  # noqa: ARG001
        on_heartbeat=None,  # noqa: ARG001
        on_stream_config_resolved=None,
        on_transcript_result=None,
        on_full_transcript=None,
    ):
        if on_stream_config_resolved is not None:
            await on_stream_config_resolved({"type": "config", "transcription_model": "stream-live-model"}, config)
        if on_transcript_result is not None:
            await on_transcript_result({"type": "partial", "text": "hello", "is_final": False}, "")
            await on_transcript_result(
                {"type": "transcription", "text": "hello world", "is_final": True},
                "hello world",
            )
        if on_full_transcript is not None:
            await on_full_transcript("hello world final", False)

    monkeypatch.setattr(audio_streaming, "handle_unified_websocket", _mock_handle)

    await audio_streaming.websocket_transcribe(ws, token=None)

    assert len(calls) >= 2
    assert all(call["media_id"] == 42 for call in calls)
    assert all(call["whisper_model"] == "stream-live-model" for call in calls)
    assert db.release_count == 1


@pytest.mark.asyncio
async def test_stream_transcribe_skips_persistence_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    ws = DummyWebSocket(query_params={"media_id": "42"})
    calls: list[dict[str, Any]] = []

    monkeypatch.setattr(audio_streaming, "_resolve_media_db_for_user", lambda _user: DummyMediaDB())

    def _upsert(db_instance, media_id: int, transcription: str, whisper_model: str, created_at=None):  # noqa: ANN001
        calls.append(
            {
                "db": db_instance,
                "media_id": media_id,
                "transcription": transcription,
                "whisper_model": whisper_model,
                "created_at": created_at,
            }
        )
        return {"id": len(calls)}

    monkeypatch.setattr(audio_streaming, "upsert_transcript", _upsert)

    async def _mock_handle(
        _websocket,
        config,
        *,
        on_audio_seconds=None,  # noqa: ARG001
        on_heartbeat=None,  # noqa: ARG001
        on_stream_config_resolved=None,
        on_transcript_result=None,
        on_full_transcript=None,
    ):
        if on_stream_config_resolved is not None:
            await on_stream_config_resolved({"type": "config"}, config)
        if on_transcript_result is not None:
            await on_transcript_result({"type": "partial", "text": "hello", "is_final": False}, "")
        if on_full_transcript is not None:
            await on_full_transcript("hello final", False)

    monkeypatch.setattr(audio_streaming, "handle_unified_websocket", _mock_handle)

    await audio_streaming.websocket_transcribe(ws, token=None)

    assert calls == []


@pytest.mark.asyncio
async def test_stream_transcribe_persistence_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    ws = DummyWebSocket(
        query_params={
            "persist_transcript": "1",
            "persist_partial_transcript": "1",
            "media_id": "42",
        }
    )
    db = DummyMediaDB()
    call_count = {"count": 0}

    monkeypatch.setattr(audio_streaming, "_resolve_media_db_for_user", lambda _user: db)

    def _upsert_raises(db_instance, media_id: int, transcription: str, whisper_model: str, created_at=None):  # noqa: ANN001
        _ = (db_instance, media_id, transcription, whisper_model, created_at)
        call_count["count"] += 1
        raise RuntimeError("simulated persistence failure")

    monkeypatch.setattr(audio_streaming, "upsert_transcript", _upsert_raises)

    async def _mock_handle(
        _websocket,
        config,
        *,
        on_audio_seconds=None,  # noqa: ARG001
        on_heartbeat=None,  # noqa: ARG001
        on_stream_config_resolved=None,
        on_transcript_result=None,
        on_full_transcript=None,
    ):
        if on_stream_config_resolved is not None:
            await on_stream_config_resolved({"type": "config"}, config)
        if on_transcript_result is not None:
            await on_transcript_result({"type": "partial", "text": "hello", "is_final": False}, "")
            await on_transcript_result({"type": "transcription", "text": "hello world", "is_final": True}, "hello")
        if on_full_transcript is not None:
            await on_full_transcript("hello world final", False)

    monkeypatch.setattr(audio_streaming, "handle_unified_websocket", _mock_handle)

    await audio_streaming.websocket_transcribe(ws, token=None)

    assert call_count["count"] == 1
    assert any(
        msg.get("type") == "warning" and msg.get("warning_type") == "transcript_persistence_unavailable"
        for msg in ws.sent_json
    )
    assert db.release_count == 1
