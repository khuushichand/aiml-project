import asyncio

import pytest

from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoint


def test_queue_estimate_sanitizes_base64_payload():


    payload = "data:image/png;base64," + ("a" * 400)
    raw = (
        "{\"messages\":[{\"role\":\"user\",\"content\":[{\"type\":\"image_url\",\"image_url\":{\"url\":\""
        + payload
        + "\"}}]}]}"
    )

    raw_est = max(1, len(raw) // 4)
    sanitized = chat_endpoint._sanitize_json_for_rate_limit(raw)
    sanitized_est = max(1, len(sanitized) // 4)
    helper_est = chat_endpoint._estimate_tokens_for_queue(raw)

    assert helper_est == sanitized_est
    assert sanitized_est < raw_est


@pytest.mark.asyncio
async def test_schedule_audit_background_task_observes_exception(monkeypatch):
    captured: list[tuple[str, tuple]] = []

    class _DummyLogger:
        def debug(self, message, *args):
            captured.append((message, args))

    monkeypatch.setattr(chat_endpoint, "logger", _DummyLogger())

    async def _boom():
        raise RuntimeError("boom")

    task = chat_endpoint._schedule_audit_background_task(_boom(), task_name="chat.endpoint.audit")
    assert task is not None
    await asyncio.gather(task, return_exceptions=True)
    await asyncio.sleep(0)

    assert any("chat.endpoint.audit" in str(args) for _, args in captured)


@pytest.mark.asyncio
async def test_schedule_audit_background_task_cancelled_is_silent(monkeypatch):
    captured: list[tuple[str, tuple]] = []

    class _DummyLogger:
        def debug(self, message, *args):
            captured.append((message, args))

    monkeypatch.setattr(chat_endpoint, "logger", _DummyLogger())

    gate = asyncio.Event()

    async def _slow():
        await gate.wait()

    task = chat_endpoint._schedule_audit_background_task(_slow(), task_name="chat.endpoint.cancel")
    assert task is not None
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await asyncio.sleep(0)

    assert not any("chat.endpoint.cancel" in str(args) and "failed" in msg for msg, args in captured)


@pytest.mark.asyncio
async def test_process_content_for_db_sync_large_image_path_handles_processor_rejection(monkeypatch):
    class _RejectingProcessor:
        async def process_image_url(self, _url: str, _max_size_bytes: int):
            return False, None, "text/plain", "Unsupported image MIME type: text/plain"

    monkeypatch.setattr(chat_endpoint, "get_image_processor", lambda: _RejectingProcessor())

    large_payload = "A" * 100001
    content = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:text/plain;base64,{large_payload}"},
        }
    ]

    text_parts, images = await chat_endpoint._process_content_for_db_sync(content, "conv_test")

    assert images == []
    assert any(
        part.startswith("<Image failed: Unsupported image MIME type: text/plain>")
        for part in text_parts
    )
