# Story Engine and Narrative Memory PRD (Interactive Fiction Backend)

Status: Draft
Owner: Core Maintainers
Audience: Backend and infrastructure contributors

## 1. Summary
- Problem: tldw_server has robust chat, RAG, and character chat features, but lacks a backend-first story engine with structured world state, narrative memory, and lore management. This prevents parity with interactive fiction workflows and blocks future story-first tooling.
- Solution: Ship a Story Engine module that provides story CRUD, world state tracking, chapter memory with summarization and retrieval, and a dynamic lorebook with optional AI-assisted management. The module is backend-only and integrates with existing LLM, AuthNZ, and database abstractions.
- Status: Not implemented. This PRD defines scope, data model, API surface, and staged rollout.

## 2. Problem Statement
Interactive fiction workflows require structured state (characters, locations, items, quests), persistent narratives, chaptered memory, and lore injection with safe gating. tldw_server currently offers character chat and world books, but they are optimized for persona chat rather than story-mode state and narrative memory. We need a dedicated backend module with clear contracts, feature flags, and test coverage that can be used by any client or future UI.

## 3. Goals and Non-Goals
### Goals
1. Provide story CRUD and per-story world state tracking.
2. Implement narrative memory: chapters, auto-summarization, manual resummarize, and retrieval over prior chapters.
3. Add a dynamic lorebook (entry state, injection rules, hidden info) with optional AI management.
4. Keep multi-user AuthNZ support and per-user DB isolation.
5. Support streaming story generation using existing LLM provider infrastructure.

### Non-Goals
- Frontend UI/UX (Next.js WebUI, desktop clients, or mobile).
- Local sync servers, QR pairing, or desktop updaters.
- Grammar checking or client-only writing tools (e.g., Harper WASM).
- Replacing existing Character Chat flows; this is a separate module.

## 4. Personas / Stakeholders
- Story builders: need structured world state and memory to build interactive narratives.
- API integrators: need a stable backend surface for story CRUD and generation.
- Maintainers: need code structure, tests, and clean DB boundaries.
- Ops: need predictable resource usage and feature flags for safe rollout.

## 5. Success Metrics
- Story creation success rate and time-to-first-response.
- Chapter summary creation success rate (and average latency).
- Retrieval accuracy proxy: percent of retrieval calls that return non-empty context.
- Error rate per endpoint and per provider.
- Coverage: unit tests for core logic + integration tests for API surface.

## 6. Scope (MVP)
MVP ships three core capabilities:
1. Story core and world state CRUD.
2. Narrative memory (chapters + retrieval).
3. Lorebook dynamic entries and optional AI lore management.

Deferred:
- Narrative assists (action choices, creative suggestions, style review).
- Client-specific features (sync, updater).

## 7. Architecture Overview
Modules (new):
- Core logic: `tldw_Server_API/app/core/Story_Engine/`
  - `story_service.py` (CRUD + orchestration)
  - `world_state.py` (characters, locations, items, story beats)
  - `memory_service.py` (chaptering + summarization + retrieval)
  - `lore_service.py` (entry CRUD + injection + activation tracking)
  - `lore_management.py` (AI-assisted entry changes, tool-calling)
- DB management: `tldw_Server_API/app/core/DB_Management/Story_DB.py` (new)
- API endpoints: `tldw_Server_API/app/api/v1/endpoints/stories.py`
- Schemas: `tldw_Server_API/app/api/v1/schemas/stories.py`

Flow (story turn):
1. Client posts user action to `/api/v1/stories/{id}/actions`.
2. World state is loaded and updated (optional classifier step).
3. Lore retrieval selects relevant entries based on injection rules.
4. Memory service decides whether to create or update chapters.
5. LLM response is generated (streaming optional) via existing provider manager.
6. Story entry + metadata are persisted.

## 8. Data Model (SQLite default, Postgres supported)
Per-user database path: `<USER_DB_BASE_DIR>/<user_id>/Story_DB.db` (new). This avoids mixing with `ChaChaNotes_DB` and keeps schema focused. Reuse DB_Management patterns (optimistic locking, soft delete, sync log optional). `USER_DB_BASE_DIR` is defined in `tldw_Server_API.app.core.config` (defaults to `Databases/user_databases/` under the project root); override via environment variable or `Config_Files/config.txt` as needed.

Tables (high level):
- `stories`
  - id, title, description, genre, mode, settings_json, memory_config_json, time_tracker_json, created_at, updated_at
- `story_entries`
  - id, story_id, type (user_action|narration|system), content, position, metadata_json, created_at
- `story_characters`, `story_locations`, `story_items`
  - story-scoped state rows with JSON metadata for relationships, visits, inventory, etc.
