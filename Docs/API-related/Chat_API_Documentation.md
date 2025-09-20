# Chat API Documentation

## Overview
- Endpoint: `POST /api/v1/chat/completions` (OpenAI-compatible)
- Purpose: Route chat requests to configured LLM providers with optional streaming and persistence.
- Scope note: Chat Dictionaries and Document Generator are part of Chatbook features, not the core Chat endpoint. See `Docs/API-related/Chatbook_Features_API_Documentation.md`.

## Authentication
- Single-user: `X-API-KEY: <key>`
- Multi-user: `Authorization: Bearer <JWT>`
- If authentication is required and missing/invalid, the endpoint returns `401`.

## Request
Follows OpenAI-style chat payload with extensions.

Key fields:
- `model` (string): Target model. May be prefixed as `provider/model` (e.g., `anthropic/claude-3-5-sonnet`).
- `messages` (array): Conversation turns. Supports roles `system`, `user`, `assistant`, `tool`.
  - User message `content` may be a string or a list of parts: text and base64 data URI `image_url`.
- `stream` (bool): If true, returns Server-Sent Events (SSE) for streaming.
- `api_provider` (string, optional): Overrides provider selection. Server default used if omitted.
- `prompt_template_name` (string, optional): Apply a named prompt template (alphanumeric, `_`, `-`).
- Common sampling params (provider-dependent): `temperature`, `top_p`, `max_tokens`, `n`, `frequency_penalty`, `presence_penalty`, `logprobs`, `top_logprobs`, `logit_bias`.
- Tools: `tools`, `tool_choice` (provider-dependent tool/function calling).
- `response_format`: `{ "type": "text" | "json_object" }` (provider-dependent).
- Chat extensions: `character_id`, `conversation_id` (context hooks), `save_to_db` (persistence toggle).

Minimal example (non‑streaming):
```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role":"user","content":"Hello!"}]
  }'
```

Streaming example (SSE):
```bash
curl -N -X POST http://127.0.0.1:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
    "model": "anthropic/claude-3-5-sonnet",
    "messages": [{"role":"user","content":"Stream this response."}],
    "stream": true
  }'
```

## Provider Selection
- If `model` includes a provider prefix (`provider/model`), that provider is used unless `api_provider` is explicitly set.
- If no provider is specified, the server uses `DEFAULT_LLM_PROVIDER`.
- Provider API keys are sourced from environment (`.env`) or `tldw_Server_API/Config_Files/config.txt`.
 - When provider fallback is enabled in server config, the server may automatically select a healthy provider if the requested one is unavailable.

## Streaming Behavior
- Media type: `text/event-stream`.
- Heartbeats: Sent periodically (default 30s) to keep connections alive.
- Idle timeout: Default 300s of inactivity ends the stream with an error event.
- Completion: Upstream `[DONE]` or natural stream end closes the SSE.

Event shapes (examples):
```
event: stream_start
data: {"conversation_id":"<id>","model":"<model>","timestamp":"<iso>"}

data: {"choices":[{"delta":{"content":"Hello"}}]}

: heartbeat 2025-01-01T00:00:30Z

event: stream_end
data: {"conversation_id":"<id>","success":true,"timestamp":"<iso>"}
```

Errors during streaming are emitted as SSE `data:` frames with an `{"error": {"message": "..."}}` payload.

Note: Stream chunks follow OpenAI-style `choices[].delta.content` for maximum client compatibility.

## Responses
- Non-streaming JSON includes the standard OpenAI `choices` structure and a `tldw_conversation_id` field to help clients track state.

## Persistence
- Default behavior is ephemeral (no DB writes).
- Per-request opt‑in: set `"save_to_db": true` to persist conversation/messages.
- Server default can be toggled without client changes:
  - Env: `CHAT_SAVE_DEFAULT=true` (highest precedence) or `DEFAULT_CHAT_SAVE=true`
  - Config file (`Config_Files/config.txt`): `[Chat-Module] chat_save_default = True` (or `default_save_to_db = True`)
  - Fallback legacy default: `[Auto-Save] save_character_chats`
- Stored content includes text and validated/decoded images. Invalid images are saved as placeholders to preserve turn continuity.

## Validation & Limits
- Images: Accepts `image/png`, `image/jpeg`, `image/webp`. Base64 data URI validation; default max base64 payload ≈ 3MB.
- Messages: Default max messages per request: 1000.
- Text: Default per‑message text limit: 400,000 characters.
- Images per request: Default max: 10.
- Oversized or invalid payloads return `400`/`413` with details.

## Errors
- `400` Invalid request (schema, limits, bad params)
- `401` Missing/invalid authentication
- `404` Resource not found (e.g., invalid character reference)
- `409` Conflict while persisting
- `429` Rate limit exceeded
- `502`/`504` Upstream provider error/timeout
- `503` Service/configuration issue (e.g., missing API key)

## Rate Limiting
Configurable under `[Chat-Module]` in `Config_Files/config.txt`:
- `rate_limit_per_minute`
- `rate_limit_per_user_per_minute`
- `rate_limit_per_conversation_per_minute`
- `rate_limit_tokens_per_minute`
When exceeded, the endpoint returns `429`.

## Observability
- Metrics: Tracks request size, LLM latency, streaming chunks/heartbeats, DB transactions, and image processing.
- Audit: When enabled, logs API request metadata (user_id, request_id, model/provider, streaming) via the unified audit service.

## WebUI
- Location: `/webui` → Chat Completions tab.
- Persistence: “Save to DB” checkbox, default pulled from `/webui/config.json` reflecting server config.
- Providers/models: Dropdowns reflect configured providers and models.

## Related Documentation
- Chatbook features (Dictionaries, Document Generator, Import/Export): `Docs/API-related/Chatbook_Features_API_Documentation.md`
- Character chat sessions API: `Docs/CHARACTER_CHAT_API_DOCUMENTATION.md`

## Providers API
Supporting endpoints for discovering providers and models:
- `GET /api/v1/llm/providers` – Configured providers and models
- `GET /api/v1/llm/providers/{provider}` – Details for a specific provider
- `GET /api/v1/llm/models` – Flat list of `<provider>/<model>` values
- `GET /api/v1/llm/models/metadata` – Flattened model capability metadata
