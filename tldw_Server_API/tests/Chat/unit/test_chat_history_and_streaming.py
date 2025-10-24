import asyncio
from typing import Any, Dict, Optional, List

import pytest
from unittest.mock import AsyncMock, MagicMock

from tldw_Server_API.app.core.Chat import chat_service
from tldw_Server_API.app.core.Chat.streaming_utils import StreamingResponseHandler


class DummyRequestData:
    def __init__(self, history_message_limit=None, history_message_order=None, save_to_db=False):
        self.character_id = None
        self.history_message_limit = history_message_limit
        self.history_message_order = history_message_order
        self.save_to_db = save_to_db
        self.messages: List[Any] = []


class DummyChatDB:
    def __init__(self, records: List[Dict[str, Any]]):
        self._records = records
        self.client_id = "client"

    def get_messages_for_conversation(self, conversation_id: str, limit: int, offset: int, order: str):
        assert conversation_id == "conv"
        assert offset == 0
        assert order in ("ASC", "DESC")
        ordered = sorted(self._records, key=lambda r: r["timestamp"], reverse=(order == "DESC"))
        return ordered[:limit]

    def get_character_card_by_name(self, name):
        return {"id": 1, "name": name, "system_prompt": "Prompt"}

    def get_character_card_by_id(self, char_id):
        return {"id": char_id, "name": "Assistant", "system_prompt": "Prompt"}

    def get_message_metadata(self, message_id: str):
        return {}

    def get_connection(self):
        raise RuntimeError("not needed")


@pytest.mark.asyncio
async def test_build_context_uses_history_knobs():
    records = [
        {"id": f"msg-{idx}", "sender": "user" if idx % 2 == 0 else "assistant", "content": f"text-{idx}", "timestamp": idx, "images": []}
        for idx in range(10)
    ]
    db = DummyChatDB(records)
    request_data = DummyRequestData(history_message_limit=3, history_message_order="desc")
    request_data.messages = []
    loop = asyncio.get_running_loop()

    class DummyMetrics:
        def track_character_access(self, *args, **kwargs):
            pass

        def track_conversation(self, *args, **kwargs):
            pass

    result = await chat_service.build_context_and_messages(
        chat_db=db,
        request_data=request_data,
        loop=loop,
        metrics=DummyMetrics(),
        default_save_to_db=False,
        final_conversation_id="conv",
        save_message_fn=AsyncMock(),
    )

    history = result[4]
    assert len(history) == 3
    # Expect oldest to newest ordering even when fetching via DESC
    timestamps = [msg_part["content"][0]["text"].split("-")[-1] for msg_part in history if msg_part["content"]]
    assert timestamps == ["7", "8", "9"]


class DummySave:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    async def __call__(self, text: str, tool_calls: Optional[List[Dict[str, Any]]], function_call: Optional[Dict[str, Any]]):
        self.calls.append({
            "text": text,
            "tool_calls": tool_calls,
            "function_call": function_call,
        })


@pytest.mark.asyncio
async def test_streaming_handler_persists_tool_calls():
    handler = StreamingResponseHandler(
        conversation_id="conv",
        model_name="model",
        idle_timeout=30,
        heartbeat_interval=30,
        max_response_size=1024,
    )

    handler._accumulate_tool_calls([
        {
            "index": 0,
            "id": "call",
            "type": "function",
            "function": {"name": "foo", "arguments": "{\\\"a\\\": "},
        }
    ])
    handler._accumulate_tool_calls([
        {
            "index": 0,
            "function": {"arguments": "1\\\"}"},
        }
    ])

    async def chunk_stream():
        yield "data: {\"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}\n\n"
        yield "data: [DONE]\n\n"

    saver = DummySave()
    stream = handler.safe_stream_generator(chunk_stream(), save_callback=saver)
    collected = []
    async for item in stream:
        collected.append(item)
    assert any("Hello" in part for part in collected)
    assert saver.calls
    persisted = saver.calls[0]
    assert persisted["text"] == "Hello"
    assert persisted["tool_calls"] == [
        {
            "id": "call",
            "type": "function",
            "function": {"name": "foo", "arguments": "{\\\"a\\\": 1\\\"}"},
        }
    ]
    assert persisted["function_call"] is None


def test_document_generator_accepts_string_ids(tmp_path):
    from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
    from tldw_Server_API.app.core.Chat.document_generator import DocumentGeneratorService, DocumentType

    db_path = tmp_path / "chacha.db"
    service_db = CharactersRAGDB(db_path=str(db_path), client_id="client")
    generator = DocumentGeneratorService(service_db, user_id="user")

    # Force table initialization
    generator._init_tables()

    # Insert with UUID conversation id
    conv_id = "550e8400-e29b-41d4-a716-446655440000"
    job_id = generator.create_generation_job(conv_id, DocumentType.SUMMARY, provider="openai", model="gpt", prompt_config={})
    generator._save_generated_document(
        conversation_id=conv_id,
        document_type=DocumentType.SUMMARY,
        title="t",
        content="body",
        provider="openai",
        model="gpt",
        generation_time_ms=1,
    )

    docs = generator.get_generated_documents(conversation_id=conv_id)
    assert docs and docs[0]["conversation_id"] == conv_id

    job = generator.get_job_status(job_id)
    assert job is not None