- `story_beats`
  - title, description, type, status, triggered_at, resolved_at
- `chapters`
  - number, start_entry_id, end_entry_id, entry_count, summary, keywords_json, characters_json, locations_json, plot_threads_json, emotional_tone, start_time_json, end_time_json
- `checkpoints`
  - snapshot of story state (entries, world state, chapters), created_at
- `lore_entries`
  - name, type, description, hidden_info, aliases_json, state_json, injection_json, created_by, created_at, updated_at, lore_management_blacklisted
- `lore_entry_activations`
  - entry_id, last_activated_at, last_entry_position, activation_count
- `lore_change_log` (optional)
  - change_id, story_id, entry_id, change_type, payload_json, created_at

Indexes: story_id + position for entries, story_id + type for lore entries, story_id + number for chapters.

## 9. API Surface (Proposed)
Base path: `/api/v1/stories`

Core:
- POST `/` create story
- GET `/` list stories (filters: mode, updated_at)
- GET `/{story_id}` get story
- PATCH `/{story_id}` update story metadata/settings
- DELETE `/{story_id}` soft delete
- POST `/{story_id}/actions` add user action and generate narrative (streaming optional)
- GET `/{story_id}/entries` list entries (pagination)

World state:
- CRUD endpoints for characters, locations, items, story beats under `/{story_id}/world/*`

Memory:
- GET `/{story_id}/chapters`
- POST `/{story_id}/chapters` (manual chapter)
- POST `/{story_id}/chapters/{chapter_id}/resummarize`
- POST `/{story_id}/memory/analyze` (auto-summarize decision)
- POST `/{story_id}/memory/retrieve` (chapter retrieval)

Lorebook:
- CRUD `/{story_id}/lore/entries`
- POST `/{story_id}/lore/retrieve` (tiered injection result)
- POST `/{story_id}/lore/management` (AI-managed change set, dry-run by default)

Export/Import:
- POST `/{story_id}/export` (Aventura JSON compatible, optional)
- POST `/import` (ingest Aventura JSON into Story DB)

AuthNZ:
- Reuse `get_auth_principal` dependencies, per-user DB resolution, and role gating for admin actions.

## 10. Functional Requirements
1. Story entries are append-only by default; edits require explicit endpoint and optimistic locking.
2. Auto-summarization respects token thresholds and buffer sizes from `memory_config`.
3. Chapter summaries must be deterministic for the same inputs when using deterministic LLM settings.
4. Lore entries support injection modes: `always`, `keyword`, `relevant`, `never`.
5. Hidden lore is never returned to clients unless `include_hidden=true` and user has admin role.
6. Lore management produces a change set that is validated before apply; all changes are logged.
7. Streaming narrative responses are supported via SSE, aligned with existing chat streaming conventions.
8. All DB access uses `DB_Management` abstractions (no raw SQL outside).
9. Feature flags gate endpoints and are exposed in `/api/v1/config/docs-info`.

## 11. Security and Privacy
- AuthNZ enforced on all routes. Story data is per-user by default.
- Rate limits applied to generation and lore management endpoints via ResourceGovernor or module limiters.
- Never log full story content in production logs; use request IDs and token counts.
- Lore entries with hidden_info must be redacted in standard responses.

## 12. Metrics and Observability
Metrics (examples):
- `story_requests_total{endpoint,status}`
- `story_generation_latency_seconds{provider,model}`
- `story_chapter_summaries_total{status}`
- `story_lore_retrieval_total{tier}`
- `story_lore_management_changes_total{change_type}`

Logs:
- Structured loguru fields: `story_id`, `user_id`, `entry_id`, `chapter_id`, `provider`, `model`.

## 13. Rollout Plan
Phase 0: PRD sign-off, schema review, and config flag definition.
Phase 1: Story core + world state CRUD + Story DB.
Phase 2: Memory system (chapters, auto-summarize, retrieval).
Phase 3: Lore entries + retrieval + AI lore management (dry-run default).
Phase 4: Optional import/export and narrative assist endpoints.

## 14. Open Questions
1. Should Story Engine extend `ChaChaNotes_DB` instead of a new `Story_DB`?
2. How should story export align with Chatbooks (shared format vs dedicated)?
3. Should memory retrieval use existing RAG pipelines or a story-specific index?
4. Which endpoints must be admin-gated vs standard user access?
5. What are the minimum provider requirements for tool-calling lore management?

## 15. References
- Character chat and world books: `tldw_Server_API/app/core/Character_Chat/README.md`
- AuthNZ and DB conventions: `Docs/Code_Documentation/Databases/ChaChaNotes_DB.md`
- LLM provider manager: `tldw_Server_API/app/core/LLM_Calls/`
