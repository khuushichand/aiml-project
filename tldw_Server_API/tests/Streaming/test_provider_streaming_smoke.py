import asyncio
import types
import pytest


pytestmark = pytest.mark.asyncio


def _mk_event(data: str):
    return types.SimpleNamespace(event="message", data=data, id=None, retry=None)


async def _collect(ait, limit=100):
    out = []
    async for x in ait:
        out.append(x)
        if len(out) >= limit:
            break
    return out


@pytest.mark.unit
async def test_openai_stream_smoke(monkeypatch):
    # Patch provider stream to a simple sequence of SSE events
    from tldw_Server_API.app.core.LLM_Calls import streaming as streaming_mod

    async def fake_astream_sse(url: str, method: str = "GET", **kwargs):  # noqa: ARG001
        yield _mk_event("data: {\"choices\":[{\"delta\":{\"content\":\"hello\"}}]}")
        yield _mk_event("data: {\"choices\":[{\"delta\":{\"content\":\" world\"}}]}")

    monkeypatch.setattr(streaming_mod, "astream_sse", fake_astream_sse)

    from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_openai_async

    it = await chat_with_openai_async(
        input_data=[{"role": "user", "content": "hi"}],
        api_key="x",
        streaming=True,
        app_config={"openai_api": {"api_base_url": "https://api.openai.com/v1"}},
    )
    chunks = await _collect(it)
    assert chunks[-1].strip() == "data: [DONE]"
    assert "hello" in "".join(chunks)


@pytest.mark.unit
async def test_openai_stream_no_retry_after_first_byte(monkeypatch):
    # Verify adapter does not re-invoke stream after first byte
    from tldw_Server_API.app.core.LLM_Calls import streaming as streaming_mod

    calls = {"n": 0}

    class SentinelError(RuntimeError):
        pass

    async def fake_astream_sse(url: str, method: str = "GET", **kwargs):  # noqa: ARG001
        calls["n"] += 1
        yield _mk_event("data: {\"choices\":[{\"delta\":{\"content\":\"one\"}}]}")
        raise SentinelError("boom")

    monkeypatch.setattr(streaming_mod, "astream_sse", fake_astream_sse)

    from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_openai_async

    it = await chat_with_openai_async(
        input_data=[{"role": "user", "content": "x"}],
        api_key="x",
        streaming=True,
        app_config={"openai_api": {"api_base_url": "https://api.openai.com/v1"}},
    )

    got = []
    with pytest.raises(SentinelError):
        async for ch in it:
            got.append(ch)
    # only one invocation of astream_sse should have occurred
    assert calls["n"] == 1
    # we received the first chunk
    assert any("one" in c for c in got)


