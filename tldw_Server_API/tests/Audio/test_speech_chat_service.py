import base64
import io
from typing import Any, Dict

import numpy as np
import pytest
import soundfile as sf

from tldw_Server_API.app.api.v1.schemas.audio_schemas import (
    SpeechChatRequest,
    SpeechChatLLMConfig,
)
from tldw_Server_API.app.core.Streaming.speech_chat_service import run_speech_chat_turn


class _StubUser:
    def __init__(self, user_id: int = 1):
        self.id = user_id


class _StubChatDB:
    def __init__(self, client_id: str = "test-client"):
        self.client_id = client_id
        self._conversations: Dict[str, Dict[str, Any]] = {}
        self._messages: Dict[str, Dict[str, Any]] = {}

    # Minimal subset used by helpers
    def add_conversation(self, conv_data: Dict[str, Any]) -> str:
        cid = conv_data.get("id") or "conv-1"
        self._conversations[cid] = conv_data
        return cid

    def get_conversation_by_id(self, conversation_id: str) -> Dict[str, Any] | None:
        return self._conversations.get(conversation_id)

    def add_message(self, msg_data: Dict[str, Any]) -> str:
        mid = msg_data.get("id") or f"msg-{len(self._messages) + 1}"
        self._messages[mid] = msg_data
        return mid

    def get_messages_for_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
        order_by_timestamp: str = "ASC",
        include_deleted: bool = False,
    ):
        # Return existing messages for the conversation in insertion order
        return [
            m for m in self._messages.values() if m.get("conversation_id") == conversation_id
        ][offset : offset + limit]


class _StubTTSService:
    async def generate_speech(self, request, provider=None, fallback=True):
        # Return a single tiny chunk of bytes
        yield b"stub-audio"


def _encode_silence_base64(duration_sec: float = 0.1, sr: int = 16000) -> str:
    buf = io.BytesIO()
    data = np.zeros(int(sr * duration_sec), dtype=np.float32)
    sf.write(buf, data, sr, format="WAV")
    return base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.mark.asyncio
async def test_run_speech_chat_turn_happy_path(monkeypatch):
    # Stub STT to return fixed transcript
    from tldw_Server_API.app.core.Streaming import speech_chat_service

    async def _fake_transcribe_audio(**kwargs):
        return "hello from audio"

    # transcribe_audio is synchronous in the module; patch to simple function
    monkeypatch.setattr(
        speech_chat_service, "transcribe_audio", lambda *a, **k: "hello from audio"
    )

    # Stub character/conv helpers to avoid touching real DB schema
    async def _fake_get_or_create_character_context(db, character_id, loop):
        return {"id": 1, "name": "Test Character", "system_prompt": "You are helpful."}, 1

    async def _fake_get_or_create_conversation(
        db, conversation_id, character_id, character_name, client_id, loop
    ):
        return conversation_id or "conv-1", conversation_id is None

    async def _fake_load_history(db, conversation_id, character_card, limit=20, loop=None):
        return []

    monkeypatch.setattr(
        speech_chat_service,
        "get_or_create_character_context",
        _fake_get_or_create_character_context,
    )
    monkeypatch.setattr(
        speech_chat_service,
        "get_or_create_conversation",
        _fake_get_or_create_conversation,
    )
    monkeypatch.setattr(
        speech_chat_service,
        "load_conversation_history",
        _fake_load_history,
    )

    # Stub LLM orchestrator
    async def _fake_chat_api_call_async(**kwargs):
        return {
            "choices": [
                {"message": {"role": "assistant", "content": "stub assistant reply"}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    monkeypatch.setattr(speech_chat_service, "chat_api_call_async", _fake_chat_api_call_async)

    # Prepare request
    req = SpeechChatRequest(
        session_id=None,
        input_audio=_encode_silence_base64(),
        input_audio_format="wav",
        llm_config=SpeechChatLLMConfig(model="gpt-4o-mini", api_provider="openai"),
    )
    user = _StubUser()
    db = _StubChatDB()
    tts = _StubTTSService()

    resp = await run_speech_chat_turn(
        request_data=req,
        current_user=user,
        chat_db=db,
        tts_service=tts,
    )

    assert resp.session_id
    assert resp.user_transcript == "hello from audio"
    assert resp.assistant_text == "stub assistant reply"


@pytest.mark.asyncio
async def test_run_speech_chat_turn_stt_error_sentinel_raises(monkeypatch):
    # Ensure STT error sentinel strings from transcribe_audio are mapped to HTTP 500
    from tldw_Server_API.app.core.Streaming import speech_chat_service

    # Patch transcribe_audio to return an error sentinel that should be detected
    monkeypatch.setattr(
        speech_chat_service,
        "transcribe_audio",
        lambda *a, **k: "Error in transcription: simulated failure",
    )

    # Reuse the same DB/LLM/character stubs from the happy-path test
    async def _fake_get_or_create_character_context(db, character_id, loop):
        return {"id": 1, "name": "Test Character", "system_prompt": "You are helpful."}, 1

    async def _fake_get_or_create_conversation(
        db, conversation_id, character_id, character_name, client_id, loop
    ):
        return conversation_id or "conv-1", conversation_id is None

    async def _fake_load_history(db, conversation_id, character_card, limit=20, loop=None):
        return []

    monkeypatch.setattr(
        speech_chat_service,
        "get_or_create_character_context",
        _fake_get_or_create_character_context,
    )
    monkeypatch.setattr(
        speech_chat_service,
        "get_or_create_conversation",
        _fake_get_or_create_conversation,
    )
    monkeypatch.setattr(
        speech_chat_service,
        "load_conversation_history",
        _fake_load_history,
    )

    async def _fake_chat_api_call_async(**kwargs):
        return {
            "choices": [
                {"message": {"role": "assistant", "content": "stub assistant reply"}}
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    monkeypatch.setattr(speech_chat_service, "chat_api_call_async", _fake_chat_api_call_async)

    req = SpeechChatRequest(
        session_id=None,
        input_audio=_encode_silence_base64(),
        input_audio_format="wav",
        llm_config=SpeechChatLLMConfig(model="gpt-4o-mini", api_provider="openai"),
    )
    user = _StubUser()
    db = _StubChatDB()
    tts = _StubTTSService()

    with pytest.raises(HTTPException) as exc_info:
        await run_speech_chat_turn(
            request_data=req,
            current_user=user,
            chat_db=db,
            tts_service=tts,
        )

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert resp.output_audio
    assert resp.output_audio_mime_type.startswith("audio/")
    assert resp.timing.stt_ms >= 0.0
    assert resp.timing.llm_ms >= 0.0
    assert resp.timing.tts_ms >= 0.0
    assert resp.token_usage is not None
    assert resp.token_usage.total_tokens == 15
