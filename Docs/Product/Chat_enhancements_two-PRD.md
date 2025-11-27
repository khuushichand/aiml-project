# Chat Module Enhancements (Topics, States, Integrations) — PRD

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
- State validation: v0 enforces allowed set `{in-progress, resolved, backlog, non-viable}` on create/update; migration backfills all existing conversations with null/empty `state` to `in-progress` and sets a server-side default of `in-progress` for legacy clients that omit the field. Future v1.2 enables per-tenant state definitions but keeps the allowed set consistent until then.
- Filter/list by date range, state, topic/keyword, cluster, character; order by BM25, recency, hybrid (bm25+recency), or topic.
- Ranking semantics:
  - bm25: `bm25_norm = bm25_score / max_bm25_in_resultset` (cap at 1.0; if max=0 → 0); tie-breakers: higher `bm25_norm`, newer `last_modified`, then lower `conversation_id`/UUID lexical. Max BM25 is computed over the full filtered result set (pre-pagination) via a CTE/subquery to keep ordering stable across pages.
  - recency: `recency = exp(-age_days / half_life_days)`; defaults `half_life_days=14`; tie-breakers: newer `last_modified`, then lower `conversation_id`.
  - hybrid: `hybrid = w_bm25 * bm25_norm + w_recency * recency`; defaults `w_bm25=0.65`, `w_recency=0.35` (normalize weights if unset); tie-breakers same as bm25.
  - topic: sort by `topic_label` (casefold/locale-aware), then `bm25_norm`, then recency, then ID.
  - Fallbacks: if bm25 unavailable, treat `bm25_norm=0` so hybrid collapses to recency; if `last_modified` missing use `created_at`, else recency=0.
- Tree view endpoint returning conversation messages with parent/child structure; must support pagination/limit parameters with server-side caps (default page 200 messages, max 500) and optional depth limit for safety.
- Analytics endpoint returning histogram buckets by date/topic/state with daily or weekly bucket granularity; requires `start_date`/`end_date` and enforces a maximum range (default 180 days) plus server-side pagination for buckets; buckets are computed in UTC.
- Auto-tag: best-effort background job that sets topic keywords and `topic_label`; must be idempotent and skippable.
- Clustering: periodic job; write `cluster_id` on conversations; allow opt-out.
- Knowledge bank: save message/snippet to Note (and optional Flashcard) with backlinks to `conversation_id`/`message_id`.
- Integrations (v2; reuse existing connector modules):
  - Email: ingest threads as conversations; map Message-ID to `external_ref`; preserve subject → title; allow “send reply” that also appends a message.
  - Issue tracker (GitHub/GitLab/Jira-lite): webhook/poll to create/link conversations; sync `state` from issue status; allow posting a chat comment back. **Moved to v2.**
  - Notion/wiki: export summary or note; ingest selected pages into Notes for RAG; store page URL in `external_ref`. **Moved to v2.**
  - Connector tenant/user mapping and credential storage are deferred to v2; will rely on workflow-based instrumentation to bind inbound events to the correct tenant/user; v1 connectors stay feature-flagged and off until binding is configured.
- Permissions/auth: respect existing AuthNZ modes; per-user ChaChaNotes isolation; no cross-tenant leakage.

### Non-Functional
- Keep write paths async-safe; reuse optimistic locking already in ChaChaNotes.
- Search/ranking must fall back cleanly when embeddings or clustering are unavailable.
- Connectors must be optional and disabled by default; fail closed without credentials.
- Minimal migrations; preserve soft-delete semantics and FTS triggers.
- Add covering indexes for new filters (`state`, `cluster_id`, `last_modified`, `topic_label`) and update FTS/triggers as required (must-have to avoid list/search regressions).

## Data Model (ChaChaNotes)
- `conversations` add columns: `state` (TEXT; free-form string), `topic_label` (TEXT), `cluster_id` (TEXT/UUID), `source` (TEXT), `external_ref` (TEXT).
- `state` semantics: enforce v0 allowed set `{in-progress, resolved, backlog, non-viable}`; migration backfills all existing rows with null/empty `state` to `in-progress`, sets a server/default of `in-progress` for create paths that omit state (legacy clients), and keeps transitions open between all states. Future v1.2 will add configurable per-tenant state definitions via a dedicated state keyword field for chat conversations while preserving analytics continuity.
- Topic/keyword/cluster semantics: `topic_label` is a single human-readable label summarizing the primary topic of the conversation (auto-tagger writes this; users can override). Existing `keywords` remain many-to-many tags used for search and filters. `cluster_id` is an opaque group identifier assigned by the clustering job; multiple conversations may share a `cluster_id` and it is mainly used for navigation and analytics.
- Continue to use `keywords` + `conversation_keywords` for topics/tags; no new table required.
- Keep `parent_conversation_id` and `parent_message_id` for tree rendering.
- Cluster metadata (title/centroid/stats) is persisted in ChaChaNotes (e.g., `conversation_clusters` table with columns: `cluster_id` [PK], `title`, `centroid` [JSON], `size`, `created_at`, `updated_at`). This makes cluster filters and navigation stable across sessions.
- Backlinks for knowledge bank: Notes currently lack `conversation_id`/`message_id`; add both columns (with indexes) via migration so knowledge-save can write backlinks, and wire to conversation/message IDs for navigation.

