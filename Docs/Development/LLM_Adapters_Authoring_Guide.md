# Authoring LLM Provider Adapters

This guide explains how to add a new LLM provider adapter that plugs into the Chat adapter registry. Adapters encapsulate provider-specific logic and return OpenAI-compatible responses/streams.

## Directory & Files
- Put adapters under `tldw_Server_API/app/core/LLM_Calls/providers/`
- Recommended file name: `<provider>_adapter.py` (e.g., `openai_adapter.py`)
- Implement the `ChatProvider` interface from `providers/base.py`

## Interface
```python
from tldw_Server_API.app.core.LLM_Calls.providers.base import ChatProvider, apply_tool_choice
from tldw_Server_API.app.core.LLM_Calls.sse import sse_data, sse_done
from tldw_Server_API.app.core.LLM_Calls.streaming import aiter_sse_lines_httpx, iter_sse_lines_requests

class MyProviderAdapter(ChatProvider):
    name = "myprovider"

    def capabilities(self) -> dict:
        return {
            "supports_streaming": True,
            "supports_tools": True,
            "default_timeout_seconds": 60,
            "max_output_tokens_default": 4096,
        }

    def chat(self, request: dict, *, timeout: float | None = None) -> dict:
        # 1) Build provider payload from OpenAI-like request
        # 2) Call the provider (httpx/requests)
        # 3) Normalize JSON to OpenAI-compatible chat.completion
        return {"object": "chat.completion", ...}

    def stream(self, request: dict, *, timeout: float | None = None):
        # 1) Make streaming request
        # 2) Yield normalized SSE frames (use streaming helpers)
        # 3) Do NOT yield [DONE]; caller appends via finalize_stream()
        yield sse_data({"choices": [{"delta": {"content": "..."}}]})

    # Optional async variants for native async clients
    async def achat(self, request: dict, *, timeout: float | None = None) -> dict:
        raise NotImplementedError

    async def astream(self, request: dict, *, timeout: float | None = None):
        raise NotImplementedError
```

## Request Shaping
- Adapters receive an OpenAI-like request dict. Common keys: `model`, `messages`, `stream`, `tools`, `tool_choice`, `temperature`, `top_p`, `max_tokens`, `stop`, `response_format`.
- `response_format.type` supports `text`, `json_object`, and `json_schema`.
- For `json_schema`, requests include `response_format.json_schema = {name, schema, strict?}`. If a provider cannot do `json_schema` natively, the server may downgrade the outbound request to `json_object` and still validate response content against the requested schema server-side.
- Use `apply_tool_choice(payload, tools, tool_choice)` to set `tool_choice` safely only when supported.
- Validation enforces that `tool_choice` requires `tools`; do not rely on adapters to silently ignore missing tools.
- `extra_headers`/`extra_body` are additive overrides; explicit headers/body keys in the request win on conflicts.
- Local providers must not accept request-level `api_url` overrides; base URLs are config-only.
- Do not log raw prompts—log sanitized metadata only.

## Streaming
- Use `iter_sse_lines_requests()` for `requests` streams and `aiter_sse_lines_httpx()` for `httpx` streams to normalize per-line output.
- Do NOT forward provider `[DONE]` frames; the endpoint appends a single final `sse_done()` via `finalize_stream()`.
- Structured output mode may emit additive terminal events (`structured_result` or `structured_error`) before normal stream termination markers. Adapters should only emit provider delta/event data and let chat service own terminal event sequencing.

## Error Mapping
- Wrap provider exceptions with `self.normalize_error(exc)` which maps to project `Chat*Error` types.
- Return or raise these within adapter methods; the endpoint layer maps them to HTTP codes.

## Registration
- Register the adapter with the registry (e.g., in initialization):
```python
from tldw_Server_API.app.core.LLM_Calls.adapter_registry import get_registry
get_registry().register_adapter("myprovider", "tldw_Server_API.app.core.LLM_Calls.providers.myprovider_adapter.MyProviderAdapter")
```

## Testing
- Unit test adapter methods with mocked HTTP clients.
- Verify non-streaming returns OpenAI-compatible JSON.
- Verify streaming yields normalized SSE frames and omits `[DONE]`.
- Ensure error mapping covers authentication, rate limit, bad request, and 5xx cases.

## Style & Conventions
- Follow PEP 8 and use type hints.
- Keep provider adapters small and focused; do not introduce provider-specific branching in common modules.
- Keep config resolution clear (env overrides, base URL, API key); never log secrets.

## Examples
- See TTS adapters under `tldw_Server_API/app/core/TTS/adapters/` for the pattern.
- Reuse `http_client.py` for consistent timeouts, retries, and egress policy when appropriate.

## Async Examples
- Implement async variants when providers offer native async SDKs or when throughput matters:
```python
class MyProviderAdapter(ChatProvider):
    async def achat(self, request: dict, *, timeout: float | None = None) -> dict:
        # Async JSON request via http_client (egress + retries + metrics)
        # Return OpenAI-compatible response
        ...

    async def astream(self, request: dict, *, timeout: float | None = None):
        # Async SSE stream via http_client.astream_sse
        # Yield normalized SSE lines; do not yield [DONE]
        ...
```
- Use `chat_service.perform_chat_api_call_async` for legacy async call sites; the adapter registry handles async routing for orchestrator paths.

## Embeddings Adapters
- For embeddings, implement `EmbeddingsProvider` in `providers/base.py` and return an OpenAI-like shape:
  `{ "data": [{"index": 0, "embedding": [...]}, ...], "model": "...", "object": "list" }`.
- Register in `embeddings_adapter_registry.DEFAULT_ADAPTERS`.
- The enhanced embeddings endpoint can route to adapters when `LLM_EMBEDDINGS_ADAPTERS_ENABLED=1`.
- Optional: support native HTTP behind flags like `LLM_EMBEDDINGS_NATIVE_HTTP_<PROVIDER>` to allow mock-friendly tests.
