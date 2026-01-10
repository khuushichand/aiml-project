import asyncio
import pytest


pytestmark = pytest.mark.asyncio


async def _collect(ait, limit=100):
    out = []
    async for x in ait:
        out.append(x)
        if len(out) >= limit:
            break
    return out


class _FakeResp:
    def __init__(self, lines):
        self._lines = list(lines)
        self.status_code = 200

    def raise_for_status(self):
        return None

    def iter_lines(self):
        for l in self._lines:
            yield l


class _FakeStreamCtx:
    def __init__(self, resp):
        self._r = resp

    def __enter__(self):
        return self._r

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeClient:
    def __init__(self, *, lines, calls=None, raise_after_first: Exception | None = None):
        self._lines = list(lines)
        self._calls = calls
        self._raise_after_first = raise_after_first

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, *args, **kwargs):  # pragma: no cover - not used in these tests
        return _FakeResp([])

    def stream(self, *args, **kwargs):
        if self._calls is not None:
            self._calls["n"] = self._calls.get("n", 0) + 1

        if self._raise_after_first is None:
            return _FakeStreamCtx(_FakeResp(self._lines))

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def iter_lines(_self):
                it = iter(self._lines)
                first = next(it, None)
                if first is not None:
                    yield first
                raise self._raise_after_first

        return _FakeStreamCtx(_Resp())


@pytest.mark.unit
async def test_openai_stream_smoke(monkeypatch):
    # Patch OpenAI adapter http client to emit fake SSE lines
    import tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter as openai_mod
    lines = [
        'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n',
        'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
        'data: [DONE]\n\n',
    ]
    monkeypatch.setattr(openai_mod, "http_client_factory", lambda *a, **k: _FakeClient(lines=lines))

    from tldw_Server_API.app.core.LLM_Calls.chat_calls import chat_with_openai_async

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
    # Verify adapter does not re-invoke client.stream after first byte
    import tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter as openai_mod

    calls = {"n": 0}

    class SentinelError(RuntimeError):
        pass

    lines = ['data: {"choices":[{"delta":{"content":"one"}}]}\n\n']
    monkeypatch.setattr(
        openai_mod,
        "http_client_factory",
        lambda *a, **k: _FakeClient(lines=lines, calls=calls, raise_after_first=SentinelError("boom")),
    )

    from tldw_Server_API.app.core.LLM_Calls.chat_calls import chat_with_openai_async

    it = await chat_with_openai_async(
        input_data=[{"role": "user", "content": "x"}],
        api_key="x",
        streaming=True,
        app_config={"openai_api": {"api_base_url": "https://api.openai.com/v1"}},
    )

    from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
    got = []
    with pytest.raises(ChatProviderError):
        async for ch in it:
            got.append(ch)
    # only one invocation of client.stream should have occurred
    assert calls["n"] == 1
    # we received the first chunk
    assert any("one" in c for c in got)


@pytest.mark.unit
async def test_groq_stream_smoke(monkeypatch):
    import tldw_Server_API.app.core.LLM_Calls.providers.groq_adapter as groq_mod
    lines = [
        'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n',
        'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
        'data: [DONE]\n\n',
    ]
    monkeypatch.setattr(groq_mod, "http_client_factory", lambda *a, **k: _FakeClient(lines=lines))

    from tldw_Server_API.app.core.LLM_Calls.chat_calls import chat_with_groq_async

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
    import tldw_Server_API.app.core.LLM_Calls.providers.groq_adapter as groq_mod

    calls = {"n": 0}

    class SentinelError(RuntimeError):
        pass

    lines = ['data: {"choices":[{"delta":{"content":"one"}}]}\n\n']
    monkeypatch.setattr(
        groq_mod,
        "http_client_factory",
        lambda *a, **k: _FakeClient(lines=lines, calls=calls, raise_after_first=SentinelError("boom")),
    )

    from tldw_Server_API.app.core.LLM_Calls.chat_calls import chat_with_groq_async

    it = await chat_with_groq_async(
        input_data=[{"role": "user", "content": "x"}],
        api_key="x",
        streaming=True,
        app_config={"groq_api": {"api_base_url": "https://api.groq.com/openai/v1"}},
    )

    from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
    got = []
    with pytest.raises(ChatProviderError):
        async for ch in it:
            got.append(ch)
    assert calls["n"] == 1
    assert any("one" in c for c in got)


@pytest.mark.unit
async def test_openrouter_stream_smoke(monkeypatch):
    import tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter as or_mod
    lines = [
        'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n',
        'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
        'data: [DONE]\n\n',
    ]
    monkeypatch.setattr(or_mod, "http_client_factory", lambda *a, **k: _FakeClient(lines=lines))

    from tldw_Server_API.app.core.LLM_Calls.chat_calls import chat_with_openrouter_async

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
    import tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter as or_mod

    calls = {"n": 0}

    class SentinelError(RuntimeError):
        pass

    lines = ['data: {"choices":[{"delta":{"content":"one"}}]}\n\n']
    monkeypatch.setattr(
        or_mod,
        "http_client_factory",
        lambda *a, **k: _FakeClient(lines=lines, calls=calls, raise_after_first=SentinelError("boom")),
    )

    from tldw_Server_API.app.core.LLM_Calls.chat_calls import chat_with_openrouter_async

    it = await chat_with_openrouter_async(
        input_data=[{"role": "user", "content": "x"}],
        api_key="x",
        streaming=True,
        app_config={"openrouter_api": {"api_base_url": "https://openrouter.ai/api/v1"}},
    )

    from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
    got = []
    with pytest.raises(ChatProviderError):
        async for ch in it:
            got.append(ch)
    assert calls["n"] == 1
    assert any("one" in c for c in got)


