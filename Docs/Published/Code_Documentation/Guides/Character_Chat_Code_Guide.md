# Character Chat Code Guide (Developers)

This guide orients project developers to the Character_Chat module: what’s in it, how it works, and how to work with it when building or extending the server.

See also: `tldw_Server_API/app/core/Character_Chat/README.md` for a focused module readme, and the API routers listed below for concrete usage.

## Scope & Goals
- Persona/character cards: import/export across common formats (PNG/WEBP with embedded JSON, JSON/Markdown, V1/V2/V3)
- Conversations and messages: session lifecycle, message CRUD, pagination, search, ranking
- World Books (lorebooks): keyword-driven context injection with budgets/priorities
- Chat Dictionary: pattern-based replacements, probabilities, token budgets, grouped rules
- Rate limiting: per-user ops, chat, and message guardrails (Redis + in-memory fallback)
- Per-user storage: all state lives under a user-scoped ChaChaNotes database

## Quick Map (Where Things Live)
- Facade and structure:
  - `tldw_Server_API/app/core/Character_Chat/Character_Chat_Lib_facade.py`
  - `tldw_Server_API/app/core/Character_Chat/modules/` (split implementation)
- Split modules (primary):
  - `.../modules/character_utils.py` — placeholders, UI helpers, sender→role mapping
  - `.../modules/character_io.py` — card import/export (PNG/WEBP/JSON/MD), format validation
  - `.../modules/character_validation.py` — parsers for V1/V2/Pygmalion/TextGen/Alpaca
  - `.../modules/character_db.py` — CRUD wrappers over `ChaChaNotes_DB`
  - `.../modules/character_chat.py` — chat sessions + messages + history shaping
  - `.../modules/character_templates.py` — small built-in character templates
- Ancillary components:
  - `tldw_Server_API/app/core/Character_Chat/character_rate_limiter.py` — per-user quotas
  - `tldw_Server_API/app/core/Character_Chat/chat_dictionary.py` — pattern-based text transforms
  - `tldw_Server_API/app/core/Character_Chat/world_book_manager.py` — lorebook manager
  - `tldw_Server_API/app/core/Character_Chat/ccv3_parser.py` — Character Card v3 support
- DB abstraction (per-user):
  - `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`

## API Routers (Primary Touch Points)
- Characters (cards + world books): `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`
- Chat Sessions: `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`
- Messages: `tldw_Server_API/app/api/v1/endpoints/character_messages.py`
- Chat (OpenAI-compatible) core: `tldw_Server_API/app/api/v1/endpoints/chat.py`
- Chat dictionary tooling: `tldw_Server_API/app/api/v1/endpoints/chat_dictionaries.py`

Each router resolves the per-user DB via `get_chacha_db_for_user` and the authenticated user via `get_request_user`.

## Core Concepts & Data Flow
- Per-user isolation and storage path: Every request uses a user-scoped `CharactersRAGDB`. Character Chat resolves the base directory from `USER_DB_BASE_DIR` (defined in `tldw_Server_API.app.core.config`) and stores the DB at `<USER_DB_BASE_DIR>/<user_id>/ChaChaNotes.db`. When unset, the default base is `Databases/user_databases/` under the project root via `db_path_utils`. Override via environment variable or `Config_Files/config.txt` as needed.
- Characters: Stored with textual fields and optional image bytes. JSON-like fields (`alternate_greetings`, `tags`, `extensions`) are normalized when stored.
- Placeholders: Strings may contain `{{char}}`, `{{user}}`, `<CHAR>`, `<USER>`. Utilities replace them at render time.
- Conversations & Messages: Conversations are UUID-identified. Messages reference `conversation_id` and keep `sender` as a string; utilities map sender→role.
- World Books (Lorebooks): Keyword-based snippets that can be injected as system/context messages based on recent message windows, priorities, budgets.
- Chat Dictionary: Pattern-based (regex or literal) replacements with probabilities/cooldowns. Pre-generation dictionary application is handled by the Chat module path (`/api/v1/chat/completions`) via `chat()`. The Character Chat `/complete-v2` path calls `chat_api_call()` directly and does not apply dictionaries by default. Use the Chat endpoint when you need pre-gen dictionary processing.
- Rate Limiting: Guards character operations, chat creation, message volume, and completion frequency (per-user).
- Default character: The DB dependency ensures a default “Helpful AI Assistant” character exists per user on first initialization.

