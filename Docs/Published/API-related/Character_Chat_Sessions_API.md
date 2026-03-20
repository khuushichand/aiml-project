# Character Chat Sessions API

Manage character chat sessions (conversations) for users. This layer handles session CRUD, metadata, export, and helpers for preparing context for `/api/v1/chat/completions`.

Tag in OpenAPI: `character-chat-sessions`

## Base URL
`/api/v1/chats`

Note:
- Conversation metadata endpoints (filters, ranking, analytics, tree view) are under `/api/v1/chat/conversations` and `/api/v1/chat/analytics`.

## Auth + Rate Limits
- Single-user: `X-API-KEY: <key>`
- Multi-user: `Authorization: Bearer <JWT>`
- Standard limits apply; a small per-chat throttle is used by the legacy `/complete` test endpoint.

## Endpoints

- Create session: `POST /api/v1/chats/`
- Get session: `GET /api/v1/chats/{chat_id}`
- Get context (for completions): `GET /api/v1/chats/{chat_id}/context`
- List sessions: `GET /api/v1/chats/`
- Update session: `PUT /api/v1/chats/{chat_id}`
- Delete session (soft): `DELETE /api/v1/chats/{chat_id}`
- Export session: `GET /api/v1/chats/{chat_id}/export`
- Get chat settings: `GET /api/v1/chats/{chat_id}/settings`
- Update chat settings: `PUT /api/v1/chats/{chat_id}/settings`
- Prepare character completion payload: `POST /api/v1/chats/{chat_id}/completions`
- Run character completion (optional persistence/stream): `POST /api/v1/chats/{chat_id}/complete-v2`
- Preview prompt assembly and budgets: `POST /api/v1/chats/{chat_id}/prompt-preview`
- Legacy rate-limit test: `POST /api/v1/chats/{chat_id}/complete`

Notes
- Ownership is enforced; only the creator can access their sessions.
- Use the Messages API to send/edit/delete/search messages in a session.
- For LLM replies, call `POST /api/v1/chat/completions` with a `conversation_id` and optional `character_id`.

## Character Chat Settings Fields (Selected)

`PUT /api/v1/chats/{chat_id}/settings` accepts a merged settings object. Selected keys:

- `chatPresetOverrideId` (string|null): Chat-level prompt preset ID used when `presetScope` is `"chat"`.
- `chatGenerationOverride` (object|null): Canonical per-chat generation override block.
- `generationOverrides` (object|null): Legacy alias accepted for backward compatibility.
- `presetScope` (`"chat"` or `"character"`): Controls whether chat preset override or character preset is default.

`chatGenerationOverride` / `generationOverrides` object shape:
- `enabled` (bool, optional): If `false`, chat-level generation override is disabled.
- `temperature` (number 0.0-2.0, optional)
- `top_p` (number 0.0-1.0, optional)
- `repetition_penalty` (number 0.0-3.0, optional)
- `stop` (array[string], optional)
- `updatedAt` (ISO timestamp, optional)

Compatibility and precedence:
- Server reads canonical `chatGenerationOverride` first.
- If missing, server falls back to legacy `generationOverrides`.
- If both are present, canonical wins.

## Examples

Create a session
```bash
curl -X POST "http://localhost:8000/api/v1/chats/" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"character_id": 42, "title": "Mentor chat"}'
```

Get chat context for completions
```bash
curl -X GET "http://localhost:8000/api/v1/chats/{chat_id}/context" \
  -H "X-API-KEY: $API_KEY"
```

Export as Markdown
```bash
curl -X GET "http://localhost:8000/api/v1/chats/{chat_id}/export?format=markdown" \
  -H "X-API-KEY: $API_KEY"
```

List sessions (paginated)
```bash
curl -X GET "http://localhost:8000/api/v1/chats/?page=1&per_page=20" \
  -H "X-API-KEY: $API_KEY"
```

Example list response
```json
{
  "success": true,
  "data": [
    {"id": "3f6c...", "character_id": 42, "title": "Mentor chat", "message_count": 5}
  ],
  "metadata": {"page": 1, "per_page": 20, "total": 1, "total_pages": 1}
}
```
