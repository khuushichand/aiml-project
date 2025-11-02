# Character Messages API

Manage messages within character chat sessions. Use these endpoints to send, list, edit, delete, and search messages tied to a conversation.

Tag in OpenAPI: `character-messages`

## Base Paths
- Send/list/search: `/api/v1/chats/{chat_id}/messages` (mounted under `/api/v1`)
- Message detail/edit/delete: `/api/v1/messages/{message_id}`

## Auth + Rate Limits
- Single-user: `X-API-KEY: <key>`
- Multi-user: `Authorization: Bearer <JWT>`
- Per-user/per-action rate limits apply (e.g., `message_send`).

## Endpoints

- Send message: `POST /api/v1/chats/{chat_id}/messages`
- List messages: `GET /api/v1/chats/{chat_id}/messages`
  - Query params: `limit`, `offset`, `include_deleted`, `include_character_context`, `format_for_completions`
- Edit message: `PUT /api/v1/messages/{message_id}`
- Delete message (soft): `DELETE /api/v1/messages/{message_id}`
- Search messages: `GET /api/v1/chats/{chat_id}/messages/search`

Notes
- Ownership is enforced per conversation and per message.
- `format_for_completions=true` returns the OpenAI-style `messages` array ready for `/api/v1/chat/completions`.
- When `include_character_context=true`, a system message is added with the character’s persona fields.

## Examples

Send a message
```bash
curl -X POST "http://localhost:8000/api/v1/chats/{chat_id}/messages" \
  -H "Content-Type: application/json" -H "X-API-KEY: $API_KEY" \
  -d '{"role": "user", "content": "Hello there!"}'
```

List messages formatted for completions
```bash
curl -X GET "http://localhost:8000/api/v1/chats/{chat_id}/messages?format_for_completions=true&include_character_context=true&limit=50" \
  -H "X-API-KEY: $API_KEY"
```

Search messages
```bash
curl -X GET "http://localhost:8000/api/v1/chats/{chat_id}/messages/search?query=hello&limit=20" \
  -H "X-API-KEY: $API_KEY"
```

Delete a message (soft)
```bash
curl -X DELETE "http://localhost:8000/api/v1/messages/{message_id}?expected_version=1" \
  -H "X-API-KEY: $API_KEY"
```
