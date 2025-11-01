# Chat API Documentation

## Overview
- Base path: `/api/v1`
- Endpoint: `POST /api/v1/chat/completions` (OpenAI-compatible)
- Purpose: Route chat requests to configured LLM providers with optional streaming and persistence.
- Scope note: Chat Dictionaries and the Document Generator are implemented as sub-routes under `/api/v1/chat`, but documented in Chatbook features. See `./Chatbook_Features_API_Documentation.md`.
- OpenAPI tags: `chat`, `chat-dictionaries`, `chat-documents`

## Authentication
- Single-user: `X-API-KEY: <key>`
- Multi-user: `Authorization: Bearer <JWT>`
- Backward-compatible header alias: `Token: Bearer <JWT>` is accepted.
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

Minimal example (non-streaming):
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

JSON mode example (`response_format=json_object`):
```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "response_format": {"type": "json_object"},
    "messages": [
      {"role":"system","content":"Return valid JSON only."},
      {"role":"user","content":"Summarize tldw_server with fields: summary, keywords[]"}
    ]
  }'
```

Tools example (function calling):
```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $API_KEY" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "What\'s the weather in Paris?"}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "get_weather",
          "description": "Get current weather by city",
          "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"]
          }
        }
      }
    ],
    "tool_choice": "auto"
  }'
```

## Provider Selection
- If `model` includes a provider prefix (`provider/model`), that provider is used unless `api_provider` is explicitly set.
- If no provider is specified, the server uses `DEFAULT_LLM_PROVIDER`.
- Provider API keys are sourced from environment (`.env`) or `tldw_Server_API/Config_Files/config.txt`.
- Optional failover: when enabled via server config, the Chat module may fallback to a healthy provider on upstream errors (disabled by default for stability).

## Streaming Behavior
- Media type: `text/event-stream`.
- Heartbeats: Sent periodically (default 30s) to keep connections alive.
- Idle timeout: Default 300s of inactivity ends the stream with an error event.
- Completion: Upstream `[DONE]` or natural stream end closes the SSE.

Config keys (Chat-Module):
- `streaming_idle_timeout_seconds` (default 300)
- `streaming_heartbeat_interval_seconds` (default 30)

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

### Streaming Event Format

| Event/Line     | Shape/Fields                                                                 | Notes                                         |
|----------------|-------------------------------------------------------------------------------|-----------------------------------------------|
| `event: stream_start` | `data: { conversation_id, model, timestamp }`                                | Emitted once at start                         |
| Heartbeat      | `: heartbeat <ISO-8601>`                                                      | Comment line; no `data:` payload              |
| Delta chunk    | `data: {"choices":[{"delta":{"content":"..."}}]}`                           | Repeats for each text delta                   |
| Error          | `data: {"error": {"message": "..."}}`                                       | Emitted and stream terminates                 |
| `event: stream_end` | `data: { conversation_id, success, timestamp }`                                 | Emitted on graceful completion                |


## Responses
- Non-streaming JSON uses OpenAI’s `choices` shape and includes `tldw_conversation_id` to help clients track state.

## Persistence
- Default behavior is ephemeral (no DB writes).
- Per-request opt-in: set `"save_to_db": true` to persist conversation/messages.
- Server default can be toggled without client changes:
  - Env: `CHAT_SAVE_DEFAULT=true` (highest precedence) or `DEFAULT_CHAT_SAVE=true`
  - Config file (`Config_Files/config.txt`): `[Chat-Module] chat_save_default = True` (or `default_save_to_db = True`)
  - Fallback legacy default: `[Auto-Save] save_character_chats`
- Stored content includes text and validated/decoded images. Invalid images are saved as placeholders to preserve turn continuity.

### Persistence Behavior

| Setting / Source                          | Value / Example                 | Effect / Notes                                        | Precedence |
|-------------------------------------------|---------------------------------|-------------------------------------------------------|------------|
| Request body                               | `save_to_db: true`              | Persist this request’s conversation/messages          | Highest    |
| Env var                                    | `CHAT_SAVE_DEFAULT=true`        | Default persistence for requests                      | High       |
| Env var (legacy)                           | `DEFAULT_CHAT_SAVE=true`        | Default persistence for requests                      | High       |
| Config file `[Chat-Module]`                | `chat_save_default = True`      | Default persistence (preferred key)                   | Medium     |
| Config file `[Chat-Module]` (legacy)       | `default_save_to_db = True`     | Default persistence (legacy compatibility)            | Medium     |
| Fallback legacy                            | `[Auto-Save] save_character_chats` | Used only if above unset                              | Low        |
| Response (non-stream)                      | `tldw_conversation_id`          | Returned in JSON to help clients retain context       | -          |
| Response (stream)                          | `event: stream_start`           | Includes `conversation_id` at stream start            | -          |


## Validation & Limits
- Images: Accepts `image/png`, `image/jpeg`, `image/webp`. Base64 data URI validation; default max base64 payload ≈ 3MB.
- Messages: Default max messages per request: 1000.
- Text: Default per-message text limit: 400,000 characters.
- Images per request: Default max: 10.
- Oversized or invalid payloads return `400`/`413` with details.

Image message example:
```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "What is in this image?"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,...."}}
  ]
}
```

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
- Chatbook features (Dictionaries, Document Generator, Import/Export): `./Chatbook_Features_API_Documentation.md`
- Character chat sessions API: see `./API_Design.md` (character chat endpoints overview)

## Providers API
Supporting endpoints for discovering providers and models:
- `GET /api/v1/llm/providers` - Configured providers and models
- `GET /api/v1/llm/providers/{provider}` - Details for a specific provider
- `GET /api/v1/llm/models` - Flat list of `<provider>/<model>` values
- `GET /api/v1/llm/models/metadata` - Flattened model capability metadata

## Notes & Limitations
- Provider failover is disabled by default for production stability (can be enabled in `[Chat-Module]`).
- Images in chat messages must be base64 data URIs within `image_url.url` (PNG, JPEG, WEBP).
- The API returns `tldw_conversation_id` in non-streaming responses to let clients maintain context.
