# Deep Personalization: Per-User Profiles, Memories, and RAG Biasing

Status: Active (MVP scaffold implemented)

Owner: Core (RAG, LLM, AuthNZ)

Target Version: v0.2.x (Stage 1), v0.3.x (Stage 2-3)

## Summary

Provide opt-in, explainable personalization that leverages a per-user topic profile and concise memories to improve retrieval, chat grounding, and UX. Personalization remains transparent, reversible (purge), and user-controlled.

## Current Status (v0.2.x dev)

- Feature flags: loaded from config; endpoints are gated when disabled.
  - Config: `[personalization] enabled=true` in `tldw_Server_API/Config_Files/config.txt`.
  - Exposed at runtime via `GET /api/v1/config/docs-info` under `capabilities.personalization`.
- Storage: per-user SQLite `Personalization.db` with `usage_events`, `topic_profiles`, `semantic_memories` (episodic stub present).
- Event logging: best-effort `UsageEventLogger` integrated into chat, TTS, audio transcription, media processing (videos, audios, ebooks, documents, pdfs), and web scraping endpoints.
- API endpoints (scaffolded and functional): opt-in, purge, profile, preferences, memories list/add/delete; explanations placeholder.
- Consolidation service: background loop + admin trigger; current implementation upserts topic scores from recent event tags. In-memory last-tick status is available.
- RAG integration: scorer/context builder stubs exist; blending weights and “why” tracing to be iterated.
- WebUI: Personalization tab (preview) for viewing profile/weights and adding/listing memories; tab visibility follows server capabilities.
- Tests: basic endpoint CRUD, feature flag presence, and usage-event logging across relevant media/audio/web endpoints.

## Changelog

- v0.2.x dev
  - Implemented feature flags and capability exposure via `/api/v1/config/docs-info`.
  - Added per-user SQLite Personalization DB; event logger integrated across chat/audio/media/web scraping.
  - Scaffolded personalization API (opt-in, purge, profile, preferences, memories CRUD; explanations placeholder).
  - Added consolidation service (tag-frequency topic upserts), admin trigger, and in-memory last-tick status with admin GET status endpoint.
  - WebUI tab wired behind capabilities; added unit tests for usage-event logging on ebooks/documents/pdfs.
- v0.1.0
  - Initial draft design with goals, architecture, data model, and milestones.

## Goals

- Capture user activity (ingestion, views, searches, chats, notes) as structured events.
- Consolidate events into: (1) topic affinities and (2) distilled semantic memories.
- Bias RAG re-ranking and chat preambles with user-relevant context, with explanations.
- Offer a Personalization Dashboard to inspect/edit memories, topics, and weights.
- Keep everything opt-in per user, with purge and export controls.

## Non-Goals (Initial)

- Cross-user modeling or global recommendations (future, opt-in only).
- On-device encryption/federated learning (future consideration).
- Intrusive UI nudges; personalization is subtle and explainable.

## User Stories

- As a user, I opt in and see my evolving topic interests and key preferences.
- As a user, I can pin, edit, or delete a memory and see where it applies.
- As a user, my searches and chat answers feel more relevant to my past work.
- As a user, I can purge all personalization data and return to the default behavior.

## Architecture Overview

- Event ingestion via API dependencies logs `UsageEvent`s for opted-in users.
- A background Consolidation Service periodically embeds events, clusters topics, and distills memories.
- The Personalization Scorer reranks RAG results using topic and memory overlap with the current query.
- Chat context builder injects a brief profile summary and top-k relevant memories.

## Data Model (SQLite + Chroma)

SQLite (per-user DB): `Databases/user_databases/<user_id>/Personalization.db`

- `UserProfile`
  - `user_id: str` (PK)
  - `enabled: bool` (opt-in flag)
  - `alpha: float` (bm25 weight), `beta: float` (vector), `gamma: float` (personal)
  - `recency_half_life_days: int`
  - `updated_at: datetime`

- `UsageEvent`
  - `id: str` (PK), `user_id: str`, `timestamp: datetime`, `type: enum` (ingest/view/search/chat/note)
  - `resource_id: str | null`, `tags: list[str]`, `metadata: json`

- `TopicProfile`
  - `id: str` (PK), `user_id: str`, `label: str`
  - `centroid_embedding: list[float]`, `score: float` (decayed affinity), `last_seen: datetime`

- `PersonalMemoryEpisodic`
  - `id: str` (PK), `user_id: str`, `event_id: str`, `summary: str`, `timestamp: datetime`

- `PersonalMemorySemantic`
  - `id: str` (PK), `user_id: str`, `content: str` (concise fact/preference/task)
  - `embedding: list[float]`, `tags: list[str]`, `source_event_ids: list[str]`, `pinned: bool`

Chroma (per-user collections):

- `personal_topics_<user_id>` (TopicProfile embeddings)
- `personal_memories_<user_id>` (Semantic memories)

## Services & Integration

- Event Collector (API deps)
  - Location: `tldw_Server_API/app/api/v1/API_Deps/`
  - Behavior: For authenticated requests, if user has `enabled=True`, log `UsageEvent`.
  - Privacy: Never store raw secrets; hash/strip sensitive fields.

