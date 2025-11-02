# Character Chat Sessions API

Manage character chat sessions (conversations) for users. This layer handles session CRUD, metadata, export, and helpers for preparing context for `/api/v1/chat/completions`.

Tag in OpenAPI: `character-chat-sessions`

## Base URL
`/api/v1/chats`

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
- Legacy rate-limit test: `POST /api/v1/chats/{chat_id}/complete`

Notes
- Ownership is enforced; only the creator can access their sessions.
- Use the Messages API to send/edit/delete/search messages in a session.
- For LLM replies, call `POST /api/v1/chat/completions` with a `conversation_id` and optional `character_id`.

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