Notes on images and attachments:
- API message listings include `has_image` flags but do not return raw attachment bytes. Use library helpers like `retrieve_conversation_messages_for_ui(..., rich_output=true)` for in-process rich UI shaping when needed.

## Delete and Recovery Policy

- Character deletes are soft deletes. `DELETE /api/v1/characters/{id}` sets `deleted=1` and increments `version`.
- Restore uses optimistic locking: `POST /api/v1/characters/{id}/restore?expected_version=<deleted_version>`.
- If `expected_version` is stale, restore returns `409 Conflict` with a version-mismatch detail.
- UI policy: single and bulk delete expose a 10-second undo action, and the Characters workspace includes a `Recently deleted` scope for out-of-toast recovery.
- Recovery telemetry is emitted by the UI as `tldw:characters-recovery` with actions: `delete`, `undo`, `restore`, `restore_failed`, `bulk_delete`, `bulk_undo`, `bulk_restore`, `bulk_restore_failed`.

## Key Helpers (What to Call)
- Characters
  - `create_new_character_from_data(db, payload)` → `int|None`
  - `get_character_details(db, character_id)` → `dict|None`
  - `update_existing_character_details(db, character_id, payload, version)` → `bool`
  - `delete_character_from_db(db, character_id, version)` → `bool`
  - `import_and_save_character_from_file(db, file_path=None, file_content=None, file_type=None)` → `(success: bool, message: str, character_id: Optional[int])`
  - `search_characters_by_query_text(db, query, limit)` → `list[dict]`
- Chat
  - `start_new_chat_session(db, character_id, user_name, ...)` → `(chat_id, char_data, history, image)`
  - `post_message_to_conversation(db, conversation_id, character_name, message_content, is_user_message, ...)` → `message_id`
  - `retrieve_conversation_messages_for_ui(db, conversation_id, ...)` → `[(user, assistant)]` or rich
  - `map_sender_to_role(sender, character_name)` → `"user"|"assistant"|"system"|"tool"`
  - `replace_placeholders(text, char_name, user_name)` → `str`
  - `retrieve_conversation_messages_for_ui(..., rich_output=True)` → rich UI format including attachment metadata
- World Book & Dictionary
  - See `world_book_manager.py` and `chat_dictionary.py` for CRUD and processing routines.
- Rate Limiting
  - `get_character_rate_limiter()` → `CharacterRateLimiter` with:
    - `check_rate_limit(user_id, operation)` – global operations window (character ops/imports/etc.)
    - `check_character_limit(user_id, current_count)` – caps total characters per user. Pass the current character count *before* creation; the limiter denies when `current_count >= max_characters`.
    - `check_chat_limit(user_id, current_chat_count)` – caps total chats per user. Pass the current chat count *before* creation; the limiter denies when `current_chat_count >= max_chats_per_user`.
    - `check_message_limit(chat_id, current_message_count)` – caps messages per chat (enforced by message endpoints).
    - `check_chat_completion_rate(user_id)` / `check_message_send_rate(user_id)` – per‑minute throttles.
    - `get_usage_stats(user_id)` – returns a local snapshot:
      - `operations_used`, `operations_remaining`, `reset_time` (Unix timestamp or `null` when unused).

## Schemas (Requests/Responses)
- Chat sessions/messages: `tldw_Server_API/app/api/v1/schemas/chat_session_schemas.py`
- Characters: `tldw_Server_API/app/api/v1/schemas/character_schemas.py`
- World books: `tldw_Server_API/app/api/v1/schemas/world_book_schemas.py`

These schemas define the FastAPI contracts and demonstrate field names/validation.