## API Surface (proposed)
- `GET /api/v1/chat/conversations`: filters (date range, state, cluster_id, keyword/topic, character_id), `order_by` (`bm25|recency|hybrid|topic`), pagination.
- `PATCH /api/v1/chat/conversations/{id}`: set `state`, `topic_label`, `keywords`, `cluster_id`, `external_ref`, `source`; optimistic locking via `version`.
- `GET /api/v1/chat/conversations/{id}/tree`: returns conversation metadata + message tree (parent/children) with pagination/limit and depth cap.
- `GET /api/v1/chat/analytics`: returns histogram buckets grouped by date/topic/state; accepts `start_date`, `end_date`, and `bucket_granularity` (`day|week`); enforces max date range (default 180 days) and bucket count limits.
- `POST /api/v1/chat/knowledge/save`: input `conversation_id`, `message_id`, `snippet`, `tags`, `make_flashcard?`, `export_to` (`notion|wiki|none`); output Note/Flashcard IDs.
- Connectors (v2; reuse existing connector modules; feature-flagged off in v1):
  - `POST /api/v1/chat/connectors/email/inbound`: consume parsed email payload → conversation/messages.
  - `POST /api/v1/chat/connectors/email/send`: reply and append to conversation.
  - `POST /api/v1/chat/connectors/issue/webhook`: accept issue events → create/link/update conversation state.
  - `POST /api/v1/chat/connectors/issue/comment`: post a message as issue comment.
  - `POST /api/v1/chat/connectors/notion/export`: push summary/note to page.
  - `POST /api/v1/chat/connectors/notion/ingest`: pull selected pages into Notes.
- Connector endpoints remain disabled until v2; they are gated by `CHAT_CONNECTORS_V2_ENABLED` (default: false) and tenant-binding readiness.
- MCP: mirror state/filter/search in `chats_module.py`; expose analytics summary.

## UX Notes (WebUI/Next)
- Conversation list: chips for state/topic; toggle ranking (bm25/recency/hybrid); quick filters for “needs attention” (in-progress/backlog).
- Detail view: tree toggle; right-rail showing metadata, linked issue/email, knowledge-bank saves.
- Knowledge bank CTA on hover of message → “Save snippet” + “Add flashcard”.
- Analytics tab: stacked histogram by state, topic filters.
- Integrations: small badges for source (email/issue/notion/wiki) and link-out icons.

## Background Jobs
- Auto-tagger: runs only on manual trigger or after 3+ new messages have been added since the last tag; uses summary + classifier; writes keywords and `topic_label`; manual labels remain sticky (auto-tag skips overwriting unless forced).
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
- Performance: FTS + new filters could regress; cap pagination and add covering indexes on `state`, `cluster_id`, `last_modified` (must-have).
- Connector reliability: sandbox behind feature flags; retries with backoff; store dead-letter payloads optionally.
- Data leakage: ensure per-user DB scoping; never fetch cross-tenant even in analytics; enforce AuthNZ in connectors.
- Topic/cluster quality: best-effort; allow manual overrides; expose “clear cluster/topic” to users.

## Rollout Plan
- Phase 1 (MVP): schema migration (including backfill to `in-progress` state and note backlinks), listing filters/order, state changes, tree endpoint, analytics buckets (UTC), knowledge-save to Notes/Flashcards (local only); docs + tests.
- Phase 2: auto-tagging job; clustering job; cluster filter; UI badges.
- Phase 3 (v2): connectors (email, issue, Notion/wiki) behind feature flags; reply/comment flows; RAG ingest toggle.

## Implementation Plan (added detail)
- Migration plan (ChaChaNotes):
  - SQLite: add columns if missing, backfill `state` where null/'' to `in-progress`, set default `in-progress` on `conversations.state`, add `conversation_id`/`message_id` to `notes` with indexes, and add covering indexes on `state`, `cluster_id`, `last_modified`, `topic_label`.
  - Postgres (if used): same columns/defaults/backfill; ensure concurrent index creation to avoid locks.
- API/backfill behavior: ensure create/update paths use `in-progress` default when omitted and reject values outside the allowed set.
- Feature flags: leave email/issue/Notion endpoints disabled until v2; gate by config/flag and tenant-binding readiness.
- UX copy: update any UI labels/tooltips to use “in-progress” and note connectors as “coming in v2.”
- Testing to add when implementing: migration tests for both backends; ordering test confirming global BM25 normalization across pages; knowledge-save writing backlinks; filters hitting new indexes.

## Open Questions
- None (current set resolved; revisit after Phase 1 validation).
