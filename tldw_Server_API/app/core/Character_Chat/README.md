# Character Chat Module (Developer Guide)

The Character Chat subsystem is the backbone for persona-driven conversations in **tldw_server**. It covers character card import/export, conversation persistence, lorebook (“world book”) injection, dynamic chat dictionary replacements, and the rate limiting necessary to operate these features safely in multi-user deployments.

This document orients contributors to the current code layout, major responsibilities, and integration touch points.

---

## High-Level Responsibilities
| Concern | Implementation |
| --- | --- |
| Character card lifecycle | `modules/character_io.py`, `modules/character_db.py`, `ccv3_parser.py` |
| Conversation management | `modules/character_chat.py` |
| Text transformation | `chat_dictionary.py` (pattern-based replacements, token budgets) |
| Lore/world context | `world_book_manager.py` (keyword matching, recursive scanning) |
| Throughput guardrails | `character_rate_limiter.py` (Redis + in-memory fallbacks) |
| Compatibility facade | `Character_Chat_Lib_facade.py`, `modules/__init__.py` (re-exported symbols for older call sites) |

All persistence flows through `ChaChaNotes_DB` (per-user SQLite/Postgres wrapper) from `tldw_Server_API.app.core.DB_Management`.

---

## Module Layout & Entry Points
```
Character_Chat/
├── Character_Chat_Lib_facade.py    # Facade exposing modular helpers under a single import path
├── modules/                        # Split modules with focused concerns
│   ├── character_utils.py          # Placeholder replacement, UI helpers
│   ├── character_io.py             # Card import/export (PNG/WEBP/JSON/MD) + validation
│   ├── character_validation.py     # V1/V2/Pygmalion/TextGen/Alpaca format parsers
│   ├── character_db.py             # CRUD around `ChaChaNotes_DB` tables
│   ├── character_chat.py           # Conversations, messages, metadata
│   └── character_templates.py      # Built-in template helpers (seed characters, clones)
├── chat_dictionary.py              # Pattern-based runtime text replacement engine
├── world_book_manager.py           # Lorebook manager with keyword scanning
├── character_rate_limiter.py       # Import/update/message budget guardrails
├── ccv3_parser.py                  # Character Card v3 validation + mapping
└── chat_dictionary.py / world_book_manager.py ...  # see sections below
```

`Character_Chat_Lib_facade.py` re-exports the functions from `modules` (and provides small wrappers such as placeholder substitution for `retrieve_message_details`) so downstream code can rely on a single import path. `modules/__init__.py` collects the public surface area; new helpers should be added there for discoverability.

---

## Data & Persistence Model
- Storage is handled by `CharactersRAGDB` (`ChaChaNotes_DB`), which produces per-user SQLite (default) or Postgres databases located under `Databases/user_databases/<user_id>/ChaChaNotes.db`.
- Tables include `character_cards`, `conversations`, `messages`, `world_books`, `world_book_entries`, `chat_dictionary_groups`, and `chat_dictionary_entries`.
- All functions accept an explicit `CharactersRAGDB` instance (dependency-injected in FastAPI endpoints). There is no global state or implicit connections.
- JSON-like fields (alternate greetings, tags, extensions, metadata) are stored as JSON text in the DB and materialized as Python objects inside the library helpers.

For schema details inspect `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`.

---

## Character Card Import & Export
The import pipeline (in `modules/character_io.py`) supports:
- Embedded metadata inside PNG/WEBP (`extract_json_from_image_file`).
- JSON/Markdown cards from TavernAI, SillyTavern, Pygmalion, Text Generation WebUI, Alpaca, and Character Card spec v1/v2/v3.
- Automatic image optimization (conversion to WEBP, resize) during `_prepare_character_data_for_db_storage`.
- Conflict detection: `create_new_character_from_data` raises `ConflictError` when names collide, allowing endpoints to return helpful responses.

The `ccv3_parser.py` module brings minimal support for the emerging Character Card v3 spec (`validate_v3_card`, `parse_v3_card`). V3 parsing is attempted before falling back to v2/v1 heuristics.

Common helpers:
- `import_and_save_character_from_file(...)` - orchestrates file type detection, parsing, validation, DB insert/update.
- `load_character_and_image(...)` - loads a single card with placeholder substitution and decoded `PIL.Image`.
- `get_character_list_for_ui(...)`, `extract_character_id_from_ui_choice(...)` - UI helper utilities.

### API Usage
`app/api/v1/endpoints/characters_endpoint.py` delegates to these helpers for the `/characters` REST API. Rate limits are enforced before imports or bulk operations (see below).

---

## Conversation & Message Management
Key functions live in `modules/character_chat.py`:
- `start_new_chat_session(...)`, `list_character_conversations(...)`, `delete_conversation_by_id(...)` - conversation CRUD.
- `post_message_to_conversation(...)`, `edit_message_content(...)`, `set_message_ranking(...)`, `find_messages_in_conversation(...)` - message lifecycle helpers.
- `process_db_messages_to_ui_history(...)` - convert raw message rows into `(user, bot)` tuples for UI consumption, handling placeholder replacements and consecutive message merges.
- `load_chat_and_character(...)` - fetches character metadata, conversation payload, and message list in a single call.

Placeholder replacement is centralized via `modules/character_utils.replace_placeholders`, ensuring tokens like `{{char}}` or `<USER>` resolve consistently.

Endpoints `character_chat_sessions.py` and `character_messages.py` rely heavily on these functions, so maintain backwards compatibility when refactoring signatures.

