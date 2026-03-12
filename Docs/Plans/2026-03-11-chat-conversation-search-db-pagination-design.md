# Chat Conversation Search DB Pagination Design

Date: 2026-03-11
Owner: Codex collaboration session
Status: Approved (design)

## Context and Problem

The lazy-hydration redesign removed most `/chat` mount-time burst traffic, but `/api/v1/chats/conversations` still materializes the full filtered conversation result set in Python and only then paginates.

Current behavior in [`tldw_Server_API/app/api/v1/endpoints/chat.py`](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-chat-rate-limit-lazy-hydration/tldw_Server_API/app/api/v1/endpoints/chat.py) is:

- call `db.search_conversations(...)` to fetch every filtered row
- compute recency and hybrid ranking in Python
- sort in Python
- slice `limit` and `offset` in Python

That leaves one remaining request hotspot for large chat histories and makes the new `character_scope` filter less effective than it should be.

## Goals

1. Make `/api/v1/chats/conversations` fully DB-paginated for all supported sort modes.
2. Preserve current endpoint ordering semantics, including hybrid and topic modes.
3. Preserve global `bm25_norm` semantics across the full filtered result set, even when only one page is returned.
4. Keep the existing full-list `search_conversations(...)` helper unchanged for non-endpoint callers.
5. Keep SQLite and PostgreSQL behavior aligned.

## Non-Goals

1. Rewriting analytics or conversation-enrichment workflows to use paginated search.
2. Removing the existing full-list search helpers.
3. Changing the public `/api/v1/chats/conversations` response shape.
4. Eliminating the extra aggregate query required for global BM25 normalization.

## User Decisions Captured During Brainstorming

1. `bm25_norm` must keep current global normalization semantics.
2. One extra aggregate query per search is acceptable if it avoids full materialization in Python.
3. The current ranking and filter behavior should be preserved rather than simplified.

## Design Summary

