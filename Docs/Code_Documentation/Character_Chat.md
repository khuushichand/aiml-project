# Character Chat - Developer Guide

This guide documents the Character Chat subsystem: character cards, world books (lorebooks), chat sessions, and messages - and how these integrate with the main Chat API.

## Goals & Scope

- Import and manage character cards (SillyTavern-compatible; CCv3, JSON/PNG/WEBP/MD).
- Create and manage character-scoped chat sessions and messages.
- Attach world books to characters, build contextual prompts from entries.
- Enforce rate limits and access control per user and conversation.
- Interoperate cleanly with `/api/v1/chat/completions` for LLM responses.

## Architecture Overview

- Core module: `tldw_Server_API/app/core/Character_Chat/`
  - `modules/` - refactored implementation split by concern (`character_db`, `character_chat`, `character_io`, `character_utils`, etc.).
  - `Character_Chat_Lib_facade.py` - stable API imported by endpoints; re-exports the functions from `modules`.
  - `world_book_manager.py` - world book (lorebook) CRUD, entry search, attachment to characters, statistics.
  - `chat_dictionary.py` - legacy character-scoped dictionary support (replacement, budgeting) used by older flows.
  - `character_rate_limiter.py` - rate limiting for character import, chat/session/message actions.
  - `ccv3_parser.py` - Character Card V3 parsing helpers (strict field handling, safety guards).

- Endpoints: `tldw_Server_API/app/api/v1/endpoints/`
  - `characters_endpoint.py` - import/list/get/update/delete characters; world books CRUD + bulk ops; attach/detach to characters; context processing.
  - `character_chat_sessions.py` - create/get/list/rename/delete chat sessions; prepare messages for completions; optional character-scoped completions helper.
  - `character_messages.py` - CRUD for messages within sessions; search/edit/delete; image handling.

- Database layer: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
  - `CharactersRAGDB` abstraction handles characters, conversations (chat sessions), messages, world books, and attachments. All writes/reads go through this layer - no raw SQL from endpoints.

## Data Model (Conceptual)

- Character
  - Fields: `id`, `name`, `system_prompt`, `description`, `greeting`, `tags[]`, `image`, `extensions`, etc.
  - Import supports: PNG/WEBP with embedded JSON, JSON/MD/Plain text; CCv3 parsing via `ccv3_parser.py`.
  - World books can be attached (many-to-many via attachment table).

- World Book (Lorebook)
  - World book metadata + entries (pattern, text, groups, weights, enabled flags, etc.).
  - Bulk import/export; per-entry CRUD and search; per-book stats.

- Chat Session (Conversation)
  - Fields: `id` (UUID), `character_id`, `title`, `client_id` (owner), timestamps, version; parent/root for thread structures.

- Message
  - Fields: `id` (UUID), `conversation_id`, `parent_message_id` (for threading), `sender` (`user|assistant|system`), `content`, optional `image_data`/`image_mime_type`, timestamps, version, ranking.

Access control: Conversations and messages are owned by `client_id` (user id) and validated on every action. Unauthorized access yields 403; non-existent resources yield 404.

## Request Flow (Character → Completion)

1. Import a character card via `POST /api/v1/characters/import`.
2. Create a chat session via `POST /api/v1/character_chats/` with the `character_id`.
3. Add user messages via `POST /api/v1/character_messages/chats/{chat_id}/messages`.
4. Call the generic Chat API `POST /api/v1/chat/completions` with `character_id` and `conversation_id` to assemble context and get LLM replies.
   - The Chat endpoint pulls character system context + world book entries (and optionally chat dictionaries), builds messages, and dispatches to configured providers.
   - Persistence of assistant replies is controlled by `save_to_db` or server default.

The Character Chat endpoints also expose a helper to prepare messages for completions, or to invoke a character-scoped completion directly for legacy clients.

## Character Import & Validation

- Endpoint: `POST /api/v1/characters/import`.
- Accepts: `.png`, `.webp` (embedded JSON), `.json`, `.yaml|.yml`, `.txt`, `.md`.
- The facade `import_and_save_character_from_file` handles type detection, CCv3 parsing, and DB writes.
- On name conflicts, a ConflictError may return the existing character; the endpoint surfaces 200 with details or 409 depending on context.
- Rate limiting applies to import size and frequency.

## World Books (Lorebooks)

- CRUD: create/update/delete world books and entries; import/export complete books.
- Attachment: link world books to characters; the chat pipeline loads relevant entries for the active character.
- Processing: `/process-context` endpoints can precompute context payloads (e.g., filtered entries) for debugging and testing.
- Bulk operations: batch add/update entries; stats endpoints for visibility.

## Sessions & Messages

- Sessions
  - Create: `POST /api/v1/character_chats/` → returns conversation metadata.
  - Get/List/Update/Delete: standard CRUD endpoints.
  - Limits: per-user chat count caps are enforced via `character_rate_limiter`.

- Messages
  - Create: `POST /api/v1/character_messages/chats/{chat_id}/messages` (supports parent message for threading and optional base64 image)
  - Get/List/Update/Delete: standard operations; search within a conversation.
  - Limits: per-chat message caps and send-rate limits via `character_rate_limiter`.
  - Access: conversation ownership verified for every message action.

## Integration with the Chat API

- The main Chat endpoint (`/api/v1/chat/completions`) recognizes `character_id` and `conversation_id` on the request body.
- Context assembly:
  - Character system prompt and metadata are inserted as system context.
  - World book entries attached to the character are selected/ordered per `world_book_manager` logic.
  - Existing conversation messages are loaded (bounded by limits) and included before the new user turn.
- Persistence:
  - Requests are ephemeral by default; `save_to_db: true` persists user/assistant turns.
  - Server default can be set via `[Chat-Module]` or env (see Chat Developer Guide).
- Tools and streaming:
  - Tool calls and SSE streaming follow the Chat module’s OpenAI-compatible behavior (see Chat Developer Guide for details).

## Rate Limiting & Security

- `character_rate_limiter.py` enforces action-specific limits:
  - `character_import`, `chat_create`, `message_send`, and per-chat/per-user caps.
  - Additional throttles for message send rate and world book operations.
- Access control uses `get_request_user` + DB ownership checks (`client_id`).
- Errors follow consistent HTTP codes: 401 (auth), 403 (forbidden), 404 (not found), 409 (conflict), 429 (rate limit), 5xx (server).

## Testing

- Primary suites:
  - `tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py`
  - `tldw_Server_API/tests/Character_Chat/test_rate_limits_specific.py`
  - `tldw_Server_API/tests/Character_Chat/test_world_book_*`
  - Streaming and completion helpers: `test_complete_v2_*`
- Newer harness and utilities: `tldw_Server_API/tests/Character_Chat_NEW/`

## Tips & Maintenance

- Keep all DB access through `CharactersRAGDB` to maintain transactional safety and consistent error handling.
- When updating import logic or CCv3 parsing, ensure world book mapping and extensions remain backward-compatible.
- Prefer using the facade `Character_Chat_Lib_facade.py` in endpoints to reduce coupling and simplify tests.
- For changes that affect prompt assembly or streaming behavior, also review the Chat module docs and tests.

See also: Chat Developer Guide (Code_Documentation/Chat_Developer_Guide.md) for the end-to-end chat orchestration, streaming, moderation, and provider dispatch details.
