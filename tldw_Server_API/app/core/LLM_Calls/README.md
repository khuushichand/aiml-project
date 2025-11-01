LLM Calls Module

Purpose
- Unified client functions for calling commercial and local LLM providers.
- Normalizes requests and responses to an OpenAI-compatible shape where possible.
- Provides consistent error mapping via ChatAPIError subclasses for clean API responses.

Key Files
- `tldw_Server_API/app/core/LLM_Calls/LLM_API_Calls.py` - commercial providers
- `tldw_Server_API/app/core/LLM_Calls/LLM_API_Calls_Local.py` - local/OpenAI-compatible servers + native local engines
- `tldw_Server_API/app/core/LLM_Calls/huggingface_api.py` - HF async client for GGUF discovery/download
- `tldw_Server_API/app/core/LLM_Calls/Local_Summarization_Lib.py` - local summarization helpers
- `tldw_Server_API/app/core/LLM_Calls/Summarization_General_Lib.py` - summarization utilities

Supported Providers (commercial)
- OpenAI, Anthropic, Cohere, DeepSeek, Google (Gemini), Qwen, Groq, HuggingFace (OpenAI-compatible endpoints),
  Mistral, OpenRouter, Moonshot, Z.AI, (Bedrock via OpenAI-compatible endpoint)

Common Usage
- All chat functions accept `input_data` as OpenAI-style messages `[{'role': 'user'|'assistant'|'system', 'content': ...}]`.
- Where supported, `system_message` is prepended as a `system` role message when provided.
- Most functions support `streaming=True|False`. Streaming returns an iterator of SSE lines or normalized deltas.
- Errors are raised as `ChatAPIError` subclasses from `tldw_Server_API.app.core.Chat.Chat_Deps`.

Streaming Semantics
- Streaming responses are normalized to SSE. Expect lines prefixed with `data: ` and terminated by a blank line.
- Some providers yield raw `data:` lines (already SSE-compatible); others are converted to OpenAI-like chunks.

Configuration
- Provider config is loaded via `load_and_log_configs()` and uses sections like `openai_api`, `anthropic_api`, etc.
- Typical keys: `api_key`, `model`, `api_base_url`, `temperature`, `top_p`, `max_tokens`, `streaming`,
  `api_timeout`, `api_retries`, `api_retry_delay`.
- Environment variables can override base URLs for testing; see usage of e.g. `OPENAI_API_BASE_URL`.

Example (OpenAI)
```python
from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import chat_with_openai

resp = chat_with_openai(
    input_data=[{"role":"user","content":"Hello"}],
    model="gpt-4o-mini",
)
print(resp["choices"][0]["message"]["content"])
```

Error Handling
- Provider errors map to:
  - `ChatAuthenticationError` (401/403)
  - `ChatBadRequestError` (400/404/422)
  - `ChatRateLimitError` (429)
  - `ChatProviderError` (5xx + network issues)
  - `ChatAPIError` (fallback)

Security
- Secrets are never logged. Some legacy logs used masked fragments; these have been replaced with generic messages.
- Do not add logging of API keys or request bodies that include sensitive content.

Testing
- See `tldw_Server_API/tests/LLM_Calls/test_llm_providers.py` for provider tests and
  `tests/Character_Chat/test_complete_v2_streaming_e2e_mock.py` for streaming normalization.

Adding a Provider
- Pattern to follow (see `chat_with_openai`):
  - Resolve config (api key, model, retry/timeout) with function arguments overriding config.
  - Build OpenAI-style `messages` payload (prepend `system_message` as needed).
  - Support `streaming` and non-streaming; normalize streaming to SSE.
  - Map HTTP errors to ChatAPIError subclasses.
  - Keep logs high-level; never log secrets; optionally log payload keys (not full content).

Current Improvement Backlog (low-risk, incremental)
- Reduce duplication by extracting a small request helper for retries and streaming.
- Standardize SSE normalization across providers (identical end format).
- Add per-provider docstrings summarizing supported parameters and differences.
- Expand unit tests for remaining providers (DeepSeek, Google, Groq, etc.).
- Convert synchronous HTTP calls to `httpx` async where endpoints support non-blocking usage.

Strict OpenAI-Compatible Mode (Local Providers)
- Some OpenAI-compatible local servers reject unknown/non-standard fields (e.g., `top_k`).
- A strict filtering option is available per local provider to drop non-standard keys from the payload.
  - Config key: `strict_openai_compat` (boolean)
  - When `true`, only standard OpenAI Chat Completions keys are sent:
    `messages, model, temperature, top_p, max_tokens, n, stop, presence_penalty, frequency_penalty, logit_bias,
     seed, response_format, tools, tool_choice, logprobs, top_logprobs, user, stream`.
- Supported sections:
  - `local_llm`, `llama_api`, `ooba_api`, `tabby_api`, `vllm_api`, `aphrodite_api`, `ollama_api`.
- Environment variable for `local_llm`:
  - `LOCAL_LLM_STRICT_OPENAI_COMPAT=1|true|yes|on`

Example (local_llm excerpt):
```ini
[Local-API]
; ...
strict_openai_compat = true
```

See tests for usage examples:
- `tests/LLM_Calls/test_local_llm_strict_filter.py`
- `tests/LLM_Calls/test_vllm_strict_filter.py`