---

## World Books (Lorebooks)
Implemented in `world_book_manager.py`:
- `WorldBookService` keeps CRUD isolated per user database.
- `WorldBookEntry` pre-compiles regex/literal patterns for fast matching. Supports case sensitivity, whole-word matching, and explicit regex.
- `process_context(...)` assembles lore snippets from applicable world books, respecting token budgets (`_count_tokens`), priorities, optional recursive scanning, and scan depth.
- Attachments: characters can link to multiple world books (`attach_world_books_to_character`, etc.).
- Bulk operations (import/export, statistics) power the `/world-books/*` endpoints.

Token counting uses the shared tokenizer from `tldw_Server_API.app.core.Utils.tokenizer`.

---

## Chat Dictionary
`chat_dictionary.py` provides a pattern-based replacement engine applied to outbound/inbound chat text:
- `ChatDictionaryService` caches active dictionaries per request, sorts entries by priority, and enforces probability-based application, timed effects (sticky, cooldown, delay), max replacements, and token budgets.
- Patterns support literal matches or `/regex/flags` notation (with `i`, `m`, `s`, `x`).
- Each entry tracks runtime state (`last_triggered`, `trigger_count`) to enforce timed behaviour.
- Warnings are emitted via `TokenBudgetExceededWarning` when transformations exceed configured budgets.

The chat API (`app/api/v1/endpoints/chat.py`, section around dictionary endpoints) exposes CRUD and testing endpoints for end users.

---

## Rate Limiting & Quotas
`character_rate_limiter.py` ensures character operations and chat completions cannot overwhelm the system:
- Redis-backed ZSET implementation when a Redis client is supplied; falls back to per-process memory otherwise.
- Limits:
  - `max_operations/window_seconds` - generic operations (create/update/import).
  - `max_characters`, `max_chats_per_user`, `max_messages_per_chat`.
  - `max_chat_completions_per_minute`, `max_message_sends_per_minute`.
  - `max_import_size_mb` guard for oversized uploads.
- Helper methods (e.g., `check_rate_limit`, `check_character_limit`, `check_import_size`) raise `HTTPException` (429/403/413) when exceeded.
- `get_character_rate_limiter()` (defined in API deps) instantiates a singleton rate limiter per process.

Unit tests validating this behaviour live in `tldw_Server_API/tests/unit/test_character_rate_limiter.py` and `tests/Character_Chat/test_rate_limits_specific.py`.

---

## API Integration Touch Points
The Character Chat module is consumed across several FastAPI routers:
- `characters_endpoint.py` - card CRUD, import/export, world book management.
- `character_chat_sessions.py` - conversation creation & metadata updates.
- `character_messages.py` - message history, edits, ranking, search.
- `chat.py` - dictionary CRUD, world book context injection during completions, placeholder utilities.

Each endpoint resolves the per-user `CharactersRAGDB` via `get_chacha_db_for_user` and ensures the correct AuthNZ dependencies (`get_request_user`) before calling into this module.

---

## Testing Strategy
Relevant suites:
- `tldw_Server_API/tests/Characters/test_character_chat_lib.py` - large unit suite covering helper behaviour.
- `tldw_Server_API/tests/Characters/test_ccv3_parser.py` - verifies v3 parsing.
- `tldw_Server_API/tests/Character_Chat_NEW/*` - property tests and newer unit coverage for dictionary + world book interactions.
- `tldw_Server_API/tests/integration/test_chatbook_integration.py` - exercises cross-module interactions (Chatbooks + Character Chat).
- `tldw_Server_API/tests/Chat/unit/test_chat_dictionary_endpoints.py` - API layer coverage for dictionary endpoints.

Run targeted tests after touching core logic:
```bash
python -m pytest tldw_Server_API/tests/Characters -v
python -m pytest tldw_Server_API/tests/Character_Chat_NEW -v
python -m pytest tldw_Server_API/tests/unit/test_character_rate_limiter.py -q
```

Most tests rely on fixtures that stub `CharactersRAGDB` and set `TEST_MODE=1` to disable background tasks.

---

## Extending the Module
1. **Prefer the modular files** (`modules/*.py`). Keep the facade updated if you rename or move functions that legacy imports still reference.
2. **Schema changes** must be mirrored in `ChaChaNotes_DB` migrations; avoid ad-hoc SQL in this module.
3. **Preserve placeholder semantics**. Any new message or text field should run through `replace_placeholders` where end users expect templated values.
4. **Respect budgets & limits**. When introducing new operations (e.g., bulk imports), enforce rate limits and token budgets similar to existing ones.
5. **Document supported formats** in this README if import/export changes.
6. **Add tests** in the matching suite (`tests/Characters`, `tests/Character_Chat_NEW`) to capture new behaviour and regressions.

---

## Quick Reference
- **Import character**: `import_and_save_character_from_file(db, file_content=..., file_type=...)`
- **Create conversation**: `start_new_chat_session(db, character_id, title)`
- **Run dictionary transform**: `ChatDictionaryService(db).process_text(text, token_budget=2048)`
- **Process lore**: `WorldBookService(db).process_context(input_text, world_book_ids=[...])`
- **Enforce limits**: `rate_limiter.check_rate_limit(user_id, "character_import")`

With this overview, contributors can navigate the Character Chat subsystem confidently and extend it without breaking legacy flows. Keep this document in sync when making significant changes to module surfaces or behaviour.
