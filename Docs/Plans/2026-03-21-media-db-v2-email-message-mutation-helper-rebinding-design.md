# Media DB V2 Email Message Mutation Helper Rebinding Design

## Summary

Rebind the email message mutation helper layer onto a package-owned runtime
module so the canonical `MediaDatabase` no longer owns those methods through
legacy globals. Preserve the existing worker-facing delta and delete-state
contracts, while explicitly deferring the broader email read/query surface that
still owns parser and SQL-assembly behavior.

## Scope

In scope:
- `_normalize_email_label_values(...)`
- `_resolve_email_message_row_for_source_message(...)`
- `apply_email_label_delta(...)`
- `reconcile_email_message_state(...)`
- direct ownership and compat-shell delegation regressions
- focused helper-path tests for label-delta and delete-state semantics
- reuse of broader email-native and connectors-worker guards

Out of scope:
- `search_email_messages(...)`
- `_parse_email_operator_query(...)`
- `_email_like_clause(...)`
- `get_email_message_detail(...)`
- `_resolve_email_tenant_id(...)`
- `upsert_email_message_graph(...)`
- `enforce_email_retention_policy(...)`
- `hard_delete_email_tenant_data(...)`

## Why This Slice

This is the cleanest remaining bounded email cluster because the four methods
form one coherent mutation layer:
- label normalization for inbound provider deltas
- message-row resolution by tenant/source/message key
- label-mapping mutation and FTS label-text refresh
- delete-state reconciliation through the existing media lifecycle seam

It is also already well covered:
- [test_email_native_stage1.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_email_native_stage1.py)
  directly exercises label-delta updates and delete-state reconciliation
- [test_policy_and_connectors.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/External_Sources/test_policy_and_connectors.py)
  pins the connectors worker’s instance-method contracts for both mutation
  entrypoints
- [connectors_worker.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/services/connectors_worker.py)
  already uses these methods as a delta-first fast path before falling back to
  full fetch/upsert

By contrast, `search_email_messages(...)` and `get_email_message_detail(...)`
pull in the wider read/query surface, including parser helpers and large SQL
assembly. Mixing those into this slice would turn a narrow mutation extraction
into a broader query-domain refactor.

## Existing Risks To Preserve

### 1. Worker-facing instance seams must remain intact

The connectors worker checks only for and calls instance methods:
- `apply_email_label_delta(...)`
- `reconcile_email_message_state(...)`

This tranche must preserve those names, signatures, and return shapes while
moving canonical ownership off legacy globals.

### 2. Empty or contradictory label deltas must remain harmless

`apply_email_label_delta(...)` currently:
- returns `reason="empty_delta"` when no effective labels are supplied
- nets out labels present in both `labels_added` and `labels_removed`
- preserves case-normalized uniqueness

Those behaviors are part of the delta contract and need direct helper-path
coverage, not just end-state coverage.

### 3. Message/source resolution failures must stay soft, not exceptional

Both mutation entrypoints currently return structured failure payloads for:
- `source_not_found`
- `message_not_found`

The worker relies on those outcomes to decide when to fall back to a full fetch
path. This slice must keep that behavior intact.

### 4. Label-delta mutation must preserve metadata and SQLite FTS refresh

`apply_email_label_delta(...)` updates:
- `email_message_labels`
- `email_labels`
- `email_messages.label_text`
- `email_messages.raw_metadata_json`
- SQLite `email_fts` rows when on SQLite

That combination is the highest-risk behavior in the slice and needs explicit
helper-path tests.

### 5. Delete-state reconciliation must keep routing through the media lifecycle seam

`reconcile_email_message_state(...)` should continue calling
`soft_delete_media(..., cascade=True)` through the DB instance seam, not by
inlining delete behavior. That preserves the lifecycle behavior already moved
out of legacy ownership.

## Test Strategy

### Ownership / compat-shell regressions

Add direct regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:
- canonical ownership moved off legacy globals for the four in-scope methods
- legacy `Media_DB_v2` methods delegating through a live `import_module(...)`
  reference

Keep the delegation checks explicit for the two public worker-facing entrypoints.

### Focused helper-path tests

Add a new helper test file for the runtime module covering:
- `_normalize_email_label_values(...)` deduping case-insensitively and ignoring
  empty input
- `_resolve_email_message_row_for_source_message(...)` returning the expected
  row shape for an existing source/message mapping and `None` when absent
- `apply_email_label_delta(...)` preserving empty-delta, contradictory-delta,
  source-not-found, and successful label refresh semantics
- `reconcile_email_message_state(...)` preserving no-state-change,
  source-not-found, delete, and already-deleted outcomes

### Broader caller-facing guards

Retain and reuse:
- [test_email_native_stage1.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_email_native_stage1.py)
- [test_policy_and_connectors.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/External_Sources/test_policy_and_connectors.py)

The worker tests are compatibility guards, not the primary proof of canonical
rebinding.

## Implementation Shape

Add one package runtime module, likely:
- `tldw_Server_API/app/core/DB_Management/media_db/runtime/email_message_mutation_ops.py`

It should own the four in-scope methods only.

Behavior requirements:
- do not change `_resolve_email_tenant_id(...)`
- keep worker-facing return payloads identical
- keep SQLite FTS refresh behavior unchanged
- keep `soft_delete_media(..., cascade=True)` routed through the DB instance
- leave the email read/query helpers untouched

Then:
- rebind the canonical methods in `media_database_impl.py`
- convert the legacy methods in `Media_DB_v2.py` into live-module compat shells

## Success Criteria

- canonical ownership for the four in-scope methods moves off legacy globals
- all legacy methods remain present as live-module compat shells
- focused helper-path tests pass
- broader email-native and connectors-worker guards stay green
- normalized ownership count drops from `104` to `101`
- note: `_normalize_email_label_values(...)` is rebound semantically but the
  ownership script counts only `inspect.isfunction(...)` entries on the class,
  so the rebound `staticmethod` is not included in the normalized total
