# Chat Module Enhancements (Topics, States, Integrations) — PRD

## Table of Contents
- [Overview](#overview)
- [Requirements](#requirements)
- [Data Model (ChaChaNotes)](#data-model-chachanotes)
- [API Surface (proposed)](#api-surface-proposed)
- [Rollout Plan](#rollout-plan)
- [Implementation Plan](#implementation-plan)

## Overview
- Purpose: expand chat to support topic classification, flexible ranking, visual tree/histogram views, and integrations (email, issue trackers, Notion/wiki) while reusing ChaChaNotes storage and existing RAG/search primitives.
- Audience: product, backend, WebUI/Next, infra.
- Target release: staged; first tranche delivers metadata/state/search upgrades, followed by analytics, clustering, and connectors.

## Goals
- Faster retrieval and triage with topic/date filters and ranked search.
- Make chat navigable (thread tree view) and measurable (histograms/analytics).
- Enable lifecycle states (resolved/in-progress/non-viable/backlog) for conversations.
- Provide a knowledge bank workflow to capture learnings and reuse Notes/Flashcards.
- Integrate external channels (email, issue trackers, Notion/wiki) without forking storage.

## Non-Goals
- Replacing core chat pipeline or RAG.
- Introducing new primary databases (stay on ChaChaNotes + Chroma).
- Building full-featured email/issue clients; focus on ingest/link + selective reply/export.

## Users & Use Cases
- Support: triage customer conversations, link to issue, mark resolved, export summary.
- Researcher/engineer: cluster by topic, search by recency or BM25, bookmark snippets to knowledge bank, push summaries to wiki/Notion.
- Ops/analytics: volume over time per topic/state; spot clusters.

## Scope (What/When)
1) **Foundational metadata & search** (MVP): new conversation fields, filters, ranking modes, state changes, topic tagging via keywords; tree fetch; basic analytics endpoint.
2) **Auto-topic + clustering**: async tagging pipeline using existing embeddings; optional cluster IDs for grouping and navigation.
3) **Connectors (v2)**: inbound email → conversation; issue tracker webhooks; Notion/wiki export + page ingest; reply-to-email/issue comments (deferred to v2; reuse existing connector modules).
4) **Knowledge bank UX**: “save snippet” → Note/Flashcard with backlinks

## Requirements
### Functional
- Existing chat completion/streaming APIs remain unchanged; new metadata is optional on conversation create/update and conversation search now also returns `bm25_norm` alongside ordering (no change to message response payloads).
- Create/update conversations with `state`, `topic_label`, `source`, `external_ref`, `cluster_id`; defaults are backward compatible.
- Auto-tag metadata fields (`topic_label_source`, `topic_last_tagged_at`, `topic_last_tagged_message_id`) are server-managed and not required in client requests.
- State validation: v0 enforces allowed set `{in-progress, resolved, backlog, non-viable}` on create/update; migration backfills all existing conversations with null/empty `state` to `in-progress` and sets a server-side default of `in-progress` for legacy clients that omit the field. Future v1.2 enables per-tenant state definitions but keeps the allowed set consistent until then.
- Filter/list by date range (default `last_modified`, fallback `created_at`), state, topic/keyword, cluster, character; order by BM25, recency, hybrid (bm25+recency), or topic. Optional `date_field=last_modified|created_at` can be added later.
- Ranking semantics:
  - bm25: `bm25_norm = bm25_score / max_bm25_in_resultset` (cap at 1.0; if max=0 → 0); tie-breakers: higher `bm25_norm`, newer `last_modified`, then lower `conversation_id`/UUID lexical. Max BM25 is computed over the full filtered result set (pre-pagination) via a CTE/subquery to keep ordering stable across pages.
  - recency: `recency = exp(-age_days / half_life_days)`; defaults `half_life_days=14`; age uses `last_modified` (fallback `created_at`); tie-breakers: newer `last_modified`, then lower `conversation_id`.
  - hybrid: `hybrid = w_bm25 * bm25_norm + w_recency * recency`; defaults `w_bm25=0.65`, `w_recency=0.35` (normalize weights if unset); tie-breakers same as bm25.
  - topic: sort by `topic_label` (casefold/locale-aware), nulls last, then `bm25_norm`, then recency, then ID.
  - Fallbacks: if bm25 unavailable, treat `bm25_norm=0` so hybrid collapses to recency; if `last_modified` missing use `created_at`, else recency=0.
- Tree view endpoint returning conversation messages with parent/child structure; paginate by root thread (root messages as the unit). Each page includes full subtrees for the returned roots, with server-side caps (default page 200 messages, max 500) and optional depth limit for safety. If a cap truncates a subtree, include a `truncated=true` indicator and never return children without their parents.
- Analytics endpoint returning histogram buckets by date/topic/state with daily or weekly bucket granularity; `date` is based on `last_modified` (fallback `created_at`); requires `start_date`/`end_date` and enforces a maximum range (default 180 days) plus server-side pagination for buckets; buckets are computed in UTC.
- Auto-tag: best-effort background job that sets topic keywords and `topic_label`; must be idempotent and skippable (see auto-tag metadata fields).
- Clustering: periodic job; write `cluster_id` on conversations; allow opt-out.
- Knowledge bank: save message/snippet to Note (and optional Flashcard) with backlinks to `conversation_id`/`message_id` on both Notes and Flashcards.
- Integrations (v2; reuse existing connector modules):
  - Email: ingest threads as conversations; map Message-ID to `external_ref`; preserve subject → title; allow “send reply” that also appends a message.
  - Issue tracker (GitHub/GitLab/Jira-lite): webhook/poll to create/link conversations; sync `state` from issue status; allow posting a chat comment back. **Moved to v2.**
  - Notion/wiki: export summary or note; ingest selected pages into Notes for RAG; store page URL in `external_ref`. **Moved to v2.**
  - Connector tenant/user mapping and credential storage are deferred to v2; will rely on workflow-based instrumentation to bind inbound events to the correct tenant/user; v1 connectors stay feature-flagged and off until binding is configured.
- Connector idempotency: `external_ref` uniqueness is scoped per tenant/user; duplicates should merge into the existing conversation.
- Permissions/auth: respect existing AuthNZ modes; per-user ChaChaNotes isolation; no cross-tenant leakage.

### Non-Functional
- Keep write paths async-safe; reuse optimistic locking already in ChaChaNotes.
- Search/ranking must fall back cleanly when embeddings or clustering are unavailable.
- Connectors must be optional and disabled by default; fail closed without credentials.
- Minimal migrations; preserve soft-delete semantics and FTS triggers.
- Add covering indexes for new filters (`state`, `cluster_id`, `last_modified`, `topic_label`) plus `source, external_ref` for idempotent connector lookups, and update FTS/triggers as required (must-have to avoid list/search regressions).

## Data Model (ChaChaNotes)
- `conversations` add columns: `state` (TEXT; free-form at DB level), `topic_label` (TEXT), `cluster_id` (TEXT/UUID), `source` (TEXT), `external_ref` (TEXT), `topic_label_source` (TEXT; `manual|auto`), `topic_last_tagged_at` (DATETIME), `topic_last_tagged_message_id` (TEXT/UUID).
- `state` semantics: enforce v0 allowed set `{in-progress, resolved, backlog, non-viable}` at the API/schema level; migration backfills all existing rows with null/empty `state` to `in-progress`, sets a server/default of `in-progress` for create paths that omit state (legacy clients), and keeps transitions open between all states. Future v1.2 will add configurable per-tenant state definitions via a dedicated state keyword field for chat conversations while preserving analytics continuity.
- Topic/keyword/cluster semantics: `topic_label` is a single human-readable label summarizing the primary topic of the conversation (auto-tagger writes this; users can override). Existing `keywords` remain many-to-many tags used for search and filters. `cluster_id` is an opaque group identifier assigned by the clustering job; multiple conversations may share a `cluster_id` and it is mainly used for navigation and analytics. Topic filter uses `topic_label` (exact or prefix match; nulls excluded unless requested); keyword filter uses existing `keywords` semantics.
- Continue to use `keywords` + `conversation_keywords` for topics/tags; no new table required.
- Keep `parent_conversation_id` and `parent_message_id` for tree rendering.
- Cluster metadata (title/centroid/stats) is persisted in ChaChaNotes (e.g., `conversation_clusters` table with columns: `cluster_id` [PK], `title`, `centroid` [JSON], `size`, `created_at`, `updated_at`). This makes cluster filters and navigation stable across sessions.
- Backlinks for knowledge bank: Notes and Flashcards currently lack `conversation_id`/`message_id`; add both columns (with indexes) via migration so knowledge-save can write backlinks, and wire to conversation/message IDs for navigation.

## API Surface (proposed)
- `GET /api/v1/chat/conversations`: filters (`query` search term, date range using `last_modified` by default, state, cluster_id, `topic_label`, `keywords`, character_id), `order_by` (`bm25|recency|hybrid|topic`), pagination. Optional `date_field=last_modified|created_at` and `include_null_topic=true|false` can be added later.
- `PATCH /api/v1/chat/conversations/{id}`: set `state`, `topic_label`, `keywords`, `cluster_id`, `external_ref`, `source`; optimistic locking via `version`.
- `GET /api/v1/chat/conversations/{id}/tree`: returns conversation metadata + message tree (parent/children) paginated by root threads, with limit and depth cap; includes `truncated` when a subtree is capped.
- `GET /api/v1/chat/analytics`: returns histogram buckets grouped by date/topic/state; accepts `start_date`, `end_date`, and `bucket_granularity` (`day|week`); enforces max date range (default 180 days) and bucket count limits.
- `POST /api/v1/chat/knowledge/save`: input `conversation_id`, `message_id`, `snippet`, `tags`, `make_flashcard?`, `export_to` (`notion|wiki|none`); output Note/Flashcard IDs. If `export_to` is set while connectors are disabled, return `export_status=skipped_disabled` and still create local Note/Flashcard.
- Connectors (v2; reuse existing connector modules; feature-flagged off in v1):
  - `POST /api/v1/chat/connectors/email/inbound`: consume parsed email payload → conversation/messages.
  - `POST /api/v1/chat/connectors/email/send`: reply and append to conversation.
  - `POST /api/v1/chat/connectors/issue/webhook`: accept issue events → create/link/update conversation state.
  - `POST /api/v1/chat/connectors/issue/comment`: post a message as issue comment.
  - `POST /api/v1/chat/connectors/notion/export`: push summary/note to page.
- `POST /api/v1/chat/connectors/notion/ingest`: pull selected pages into Notes.
- Connector endpoints remain disabled until v2; they are gated by `CHAT_CONNECTORS_V2_ENABLED` (default: false) and tenant-binding readiness.
- MCP: mirror state/filter/search in `chats_module.py`; expose analytics summary.

### API Parameter Glossary (proposed)
- `query`: search term for BM25/FTS; named consistently with existing chat message and character search endpoints.
- `date_field`: `last_modified|created_at`; default `last_modified`; if `last_modified` is null fallback to `created_at`.
- `topic_label`: filters by conversation `topic_label` (casefold; exact or prefix match); nulls excluded unless `include_null_topic=true`.
- `include_null_topic`: include conversations with empty or null `topic_label` (default false).
- `keywords`: repeatable query parameter (`?keywords=foo&keywords=bar`) aligned with existing tag filters; uses existing `conversation_keywords` semantics.

## UX Notes (WebUI/Next)
- Conversation list: chips for state/topic; toggle ranking (bm25/recency/hybrid); quick filters for “needs attention” (in-progress/backlog).
- Detail view: tree toggle; right-rail showing metadata, linked issue/email, knowledge-bank saves.
- Knowledge bank CTA on hover of message → “Save snippet” + “Add flashcard”.
- Analytics tab: stacked histogram by state, topic filters.
- Integrations: small badges for source (email/issue/notion/wiki) and link-out icons.

## Background Jobs
- Auto-tagger: runs only on manual trigger or after 3+ new messages have been added since `topic_last_tagged_message_id`; uses summary + classifier; writes keywords and `topic_label`. Manual labels set `topic_label_source=manual` and remain sticky (auto-tag skips overwriting unless forced); auto-tag writes `topic_label_source=auto`. Idempotency is tracked via `topic_last_tagged_message_id` and `topic_label_source`.
- Clustering worker: periodic; fetch embeddings (latest summary), run HDBSCAN/k-means; write `cluster_id`; mark clusters with representative titles; allow “unclustered” fallback; triggered after auto-tag runs or when explicitly requested; persists cluster metadata for navigation.
- Connector sync (v2): email polling (if IMAP/SMTP), issue webhook receiver, Notion ingest tasks; all best-effort and idempotent; reuse existing connector modules.

## Success Metrics (testing-only)
- These metrics are used only for local testing/QA and manual evaluation; this feature does not add any new production telemetry or external analytics.
- Time-to-find: median search latency and result click depth (proxy via top-k position).
- Coverage: % conversations with state; % with topic tags; % clustered.
- Resolution: MTTR per state/issue-linked conversations.
- Knowledge reuse: # snippets saved; # retrieved in RAG answers.
- Reliability: connector error rates; job failure counts; DB contention incidents.

## Dependencies & Reuse
- Storage: ChaChaNotes DB + existing keywords/FTS; Chroma for embeddings.
- Services: `chat_service`, `chat_helpers`, `chat_history`, `notes.py`, `flashcards.py`, `rag_unified`, `connectors.py` patterns.
- AuthNZ/rate limit: reuse API deps; guard new endpoints with existing decorators.
- Config knobs: `half_life_days` (float, default 14), `w_bm25` (default 0.65), `w_recency` (default 0.35) normalized to sum~1; expose via config.txt/env.

## Risks & Mitigations
- Schema churn: keep migration small; default nulls; add indices for new filters.
- Performance: FTS + new filters could regress; cap pagination and add covering indexes on `state`, `cluster_id`, `last_modified` (must-have). BM25 normalization over full filtered sets can be expensive; mitigate with DB-side CTEs, caching, or configurable cap/window when needed.
- Connector reliability: sandbox behind feature flags; retries with backoff; store dead-letter payloads optionally.
- Data leakage: ensure per-user DB scoping; never fetch cross-tenant even in analytics; enforce AuthNZ in connectors.
- Topic/cluster quality: best-effort; allow manual overrides; expose “clear cluster/topic” to users.

## Rollout Plan
- Phase 1 (MVP): schema migration (including backfill to `in-progress` state and note/flashcard backlinks), listing filters/order, state changes, tree endpoint, analytics buckets (UTC), knowledge-save to Notes/Flashcards (local only); docs + tests.
- Phase 2: auto-tagging job; clustering job; cluster filter; UI badges.
- Phase 3 (v2): connectors (email, issue, Notion/wiki) behind feature flags; reply/comment flows; RAG ingest toggle.

## Implementation Plan (added detail)
- Migration plan (ChaChaNotes):
  - SQLite: add columns if missing (including `topic_label_source`, `topic_last_tagged_at`, `topic_last_tagged_message_id`), backfill `state` where null/'' to `in-progress`, set default `in-progress` on `conversations.state`, add `conversation_id`/`message_id` to `notes` and `flashcards` with indexes, create `conversation_clusters`, and add covering indexes on `state`, `cluster_id`, `last_modified`, `topic_label`, plus `(source, external_ref)` for idempotent connector lookups (per-user DB; include tenant/user scope if stored).
  - Postgres (if used): same columns/defaults/backfill; ensure concurrent index creation to avoid locks.
- API/backfill behavior: ensure create/update paths use `in-progress` default when omitted and reject values outside the allowed set.
- Feature flags: leave email/issue/Notion endpoints disabled until v2; gate by config/flag and tenant-binding readiness.
- UX copy: update any UI labels/tooltips to use “in-progress” and note connectors as “coming in v2.”
- Testing to add when implementing: migration tests for both backends; ordering test confirming global BM25 normalization across pages; knowledge-save writing backlinks; filters hitting new indexes.

## Open Questions
- None (current set resolved; revisit after Phase 1 validation).

## Implementation Plan
## Stage 1: Schema & Data Model
**Goal**: Add required ChaChaNotes schema changes and indexes with safe defaults and backfills.
- Conversations: add `state`, `topic_label`, `cluster_id`, `source`, `external_ref`, `topic_label_source`, `topic_last_tagged_at`, `topic_last_tagged_message_id`.
- Notes/Flashcards: add `conversation_id` and `message_id` backlink columns.
- Clusters: create `conversation_clusters` table for metadata persistence.
- Indexes: `state`, `cluster_id`, `last_modified`, `topic_label`, `(source, external_ref)` (non-unique lookup only), and backlink indexes. Dedup uses app-level merge logic, not DB uniqueness.
- FTS/triggers: update only if needed to preserve search parity and soft-delete semantics.
**Success Criteria**: Migrations apply idempotently on SQLite and Postgres; defaults/backfills set `state` to `in-progress`; new columns and indexes are visible via schema introspection; legacy clients continue to work with null-safe columns.
**Tests**: Migration/backfill tests (SQLite/Postgres); index presence or explain-plan checks for new filters; note/flashcard backlink column validation on create/update.
**Status**: Not Started

## Stage 2: Core APIs (List/Update/Tree/Analytics/Knowledge Save)
**Goal**: Implement Phase 1 endpoints and semantics (filters, ranking, tree pagination, analytics buckets, knowledge-save).
- `GET /api/v1/chat/conversations`: filters (`query`, date range, `state`, `topic_label`, `keywords`, `cluster_id`, `character_id`), optional `date_field`, `order_by=bm25|recency|hybrid|topic`, pagination via `limit`/`offset` (align with existing list endpoints).
- `PATCH /api/v1/chat/conversations/{id}`: validate `state`, apply default `in-progress` when omitted, optimistic locking via `version`.
- `GET /api/v1/chat/conversations/{id}/tree`: paginate by root threads, enforce depth cap, message caps (default 200, max 500), return `truncated` when caps apply.
- `GET /api/v1/chat/analytics`: UTC buckets (day/week), max range, date based on `last_modified` fallback to `created_at`.
- `POST /api/v1/chat/knowledge/save`: write backlinks to Notes/Flashcards; return `export_status=skipped_disabled` when connectors are off.
**Success Criteria**: BM25 normalization uses full filtered set pre-pagination; ordering stable across pages; recency uses `last_modified` fallback to `created_at`; tree never returns orphaned children; analytics buckets respect UTC and max-range limits; `bm25_norm` returned without changing chat completion payloads.
**Tests**: BM25 ordering + pagination stability test; recency fallback test; tree integrity + truncation test; analytics bucket range test; knowledge-save backlink test (notes + flashcards) including `export_status` when connectors disabled.
**Status**: Not Started

## Stage 3: Auto-Tagging & Clustering (Phase 2)
**Goal**: Implement background jobs for auto-tagging and clustering with idempotency metadata.
- Auto-tag triggers after 3+ new messages since `topic_last_tagged_message_id` or manual trigger; writes `topic_label_source` and `topic_last_tagged_message_id`.
- Manual labels set `topic_label_source=manual` and are preserved unless forced.
- Clustering worker assigns `cluster_id`, persists `conversation_clusters` metadata, supports opt-out and "unclustered" fallback.
**Success Criteria**: Auto-tag is idempotent and skips unchanged conversations; manual overrides persist; clustering writes stable `cluster_id` values and metadata for navigation.
**Tests**: Auto-tag idempotency + manual override tests; clustering persistence test; opt-out/unclustered handling test.
**Status**: Not Started

## Stage 4: WebUI & Docs Alignment
**Goal**: Update WebUI to surface new filters, ranking, tree view, and analytics; align docs with final API params.
- Conversation list: state/topic chips, `bm25|recency|hybrid|topic` toggle, date filters.
- Detail view: tree toggle, metadata rail, knowledge-save actions.
- Analytics tab: histogram buckets with topic/state filters.
- Docs: update API docs for new endpoints/params and glossary (`query`, `keywords`, `date_field`, `include_null_topic`).
**Success Criteria**: UI exposes new filters and ranking modes; tree view matches root-thread pagination; analytics matches API buckets; docs reflect defaults and param naming.
**Tests**: UI smoke test for list/detail/analytics; OpenAPI/docs examples validate against schema.
**Status**: Not Started

## Deferred Scope
**Note**: v2 connectors (email/issue/Notion) are intentionally out-of-scope for this plan and will be captured in a separate Phase 3 plan.
