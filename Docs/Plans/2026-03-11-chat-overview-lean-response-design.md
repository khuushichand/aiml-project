# Chat Overview Lean Response Design

**Date:** 2026-03-11

**Goal:** Reduce avoidable work on `/api/v1/chats/` overview traffic without changing the default API contract for existing consumers.

## Problem

The sidebar overview path uses `/api/v1/chats/` and mainly reads chat identity and navigation fields such as title, topic label, state, and timestamps. The endpoint currently enriches every returned conversation with `message_count`, even for clients that never display it. That adds avoidable DB work on a hot path.

Separately, the dominant list/count queries for conversations rely on `client_id`, `deleted`, `character_id`, and `last_modified`, but the schema mostly has single-column indexes. That is acceptable at small scale and degrades predictably as histories grow.

## Recommended Approach

1. Add a backwards-compatible query flag to `/api/v1/chats/`:
   - `include_message_counts=true` by default
   - when `false`, skip message counting entirely and return `message_count=null`

2. Update the sidebar overview caller to pass `include_message_counts=false` for paged overview requests.

3. Add a small index migration for the stable conversation list patterns:
   - `(client_id, deleted, last_modified DESC)`
   - `(client_id, character_id, deleted, last_modified DESC)`
   - `(client_id, deleted, created_at DESC)` to support date-field fallbacks and future query reuse

## Why This Approach

- It keeps existing API behavior unchanged unless a client opts into the leaner mode.
- It targets the most obvious remaining waste on the chat overview path without creating a second response schema.
- It improves long-term stability with simple DB primitives instead of more caching or coordination logic.

## Non-Goals

- No new cache layer
- No second overview endpoint
- No broader response-shape split for search results
- No attempt to solve every remaining query plan issue in one pass

## Risks

- Existing consumers that actually need `message_count` must keep default behavior.
- Added indexes increase write cost slightly; the pass should stay small and tied to known query shapes.
- Older SQLite databases need a real schema migration, not just startup DDL.

## Verification

- Backend endpoint test proving `include_message_counts=false` skips both single and batched count helpers.
- Frontend hook test proving overview requests send the opt-out flag.
- SQLite migration/index test proving the new indexes exist after initialization/migration.