Add a new endpoint-specific DB helper, `search_conversations_page(...)`, in [`tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-chat-rate-limit-lazy-hydration/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py).

This helper will:

- reuse the same validated filter semantics as `search_conversations(...)`
- accept request-scoped `as_of` time, `order_by`, `limit`, and `offset`
- return the requested page rows plus global metadata needed by the endpoint

The endpoint in [`tldw_Server_API/app/api/v1/endpoints/chat.py`](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-chat-rate-limit-lazy-hydration/tldw_Server_API/app/api/v1/endpoints/chat.py) will stop sorting and paginating in Python and instead format the page returned by the DB helper.

## Architecture

### Keep Existing Full-List Search Intact

[`search_conversations(...)`](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-chat-rate-limit-lazy-hydration/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py) is still used by:

- analytics aggregation in [`chat.py`](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-chat-rate-limit-lazy-hydration/tldw_Server_API/app/api/v1/endpoints/chat.py)
- clustering and enrichment flows in [`conversation_enrichment.py`](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-chat-rate-limit-lazy-hydration/tldw_Server_API/app/core/Chat/conversation_enrichment.py)

Those callers rely on the current “return all filtered rows” contract. To avoid semantic drift, the new pagination behavior lives in a separate helper.

### New Paginated Search Helper

Add `search_conversations_page(...)` with a shape equivalent to:

- inputs: current filters, `order_by`, `limit`, `offset`, `as_of`
- outputs: `rows`, `total`, `max_bm25`

`rows` remain plain conversation dictionaries plus ranking fields used by the endpoint. `total` is the full filtered count. `max_bm25` is the global BM25 maximum for normalization when applicable.

### Shared Filter Construction

The new paginated helper must not duplicate filter semantics by hand. Reuse a shared backend-specific filter builder so these stay aligned across:

- `search_conversations(...)`
- `search_conversations_page(...)`
- SQLite
- PostgreSQL

Shared filters include:

- `client_id`
- `character_id`
- `character_scope`
- state
- topic label and prefix
- cluster id
- keywords
- date range
- text query

## Data Flow

### Request-Scoped Time Anchor

The endpoint computes one `as_of = datetime.now(timezone.utc)` value and passes it to the DB helper.

That same bound value is used in both:

- the aggregate query
- the page query

This avoids drift between recency and hybrid ranking calculations when two queries run back-to-back.

### Aggregate Query Rules

The helper performs an aggregate query over the full filtered candidate set to compute:

- `COUNT(*)` always
- `MAX(bm25_raw)` only when a text query is present and the ordering path needs global BM25 normalization

The aggregate BM25 query is required only when:

- `order_by=bm25`
- `order_by=hybrid`
- `order_by=topic` with a text query present

It is skipped for:

- `order_by=recency`
- no-query `bm25`
- no-query `hybrid`
- no-query `topic`

### Page Query Rules

The page query returns only `limit` rows starting at `offset`, with SQL-side ordering for all supported modes.

Supported sort behavior:

- `bm25`
  - with text query: order by `bm25_raw DESC`, then recency timestamp DESC, then `id`
  - without text query: explicitly fall back to recency ordering
- `recency`
  - order by computed recency DESC, then timestamp DESC, then `id`
- `hybrid`
  - compute `(normalized_bm25 * w_bm25) + (recency * w_recency)` in SQL
  - without text query, this naturally reduces to recency ordering
- `topic`
  - order by normalized topic label ASC with null-like values last
  - then BM25 when query is present
  - then recency
  - then `id`

### Topic Label Null Handling

Topic ordering must preserve current Python behavior:

- `NULL` labels sort last
- blank or whitespace-only labels also sort last

The SQL path therefore treats `NULLIF(TRIM(topic_label), '')` as the effective topic sort key.

## Ranking Semantics

### Recency

Recency remains exponential decay using the same semantics currently implemented in Python:

- age is based on `as_of - conversation_timestamp`
- half-life remains `RECENCY_HALF_LIFE_DAYS`
- missing timestamps produce a zero recency contribution

### BM25 Normalization

`bm25_norm` must remain global to the full filtered result set, not page-local.

This means page 2 of a search returns the same `bm25_norm` values the same rows would have if page 1 had also been fetched.

### Tie-Breaking

Every DB ordering path must end with a stable `id` tie-breaker so repeated requests remain deterministic.

## Endpoint Changes

[`list_chat_conversations(...)`](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-chat-rate-limit-lazy-hydration/tldw_Server_API/app/api/v1/endpoints/chat.py) changes from:

- full-list fetch
- Python ranking
- Python sort
- Python pagination

to:

- compute request-scoped `as_of`
- call `db.search_conversations_page(...)`
- use returned `rows`, `total`, and ranking fields directly
- fetch keywords and message counts only for page rows

The response schema does not change.

## Error Handling

Validation behavior must remain unchanged:

- invalid `character_scope` or `date_field` still returns `400`
- incompatible `character_scope=non_character` plus `character_id` still returns `400`
- invalid `order_by` remains rejected by FastAPI query validation

If the aggregate or page query fails, the endpoint returns a single failure response rather than mixing partial aggregate data with fresh rows.

## Testing Strategy

### DB-Level Tests

Add paged-search tests that prove:

1. page 2 preserves the same global `bm25_norm` values as the full filtered result set
2. `bm25` without a text query falls back to recency ordering
3. topic ordering treats null and blank labels as the same null-like bucket
4. `total` reflects the full filtered set while `rows` contains only the requested page

### Endpoint Tests

Add endpoint tests that prove:

1. `/api/v1/chats/conversations?limit=1&offset=1` returns only the second ranked row
2. `pagination.total` still reflects the full filtered count
3. `character_scope` remains effective under paginated search
4. `hybrid` and `topic` ordering remain deterministic on ties

### Regression Focus

The critical regression to prevent is reintroducing full Python-side materialization. Tests should exercise the new paged helper rather than only verifying the old full-list helper.

## Risks and Trade-Offs

### Accepted Trade-Off

Search with text query may now use two SQL queries instead of one:

- one aggregate query
- one page query

That is acceptable because it replaces unbounded Python-side materialization and keeps global BM25 normalization intact.

### Residual Risk

The query logic becomes more complex, especially for keeping SQLite and PostgreSQL aligned. That is why filter construction and ordering expressions must be centralized rather than copied between helpers.

## Success Criteria

This design is successful when:

1. `/api/v1/chats/conversations` no longer materializes full result sets in Python before pagination.
2. Search result ordering matches current behavior for `bm25`, `recency`, `hybrid`, and `topic`.
3. `bm25_norm` stays globally normalized across pages.
4. The existing non-endpoint full-list workflows remain unchanged.