## How It Works (Under the Hood)
- Facade pattern: `Character_Chat_Lib_facade.py` re-exports `modules/*` functions to preserve legacy import paths while allowing modular code.
- Storage: All reads/writes go through `CharactersRAGDB` (no raw SQL from these helpers); optimistic locking is supported via per-record `version` fields.
- Images: On character create/update, `image_base64` is decoded, optionally resized and converted to WEBP, and stored as bytes.
- Sender→role mapping: `character_utils.map_sender_to_role()` normalizes stored senders to OpenAI roles using aliases plus the conversation’s character name.
- History shaping: `character_chat.process_db_messages_to_rich_ui_history()` infers turns (user/character/system/tool), resolves placeholders, and supports alternate character aliases discovered from message history.
- World books: Entries compile into regex/literal patterns; recent conversation windows are scanned to select entries within a token budget.
- Chat dictionary: Each entry can be probability-gated and time-gated; processing walks entries and applies substitutions up to defined limits.
- Rate limiting: Redis ZSETs if enabled, else in-memory; separate guards exist for operations/hour, chats/user, messages/chat, and completions/minute.

## Working With It (Common Recipes)

1) Create a character
```python
from tldw_Server_API.app.core.Character_Chat.Character_Chat_Lib_facade import create_new_character_from_data

payload = {
    "name": "Ayla",
    "description": "A curious explorer",
    "personality": "Optimistic, thoughtful",
    "first_message": "Hi, I’m {{char}}. What shall we learn today, {{user}}?",
    "tags": ["exploration", "friendly"],
}
char_id = create_new_character_from_data(db, payload)
```

2) Start a chat session
```python
from tldw_Server_API.app.core.Character_Chat.Character_Chat_Lib_facade import start_new_chat_session
chat_id, char_data, ui_history, image = start_new_chat_session(db, character_id=char_id, user_name="User")
```

3) Send a message
```python
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
message_id = db.add_message({
    "conversation_id": chat_id,
    "sender": "user",
    "content": "Hello!",
})
```

4) Fetch messages formatted for OpenAI Chat API
```python
from tldw_Server_API.app.core.Character_Chat.Character_Chat_Lib_facade import retrieve_conversation_messages_for_ui
msgs = retrieve_conversation_messages_for_ui(db, chat_id, messages_limit=50)
# Or via endpoint:
# GET /api/v1/chats/{chat_id}/messages?format_for_completions=true
# Add include_character_context=true to prepend character system context
# Add include_message_ids=true to include message_id fields in completions format
```

5) Prepare and call completion (v2)
- Prepare: `POST /api/v1/chats/{chat_id}/completions` → returns `{messages: [...]} + character system context`
- Complete: `POST /api/v1/chats/{chat_id}/complete-v2` with provider/model/temp/max_tokens/stream
- Persist streamed results: `POST /api/v1/chats/{chat_id}/completions/persist`

6) Filter characters by tags
```http
GET /api/v1/characters/filter?tags=wizard&tags=fantasy&match_all=false
```

7) World book basics
- Create: `POST /api/v1/characters/world-books`
- Add entries: `POST /api/v1/characters/world-books/{id}/entries`
- Stats/Export/Import available under the same router.

8) Chat dictionary basics
- Manage groups/entries under `chat_dictionaries.py` endpoints (create/list/export/import/statistics)
- Pre-generation application occurs in the Chat module path (`/api/v1/chat/completions`). The Character Chat `/complete-v2` flow does not apply dictionaries by default; use the Chat endpoint if you need dictionary processing before provider calls.

## API Examples (curl/httpx)

Set up some quick env vars:
```bash
API="http://127.0.0.1:8000/api/v1"
KEY="<YOUR_API_KEY_OR_BEARER>"   # Use X-API-KEY for single-user; Authorization for JWT
```

1) Create chat with seeded greeting
```bash
curl -sS -X POST "$API/chats?seed_first_message=true&greeting_strategy=alternate_index&alternate_index=0" \
  -H 'Content-Type: application/json' \
  -H "X-API-KEY: $KEY" \
  -d '{
    "character_id": <CHARACTER_ID>,
    "title": "Intro chat"
  }'
# JWT alternative:
# -H "Authorization: Bearer $KEY"
```