- Consolidation Service
  - Location: `tldw_Server_API/app/services/personalization_consolidation.py`
  - Schedule: Periodic (e.g., every 30-60 min) and on-demand API trigger.
  - Steps:
    - Embed recent events (title, tags, brief content fingerprint).
    - Incremental clustering → update `TopicProfile` + Chroma centroid.
    - Summarize frequent patterns into `PersonalMemorySemantic` (LLM-assisted, rate limited).
    - Move highlights into `PersonalMemoryEpisodic` for short-term recall.
  - MVP behavior (implemented): compute tag-frequency topic scores from recent events; upsert into `topic_profiles`.
  - Ops: maintains in-memory `last_ticks` per user for status; graceful start/stop with app lifecycle.

- Personalization Scorer (RAG)
  - Location: `tldw_Server_API/app/core/RAG/personalization_scorer.py`
  - Score: `score = bm25 + alpha*vector + beta*personal_similarity + gamma*recency`
  - Explanations: Attach `why` signals (topic overlap, memory match, recency boost).

- Chat Context Builder (LLM)
  - Location: `tldw_Server_API/app/core/LLM_Calls/context_builders/personal_context.py`
  - Behavior: Given a chat input, embed intent; fetch top-k semantic memories; add concise profile summary (<300 chars) and selected memories (<3-5) to the system preamble.

## API Design

Base path: `/api/v1/personalization`

- `POST /opt-in` → enable personalization (idempotent)
  - Req: `{ enabled: true }`
  - Res: `{ enabled: true, user_id, updated_at }`

- `POST /purge` → delete all personalization data for user
  - Res: `{ status: "ok", deleted_counts: {...} }`

- `GET /profile` → get settings and summary
  - Res: `{ enabled, alpha, beta, gamma, recency_half_life_days, topic_count, memory_count, updated_at }`

- `POST /preferences` → update weights/preferences
  - Req: `{ alpha?, beta?, gamma?, recency_half_life_days? }`
  - Res: profile object

- `GET /memories` → list semantic and episodic memories (paged)
  - Query: `type=semantic|episodic`, `q?`, `page?`, `size?`

- `POST /memories` → add or pin a semantic memory
  - Req: `{ content, tags?, pinned? }`

- `DELETE /memories/{id}` → remove memory

- `GET /explanations` → last N personalization signals used in RAG/chat
  - Res: `[ { timestamp, context: "rag|chat", signals: [...] } ]`

Schemas live under: `tldw_Server_API/app/api/v1/schemas/personalization.py`

Implementation notes:
- All endpoints are feature-gated; return 404 when personalization is disabled.
- Explanations endpoint is a placeholder pending integration with the reranker trace.

Admin & Ops:
- `POST /api/v1/admin/personalization/consolidate` (admin) triggers one-off consolidation.
- `GET  /api/v1/admin/personalization/status` (admin) returns background service state and per-user last tick.

## WebUI Additions

- Personalization Dashboard (`/webui/personalization`)
  - Opt-in toggle, sliders for `alpha/beta/gamma`, half-life selector.
  - Topic list with affinity bars; memory list with search, pin, delete.
  - “Why” popovers on search/chat results.
  - Visibility controlled by capability map from `GET /api/v1/config/docs-info` (`capabilities.personalization`).

## Configuration

`tldw_Server_API/Config_Files/config.txt`

```
[personalization]
enabled = true
alpha = 0.2
beta = 0.6
gamma = 0.2
recency_half_life_days = 14
```

Environment overrides supported via existing config loader.

Runtime capability surface:
- `GET /api/v1/config/docs-info` → includes `capabilities` and `supported_features` maps (for backward compatibility).

## Privacy & Security

- Default off per user; explicit opt-in.
- Purge endpoint removes SQLite rows and Chroma collections.
- Rate limits on consolidation; never log secret values.
- Access control via existing AuthNZ user scopes.

## Testing Strategy

- Unit
  - Topic clustering stability and centroid updates.
  - Personalization scoring blends and `why` signal emission.
  - Consolidation idempotence over overlapping event windows.

- Integration
  - RAG search with/without personalization; uplift in MRR@k.
  - Chat injection remains within token budget and improves judged relevance.
  - Opt-in/out and purge flows, including Chroma cleanup.
  - Usage-event logging smoke tests for TTS, web scraping, ebooks/documents/pdfs process endpoints.

- Fixtures/Mocks
  - Mock embeddings and LLM summarization for deterministic tests.
  - Use temporary per-test user DBs under `Databases/user_databases/<test_user>`.

## Metrics & Evaluation

- Retrieval: MRR@k, NDCG@k with and without personalization.
- Engagement: Click-through/top-3, dwell time, “usefulness” thumbs-up rate.
- Safety: Purge correctness and latency, token overhead in chat.

## Milestones

- Stage 1 (MVP)
  - Event logging, profile flags, simple RAG re-rank based on topic overlap.
  - Dashboard read-only view with topics and memories.

- Stage 2
  - Consolidation service, semantic memories, chat context builder, “why” signals.
  - Dashboard CRUD for memories and preferences.

- Stage 3
  - Metrics dashboard, project-scoped profiles, export/import of personalization data.

## Open Questions

- Default top-k memories to inject for chat without bloat?
- Per-project overrides in addition to global user profile?
- How to surface “why” without cluttering the UI?

## Risks & Mitigations

- Token bloat in chat → enforce strict memory caps and concise summaries.
- Privacy concerns → opt-in, purge, and clear data visibility/editing.
- Overfitting to recent interests → recency half-life configurable and visible.