@pytest.mark.unit
async def test_groq_stream_smoke(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import streaming as streaming_mod

    async def fake_astream_sse(url: str, method: str = "GET", **kwargs):  # noqa: ARG001
        yield _mk_event("data: {\"choices\":[{\"delta\":{\"content\":\"hello\"}}]}")
        yield _mk_event("data: {\"choices\":[{\"delta\":{\"content\":\" world\"}}]}")

    monkeypatch.setattr(streaming_mod, "astream_sse", fake_astream_sse)

    from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_groq_async

    it = await chat_with_groq_async(
        input_data=[{"role": "user", "content": "hi"}],
        api_key="x",
        streaming=True,
        app_config={"groq_api": {"api_base_url": "https://api.groq.com/openai/v1"}},
    )
    chunks = await _collect(it)
    assert chunks[-1].strip() == "data: [DONE]"
    assert "hello" in "".join(chunks)


@pytest.mark.unit
async def test_groq_stream_no_retry_after_first_byte(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import streaming as streaming_mod

    calls = {"n": 0}

    class SentinelError(RuntimeError):
        pass

    async def fake_astream_sse(url: str, method: str = "GET", **kwargs):  # noqa: ARG001
        calls["n"] += 1
        yield _mk_event("data: {\"choices\":[{\"delta\":{\"content\":\"one\"}}]}")
        raise SentinelError("boom")

    monkeypatch.setattr(streaming_mod, "astream_sse", fake_astream_sse)

    from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_groq_async

    it = await chat_with_groq_async(
        input_data=[{"role": "user", "content": "x"}],
        api_key="x",
        streaming=True,
        app_config={"groq_api": {"api_base_url": "https://api.groq.com/openai/v1"}},
    )

    got = []
    with pytest.raises(SentinelError):
        async for ch in it:
            got.append(ch)
    assert calls["n"] == 1
    assert any("one" in c for c in got)


@pytest.mark.unit
async def test_openrouter_stream_smoke(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import streaming as streaming_mod

    async def fake_astream_sse(url: str, method: str = "GET", **kwargs):  # noqa: ARG001
        yield _mk_event("data: {\"choices\":[{\"delta\":{\"content\":\"hello\"}}]}")
        yield _mk_event("data: {\"choices\":[{\"delta\":{\"content\":\" world\"}}]}")

    monkeypatch.setattr(streaming_mod, "astream_sse", fake_astream_sse)

    from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_openrouter_async

    it = await chat_with_openrouter_async(
        input_data=[{"role": "user", "content": "hi"}],
        api_key="x",
        streaming=True,
        app_config={"openrouter_api": {"api_base_url": "https://openrouter.ai/api/v1"}},
    )
    chunks = await _collect(it)
    assert chunks[-1].strip() == "data: [DONE]"
    assert "hello" in "".join(chunks)


@pytest.mark.unit
async def test_openrouter_stream_no_retry_after_first_byte(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import streaming as streaming_mod

    calls = {"n": 0}

    class SentinelError(RuntimeError):
        pass

    async def fake_astream_sse(url: str, method: str = "GET", **kwargs):  # noqa: ARG001
        calls["n"] += 1
        yield _mk_event("data: {\"choices\":[{\"delta\":{\"content\":\"one\"}}]}")
        raise SentinelError("boom")

    monkeypatch.setattr(streaming_mod, "astream_sse", fake_astream_sse)

    from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_openrouter_async

    it = await chat_with_openrouter_async(
        input_data=[{"role": "user", "content": "x"}],
        api_key="x",
        streaming=True,
        app_config={"openrouter_api": {"api_base_url": "https://openrouter.ai/api/v1"}},
    )

    got = []
    with pytest.raises(SentinelError):
        async for ch in it:
            got.append(ch)
    assert calls["n"] == 1
    assert any("one" in c for c in got)


@pytest.mark.unit
async def test_anthropic_stream_smoke(monkeypatch):
    # Patch create_async_client to return a stub streaming response
    from tldw_Server_API.app.core import LLM_Calls as llm_mod

    class FakeResp:
        async def aiter_lines(self):
            yield "data: {\"type\": \"content_block_delta\", \"delta\": {\"type\": \"text_delta\", \"text\": \"hello\"}}"
            yield "data: {\"type\": \"content_block_delta\", \"delta\": {\"type\": \"text_delta\", \"text\": \" world\"}}"
        def raise_for_status(self):
            return None

    class FakeCtx:
        async def __aenter__(self):
            return FakeResp()

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return False

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return False

        def stream(self, method, url, headers=None, json=None):  # noqa: ARG002
            return FakeCtx()

    calls = {"n": 0}

    def fake_create_async_client(*args, **kwargs):  # noqa: ARG002
        calls["n"] += 1
        return FakeClient()

    monkeypatch.setattr(llm_mod.LLM_API_Calls, "create_async_client", fake_create_async_client)

    from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_anthropic_async

    it = await chat_with_anthropic_async(
        input_data=[{"role": "user", "content": "hi"}],
        api_key="x",
        streaming=True,
        app_config={"anthropic_api": {"api_base_url": "https://api.anthropic.com/v1"}},
    )
    chunks = await _collect(it)
    assert chunks[-1].strip() == "data: [DONE]"
    assert "hello" in "".join(chunks)


@pytest.mark.unit
async def test_anthropic_stream_no_retry_after_first_byte(monkeypatch):
    from tldw_Server_API.app.core import LLM_Calls as llm_mod

    class SentinelError(RuntimeError):
        pass

    class FakeResp:
        async def aiter_lines(self):
            yield "data: {\"type\": \"content_block_delta\", \"delta\": {\"type\": \"text_delta\", \"text\": \"one\"}}"
            raise SentinelError("boom")
        def raise_for_status(self):
            return None

    class FakeCtx:
        async def __aenter__(self):
            return FakeResp()

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return False

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return False

        def stream(self, method, url, headers=None, json=None):  # noqa: ARG002
            return FakeCtx()

    calls = {"n": 0}

    def fake_create_async_client(*args, **kwargs):  # noqa: ARG002
        calls["n"] += 1
        return FakeClient()

    monkeypatch.setattr(llm_mod.LLM_API_Calls, "create_async_client", fake_create_async_client)

    from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_anthropic_async

    it = await chat_with_anthropic_async(
        input_data=[{"role": "user", "content": "x"}],
        api_key="x",
        streaming=True,
        app_config={"anthropic_api": {"api_base_url": "https://api.anthropic.com/v1"}},
    )

    got = []
    with pytest.raises(SentinelError):
        async for ch in it:
            got.append(ch)
    # only a single create_async_client invocation
    assert calls["n"] == 1
    assert any("one" in c for c in got)


@pytest.mark.unit
@pytest.mark.parametrize(
    "provider,fn_name,config_key,base_url",
    [
        ("openai", "chat_with_openai_async", "openai_api", "https://api.openai.com/v1"),
        ("groq", "chat_with_groq_async", "groq_api", "https://api.groq.com/openai/v1"),
        ("openrouter", "chat_with_openrouter_async", "openrouter_api", "https://openrouter.ai/api/v1"),
    ],
)
async def test_combined_sse_providers_smoke_and_cancel(monkeypatch, provider, fn_name, config_key, base_url):
    """Combined smoke for SSE-based providers: DONE ordering and cancellation propagation.

    - Confirms we end with [DONE]
    - Confirms cancelling the consumer after first chunk does not re-invoke the stream (no retry after first byte)
    """
    from tldw_Server_API.app.core.LLM_Calls import streaming as streaming_mod
    from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as llm_api

    calls = {"n": 0}

    async def fake_astream_sse(url: str, method: str = "GET", **kwargs):  # noqa: ARG001
        calls["n"] += 1
        # One normal event
        yield _mk_event("data: {\"choices\":[{\"delta\":{\"content\":\"A\"}}]}")
        # Simulate small delay before next
        await asyncio.sleep(0.01)
        yield _mk_event("data: {\"choices\":[{\"delta\":{\"content\":\"B\"}}]}")

    monkeypatch.setattr(streaming_mod, "astream_sse", fake_astream_sse)

    chat_fn = getattr(llm_api, fn_name)
    it = await chat_fn(
        input_data=[{"role": "user", "content": "hi"}],
        api_key="x",
        streaming=True,
        app_config={config_key: {"api_base_url": base_url}},
    )
    # Smoke path: collect and ensure DONE is last
    chunks = await _collect(it)
    assert chunks[-1].strip().endswith("[DONE]")

    # Cancellation path: cancel after first chunk and ensure no second invocation
    calls["n"] = 0

    it2 = await chat_fn(
        input_data=[{"role": "user", "content": "hi"}],
        api_key="x",
        streaming=True,
        app_config={config_key: {"api_base_url": base_url}},
    )

    async def consumer():
        got_one = False
        async for ch in it2:
            if not got_one:
                got_one = True
                raise asyncio.CancelledError

    task = asyncio.create_task(consumer())
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls["n"] == 1


@pytest.mark.unit
async def test_combined_anthropic_smoke_and_cancel(monkeypatch):
    """Anthropic combined smoke: DONE ordering and cancellation propagation, no retry after first byte."""
    from tldw_Server_API.app.core import LLM_Calls as llm_mod

    class FakeResp:
        async def aiter_lines(self):
            yield "data: {\"type\": \"content_block_delta\", \"delta\": {\"type\": \"text_delta\", \"text\": \"A\"}}"
            await asyncio.sleep(0.01)
            yield "data: {\"type\": \"content_block_delta\", \"delta\": {\"type\": \"text_delta\", \"text\": \"B\"}}"
        def raise_for_status(self):
            return None

    class FakeCtx:
        async def __aenter__(self):
            return FakeResp()
        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return False

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ARG002
            return False

        def stream(self, method, url, headers=None, json=None):  # noqa: ARG002
            return FakeCtx()

    calls = {"n": 0}

    def fake_create_async_client(*args, **kwargs):  # noqa: ARG002
        calls["n"] += 1
        return FakeClient()

    monkeypatch.setattr(llm_mod.LLM_API_Calls, "create_async_client", fake_create_async_client)
    from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_anthropic_async

    it = await chat_with_anthropic_async(
        input_data=[{"role": "user", "content": "hi"}],
        api_key="x",
        streaming=True,
        app_config={"anthropic_api": {"api_base_url": "https://api.anthropic.com/v1"}},
    )
    chunks = await _collect(it)
    assert chunks[-1].strip().endswith("[DONE]")

    # Cancellation path
    calls["n"] = 0
    it2 = await chat_with_anthropic_async(
        input_data=[{"role": "user", "content": "hi"}],
        api_key="x",
        streaming=True,
        app_config={"anthropic_api": {"api_base_url": "https://api.anthropic.com/v1"}},
    )

    async def consumer():
        got_one = False
        async for ch in it2:
            if not got_one:
                got_one = True
                raise asyncio.CancelledError

    task = asyncio.create_task(consumer())
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls["n"] == 1


@pytest.mark.unit
async def test_multi_chunk_done_ordering_under_load(monkeypatch):
    """Stress: many small chunks; ensure a single final [DONE] and proper ordering."""
    from tldw_Server_API.app.core.LLM_Calls import streaming as streaming_mod
    from tldw_Server_API.app.core.LLM_Calls import LLM_API_Calls as llm_api

    async def fake_astream_sse(url: str, method: str = "GET", **kwargs):  # noqa: ARG001
        # Emit many small chunks with tiny delays
        for i in range(25):
            await asyncio.sleep(0.001)
            yield _mk_event(
                f"data: {{\"choices\":[{{\"delta\":{{\"content\":\"C{i}\"}}}}]}}"
            )

    monkeypatch.setattr(streaming_mod, "astream_sse", fake_astream_sse)

    it = await llm_api.chat_with_openai_async(
        input_data=[{"role": "user", "content": "hi"}],
        api_key="x",
        streaming=True,
        app_config={"openai_api": {"api_base_url": "https://api.openai.com/v1"}},
    )
    chunks = await _collect(it, limit=1000)
    text = "".join(chunks)
    assert text.strip().endswith("[DONE]")
    # Ensure [DONE] appears exactly once at the end
    assert text.count("[DONE]") == 1