2) Get messages with tool_calls and metadata
```bash
curl -sS "$API/chats/<CHAT_ID>/messages?limit=50&include_tool_calls=true&include_metadata=true" \
  -H "X-API-KEY: $KEY"

# Completions-ready format with system context:
curl -sS "$API/chats/<CHAT_ID>/messages?format_for_completions=true&include_character_context=true&include_message_ids=true" \
  -H "X-API-KEY: $KEY"
```

3) World book processing
```bash
curl -sS -X POST "$API/characters/world-books/process" \
  -H 'Content-Type: application/json' \
  -H "X-API-KEY: $KEY" \
  -d '{
    "text": "User mentions Hogwarts and potions in the last messages",
    "character_id": <CHARACTER_ID>,
    "scan_depth": 5,
    "token_budget": 400,
    "recursive_scanning": false
  }'
```

4) Complete (non-streaming) and persist
```bash
curl -sS -X POST "$API/chats/<CHAT_ID>/complete-v2" \
  -H 'Content-Type: application/json' \
  -H "X-API-KEY: $KEY" \
  -d '{
    "include_character_context": true,
    "append_user_message": "Hello!",
    "save_to_db": true,
    "provider": "local-llm",
    "model": "local-test",
    "stream": false,
    "temperature": 0.7,
    "max_tokens": 200
  }'
# Response contains assistant_content and saved=true when persisted.
```

5) Complete (streaming SSE) then persist
```bash
# Streamed response (assistant content is NOT persisted in streaming mode)
curl -N -sS -X POST "$API/chats/<CHAT_ID>/complete-v2" \
  -H 'Content-Type: application/json' \
  -H "X-API-KEY: $KEY" \
  -d '{
    "include_character_context": true,
    "append_user_message": "Hello!",
    "save_to_db": false,
    "provider": "local-llm",
    "model": "local-test",
    "stream": true
  }'

# Persist the streamed assistant text (replace with content and optional user_message_id)
curl -sS -X POST "$API/chats/<CHAT_ID>/completions/persist" \
  -H 'Content-Type: application/json' \
  -H "X-API-KEY: $KEY" \
  -d '{
    "assistant_content": "<ASSISTANT_TEXT_FROM_SSE>",
    "user_message_id": "<USER_MESSAGE_ID>",
    "tool_calls": [],
    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
  }'
```

Callout: When `stream=true`, assistant content is never persisted during `/complete-v2` (even if `save_to_db=true`). Use `/{chat_id}/completions/persist` to store the streamed result.

6) Character search and rate-limit status
```bash
curl -sS "$API/characters/search/?query=wizard" -H "X-API-KEY: $KEY"
curl -sS "$API/characters/rate-limit-status" -H "X-API-KEY: $KEY"
```

## Extension Points
- Add card formats: extend `character_validation.py` and `character_io.py` (parsing + normalization), wire through facade exports if needed.
- Customize role mapping: adjust `map_sender_to_role` and alias constants in `character_utils.py`.
- Message metadata/tool-calls: store via endpoints that accept `tool_calls` and retrieve with `db.get_message_metadata(message_id)` (see `character_messages.py`).
- Rate limits: tune in `character_rate_limiter.py` or via env/settings (`CHARACTER_RATE_LIMIT_*`, `MAX_*`). Defaults (current): `MAX_CHATS_PER_USER=100`, `MAX_MESSAGES_PER_CHAT=1000`, `MAX_MESSAGES_PER_CHAT_SOFT=1000` (non-persisted completions), `MAX_CHAT_COMPLETIONS_PER_MINUTE=20`, `MAX_MESSAGE_SENDS_PER_MINUTE=60`.
- Provider integration: Character Chat builds standard OpenAI-style `messages` for `/api/v1/chat/completions`. Extend provider logic in the Chat module (`core/Chat/*`).
- Dictionary application: Pre-gen dictionary logic lives in the Chat module (`chat()`); Character Chat `/complete-v2` does not apply it by default.