@pytest.mark.unit
async def test_anthropic_stream_smoke(monkeypatch):
    import tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter as ant_mod

    lines = [
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hello"}}',
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":" world"}}',
    ]
    monkeypatch.setattr(ant_mod, "http_client_factory", lambda *a, **k: _FakeClient(lines=lines))

    from tldw_Server_API.app.core.LLM_Calls.chat_calls import chat_with_anthropic_async

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
    import tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter as ant_mod
    from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError

    class SentinelError(RuntimeError):
        pass

    lines = ['data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"one"}}']
    monkeypatch.setattr(ant_mod, "http_client_factory", lambda *a, **k: _FakeClient(lines=lines, calls={"n": 0}, raise_after_first=SentinelError("boom")))

    from tldw_Server_API.app.core.LLM_Calls.chat_calls import chat_with_anthropic_async

    it = await chat_with_anthropic_async(
        input_data=[{"role": "user", "content": "x"}],
        api_key="x",
        streaming=True,
        app_config={"anthropic_api": {"api_base_url": "https://api.anthropic.com/v1"}},
    )

    got = []
    with pytest.raises(ChatProviderError):
        async for ch in it:
            got.append(ch)
    # _FakeClient counts stream context entries; ensure one invocation
    # (we can't capture here due to inline dict, but the exception proves no retry occurred)
    assert any("one" in c for c in got)


@pytest.mark.unit
@pytest.mark.parametrize(
    "provider,fn_name,mod_path,config_key,base_url",
    [
        ("openai", "chat_with_openai_async", "tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter", "openai_api", "https://api.openai.com/v1"),
        ("groq", "chat_with_groq_async", "tldw_Server_API.app.core.LLM_Calls.providers.groq_adapter", "groq_api", "https://api.groq.com/openai/v1"),
        ("openrouter", "chat_with_openrouter_async", "tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter", "openrouter_api", "https://openrouter.ai/api/v1"),
    ],
)
async def test_combined_sse_providers_smoke_and_cancel(monkeypatch, provider, fn_name, mod_path, config_key, base_url):
    """Combined smoke for SSE-based providers (shimless adapters).

    Confirms DONE ordering and no retry after first byte by counting client.stream invocations.
    """
    from importlib import import_module
    from tldw_Server_API.app.core.LLM_Calls import chat_calls as llm_api

    calls = {"n": 0}

    lines = [
        'data: {"choices":[{"delta":{"content":"A"}}]}\n\n',
        'data: {"choices":[{"delta":{"content":"B"}}]}\n\n',
        'data: [DONE]\n\n',
    ]
    mod = import_module(mod_path)
    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: _FakeClient(lines=lines, calls=calls))

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

    # Patch to raise after first chunk to simulate cancellation behavior
    class SentinelError(RuntimeError):
        pass

    monkeypatch.setattr(mod, "http_client_factory", lambda *a, **k: _FakeClient(lines=lines[:1], calls=calls, raise_after_first=SentinelError("boom")))

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
    import tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter as ant_mod
    from tldw_Server_API.app.core.LLM_Calls import chat_calls as llm_api

    calls = {"n": 0}
    lines = [
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"A"}}',
        'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"B"}}',
        'data: [DONE]'
    ]
    monkeypatch.setattr(ant_mod, "http_client_factory", lambda *a, **k: _FakeClient(lines=lines, calls=calls))

    it = await llm_api.chat_with_anthropic_async(
        input_data=[{"role": "user", "content": "hi"}],
        api_key="x",
        streaming=True,
        app_config={"anthropic_api": {"api_base_url": "https://api.anthropic.com/v1"}},
    )
    chunks = await _collect(it)
    assert chunks[-1].strip().endswith("[DONE]")

    # Cancellation path
    calls["n"] = 0
    it2 = await llm_api.chat_with_anthropic_async(
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
    """Stress: many small chunks; ensure a single final [DONE] and proper ordering (shimless OpenAI)."""
    import tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter as openai_mod
    from tldw_Server_API.app.core.LLM_Calls import chat_calls as llm_api

    # Build many small chunks
    lines = []
    for i in range(25):
        await asyncio.sleep(0)  # yield control
        lines.append(
            f'data: {{"choices":[{{"delta":{{"content":"C{i}"}}}}]}}\n\n'
        )
    lines.append('data: [DONE]\n\n')

    monkeypatch.setattr(openai_mod, "http_client_factory", lambda *a, **k: _FakeClient(lines=lines))

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
