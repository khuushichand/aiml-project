# Media DB V2 Claims Monitoring Event Helper Rebinding Design

## Overview

This tranche removes the legacy ownership of the live claims monitoring event
delivery layer from `Media_DB_v2` and rebinds it onto a package-owned runtime
module. The target methods are:

- `insert_claims_monitoring_event(...)`
- `list_claims_monitoring_events(...)`
- `list_undelivered_claims_monitoring_events(...)`
- `mark_claims_monitoring_events_delivered(...)`
- `get_latest_claims_monitoring_event_delivery(...)`

The canonical `MediaDatabase` class should stop owning these methods through
legacy globals, while `Media_DB_v2` keeps compat-shell methods that delegate
through a live module reference.

## Why This Slice

After the monitoring alert and health helpers moved off legacy ownership, the
next clean claims-monitoring seam is the event delivery cluster:

- it is a coherent five-method cluster in `Media_DB_v2`
- it sits on the active runtime path for webhook delivery, email digests, and
  dashboard analytics
- it already has caller-facing coverage in:
  - `tldw_Server_API/tests/Claims/test_claims_alerts_digest.py`
  - `tldw_Server_API/tests/Claims/test_claims_webhook_delivery.py`
  - `tldw_Server_API/tests/Claims/test_claims_dashboard_analytics.py`

This is better leverage than jumping into the broader claims clustering or
legacy config surfaces.

## In Scope

- Add one package-owned runtime helper module for the five event methods
- Rebind canonical `MediaDatabase` methods in `media_database_impl.py`
- Convert the five legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests for the event delivery behaviors that are easy
  to regress during extraction

## Out Of Scope

- `list_claims_monitoring_user_ids(...)`
- `create_claims_monitoring_config(...)`
- `get_claims_monitoring_config(...)`
- `update_claims_monitoring_config(...)`
- `delete_claims_monitoring_config(...)`
- `delete_claims_monitoring_configs_by_user(...)`
- `migrate_legacy_claims_monitoring_alerts(...)`
- claims review, claims clustering, and search helpers

## Required Behavior To Preserve

### Insert

- `insert_claims_monitoring_event(...)` must keep writing:
  - `user_id`
  - `event_type`
  - `severity`
  - `payload_json`
  - `created_at`
  - `delivered_at`
- it must keep using `self._get_current_utc_timestamp_str()` for the insert
  timestamp
- it must keep storing `delivered_at` as `None` on insert

### List

- `list_claims_monitoring_events(...)` must keep:
  - filtering by `user_id`
  - optional filters for `event_type`, `severity`, `start_time`, and `end_time`
  - `created_at ASC` ordering
  - `dict(row)` row materialization

### Undelivered

- `list_undelivered_claims_monitoring_events(...)` must keep:
  - forcing `delivered_at IS NULL`
  - optional `event_type` filtering
  - limit coercion to `int`
  - limit clamping to `1..5000`
  - `created_at ASC` ordering

### Mark Delivered

- `mark_claims_monitoring_events_delivered(...)` must keep returning `0` for an
  empty id list
- it must keep using `self._get_current_utc_timestamp_str()` for the delivery
  timestamp
- it must keep returning the cursor rowcount with the current fallback-to-`0`
  behavior

### Latest Delivery Lookup

- `get_latest_claims_monitoring_event_delivery(...)` must keep:
  - filtering by `user_id`
  - filtering to `delivered_at IS NOT NULL`
  - optional `event_type` filtering
  - returning `None` for a missing row
  - preserving the current mapping-row then tuple-row fallback when reading the
    aggregate result

## Risk Review

### 1. Digest delivery cursor behavior

The alert email digest path depends on both
`list_undelivered_claims_monitoring_events(...)` and
`mark_claims_monitoring_events_delivered(...)`. If limit clamping, ordering, or
delivery timestamp writes drift, digest batching semantics will change.

### 2. Webhook delivery history

`claims_service._record_webhook_event(...)` writes delivery attempts through
`insert_claims_monitoring_event(...)`. This slice must preserve the write path
exactly, including created-at generation and nullable `delivered_at`.

### 3. Analytics/export query filters

The dashboard/export path relies on
`list_claims_monitoring_events(...)` preserving the same optional filter
semantics and ascending order. This tranche must not reinterpret or normalize
the higher-level payload JSON or event types.

## Design

### New Runtime Module

Add:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/claims_monitoring_event_ops.py`

This module will own:

- `insert_claims_monitoring_event(...)`
- `list_claims_monitoring_events(...)`
- `list_undelivered_claims_monitoring_events(...)`
- `mark_claims_monitoring_events_delivered(...)`
- `get_latest_claims_monitoring_event_delivery(...)`

### Canonical Rebinding

In `media_database_impl.py`:

- import the five runtime helper functions
- assign them onto the canonical `MediaDatabase` class

### Legacy Compat Shells

In `Media_DB_v2.py`:

- keep the five methods present
- replace each body with an `import_module(...)` delegation call into
  `claims_monitoring_event_ops`

## Testing Strategy

### Direct Regressions

Add/extend regressions in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py` for:

- canonical ownership moved off legacy globals for all five methods
- legacy compat-shell delegation through the runtime module

### Focused Helper Tests

Add:

- `tldw_Server_API/tests/DB_Management/test_media_db_claims_monitoring_event_ops.py`

Focus on:

- insert writes `delivered_at=None`
- list filter behavior and `created_at ASC` ordering
- undelivered limit coercion and clamp behavior
- mark-delivered empty-list short circuit and rowcount behavior
- latest-delivery missing-row and tuple-row fallback behavior

### Broader Guards

Keep these as tranche-level caller-facing guards:

- `tldw_Server_API/tests/Claims/test_claims_alerts_digest.py`
- `tldw_Server_API/tests/Claims/test_claims_webhook_delivery.py`
- `tldw_Server_API/tests/Claims/test_claims_dashboard_analytics.py`

## Success Criteria

- canonical `MediaDatabase` no longer owns the five event delivery methods
  through legacy globals
- legacy `Media_DB_v2` methods remain working compat shells
- helper-path tests pass
- caller-facing claims monitoring tests stay green
- normalized ownership count drops from `63` to `58`