## Error Handling & Guardrails
- Validation: Pydantic schemas enforce inputs; import/path errors surface as `InputError`/`ConflictError` mapped to HTTP 400/409.
- Optimistic locking: Most updates require `expected_version` to avoid lost updates; endpoints return 409 on mismatch.
- Rate limits: 403 on caps (e.g., max chats/messages), 429 on per-minute throttles, 413 on large uploads/images.
- Placeholders: Replacement happens close to render; DB always stores canonical raw values.
- Tool-calls retrieval: `include_tool_calls=true` enriches the standard messages response. The `format_for_completions=true` output is OpenAI-style and does not include `tool_calls` objects.

## Settings & Environment Flags
- Rate limiting: `CHARACTER_RATE_LIMIT_ENABLED`, `CHARACTER_RATE_LIMIT_OPS`, `CHARACTER_RATE_LIMIT_WINDOW`, `MAX_CHARACTERS_PER_USER`, `MAX_CHATS_PER_USER` (default 100), `MAX_MESSAGES_PER_CHAT` (default 1000), `MAX_MESSAGES_PER_CHAT_SOFT` (default 1000, non-persisted completions), `MAX_CHAT_COMPLETIONS_PER_MINUTE` (default 20), `MAX_MESSAGE_SENDS_PER_MINUTE` (default 60)
- Redis: `REDIS_ENABLED`, `REDIS_URL`
- Test mode: `TEST_MODE=1` relaxes rate limits and disables heavy workers
- Local LLM toggles used by completion paths: `ENABLE_LOCAL_LLM_PROVIDER`, `ALLOW_LOCAL_LLM_CALLS`, `DISABLE_OFFLINE_SIM`

## Tests (Good Starting Points)
- Core helpers: `tldw_Server_API/tests/Characters/test_character_chat_lib.py`
- v3 parser: `tldw_Server_API/tests/Characters/test_ccv3_parser.py`
- Newer unit/property tests: `tldw_Server_API/tests/Character_Chat_NEW/`
- Dictionary endpoints: `tldw_Server_API/tests/Chat/unit/test_chat_dictionary_endpoints.py`
- Rate limiter: `tldw_Server_API/tests/unit/test_character_rate_limiter.py`

Example:
```bash
python -m pytest tldw_Server_API/tests/Characters -v
python -m pytest tldw_Server_API/tests/Character_Chat_NEW -v
```

## Gotchas
- Sender names vs roles: DB stores sender strings; always normalize via `map_sender_to_role` when building Chat API payloads.
- Image handling: `image_base64` may include data URL prefixes; normalization strips them and optimizes images. Invalid base64 raises `InputError`.
- JSON fields: `tags`, `alternate_greetings`, `extensions` accept strings or lists/dicts; validators normalize but verify types before writing.
- Pagination windows: World book scanning depends on message windows and budgets; incorrect `limit/offset` can change injected context.
 - Persistence & ownership: API endpoints set `client_id` automatically for conversations/messages. If you insert via DB helpers directly, ensure `client_id` is populated (string user ID); ownership checks depend on it.
 - Default character: The dependency ensures a per-user default “Helpful AI Assistant” is present; don’t assume an empty character list on fresh DBs.
 - Streaming persistence: For `/complete-v2`, `save_to_db` is ignored when `stream=true`; use `/{chat_id}/completions/persist`.

## Reference Endpoints (selection)
- Characters: list/create/update/delete/import/filter, world books sub-routes — `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`
- Chat Sessions: create/get/prepare/completions (v2)/list/update/delete/export — `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`
- Messages: create/list/search/get/update/delete — `tldw_Server_API/app/api/v1/endpoints/character_messages.py`
- Chat Dictionaries: group/entry CRUD + import/export/stats — `tldw_Server_API/app/api/v1/endpoints/chat_dictionaries.py`

---

If you need help wiring a new feature into Character Chat (e.g., a new card format, a provider-specific tool-calls mapping, or a world book matching strategy), mirror existing patterns in `modules/*` and expose the new API via the facade for consistency.
