# Media DB V2 Email Read Query Helper Rebinding Design

## Summary

Rebind the email read/query layer onto a package-owned runtime module so the
canonical `MediaDatabase` no longer owns the query parser, backend LIKE
adapter, search entrypoint, or detail entrypoint through legacy globals.
Preserve the existing endpoint-facing search/detail contracts while explicitly
deferring tenant-resolution, retention, and backfill coordinators.

## Scope

In scope:
- `_parse_email_operator_query(...)`
- `_email_like_clause(...)`
- `search_email_messages(...)`
- `get_email_message_detail(...)`
- direct ownership and compat-shell delegation regressions
- focused helper-path tests for parser, search, and detail semantics
- reuse of endpoint and email-native caller guards

Out of scope:
- `_resolve_email_tenant_id(...)`
- `_parse_email_relative_window(...)` as a class-owned helper
- `_sqlite_fts_literal_term(...)` as a class-owned helper
- `run_email_legacy_backfill_batch(...)`
- `run_email_legacy_backfill_worker(...)`
- `enforce_email_retention_policy(...)`
- `hard_delete_email_tenant_data(...)`
- `upsert_email_message_graph(...)`

## Why This Slice

This is the cleanest remaining bounded email cluster because the four in-scope
methods form one read/query layer:
- operator-query parsing
- backend-specific LIKE clause selection
- normalized email search with metrics and visibility filtering
- normalized email detail graph hydration

They already have strong caller coverage:
- [test_email_native_stage1.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_email_native_stage1.py)
  exercises operator filters, deleted/trash visibility, and detail graph
  hydration
- [test_email_search_endpoint.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaIngestion_NEW/integration/test_email_search_endpoint.py)
  pins the endpoint-facing search/detail contract
- [listing.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/api/v1/endpoints/media/listing.py)
  uses `search_email_messages(...)` as the operator-search bridge for media
  listing

By contrast, `_resolve_email_tenant_id(...)` is shared more broadly across the
email domain, and the backfill/retention methods are coordinator-heavy. Mixing
those into this slice would widen a coherent query move into a broader email
refactor.

## Existing Risks To Preserve

### 1. Search must keep the endpoint-facing contract

`search_email_messages(...)` is already the package boundary consumed by the
email endpoint and the media-search bridge. This tranche must preserve:
- `query`, `limit`, `offset`, and `include_deleted` semantics
- `tuple[list[dict[str, Any]], int]` return shape
- `InputError` on parse failures
- deterministic sort order

### 2. Query parsing must stay tolerant where intended

The current parser:
- rejects parentheses
- allows unknown `foo:bar` tokens to fall back to text search
- supports relative windows through private helper logic
- preserves OR-group and negation semantics

Those behaviors need direct helper-path tests so the move does not subtly
change parser behavior.

### 3. Search must preserve backend-specific behavior

The query path depends on:
- PostgreSQL `ILIKE`
- SQLite `LIKE ... COLLATE NOCASE`
- SQLite FTS literal term quoting for full-text assist
- tenant and deleted/trash filtering

Those semantics belong to the query layer and must remain unchanged.

### 4. Detail lookup must keep normalized graph shape

`get_email_message_detail(...)` currently returns:
- media/source envelopes
- grouped participants
- normalized label list
- attachment list
- parsed `raw_metadata`

It must also keep `None` behavior for missing or soft-deleted media unless
`include_deleted=True`.

## Implementation Shape

Add one package runtime module:
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/email_query_ops.py`

That module should own the four in-scope `MediaDatabase` methods only.

Important boundary choice:
- keep `_parse_email_relative_window(...)` and `_sqlite_fts_literal_term(...)`
  as module-local helper functions inside `email_query_ops.py`
- do not rebind them onto `MediaDatabase`

That keeps the runtime boundary coherent and avoids adding two new class-owned
helpers just to support the query module. It also keeps the normalized
ownership target aligned with what the counter measures.

Then:
- rebind the canonical methods in `media_database_impl.py`
- convert the legacy methods in `Media_DB_v2.py` into live-module compat shells

## Test Strategy

### Ownership / compat-shell regressions

Add direct regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:
- canonical ownership moved off legacy globals for:
  - `_parse_email_operator_query(...)`
  - `_email_like_clause(...)`
  - `search_email_messages(...)`
  - `get_email_message_detail(...)`
- legacy `Media_DB_v2` methods delegating through a live `import_module(...)`
  reference

Keep `_resolve_email_tenant_id(...)` and the module-local helper functions out
of the regression surface.

### Focused helper-path tests

Add a new helper test file covering:
- parser rejection of parentheses plus unknown-operator fallback token handling
- relative window parsing through the module-local helper path
- backend-specific LIKE clause selection
- search visibility filtering and SQLite FTS-assisted text search
- detail graph hydration and `include_deleted` behavior

### Broader caller-facing guards

Retain and reuse:
- [test_email_native_stage1.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_email_native_stage1.py)
- [test_email_search_endpoint.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaIngestion_NEW/integration/test_email_search_endpoint.py)
- [test_media_search_request_model.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_search_request_model.py)

The endpoint tests are compatibility guards, not the primary proof of canonical
rebinding.

## Success Criteria

- canonical ownership for the four in-scope methods moves off legacy globals
- all four legacy methods remain present as live-module compat shells
- focused helper-path tests pass
- broader email-native and endpoint guards stay green
- normalized ownership count drops from `101` to `97`
