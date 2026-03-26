# Media DB V2 Claims Monitoring Legacy Migration Helper Rebinding Design

## Summary

Rebind the legacy `migrate_legacy_claims_monitoring_alerts(...)` coordinator onto
a package-owned runtime helper so the canonical `MediaDatabase` no longer owns
this method through legacy globals while preserving the claims alerts API
migration path.

## Scope

In scope:
- `migrate_legacy_claims_monitoring_alerts(...)`

Out of scope:
- claims monitoring config CRUD helpers
- claims monitoring alert CRUD helpers
- claims monitoring settings/event/health helpers
- claims cluster helpers and claims CRUD/search
- bootstrap/schema helpers

## Why This Slice

This is the smallest remaining claims-specific coordinator after the alert and
config helper layers were already rebound. It has direct caller-facing coverage
through the claims alerts API and legacy migration test, which makes it a
bounded follow-up instead of another wide claims-domain tranche.

## Current Behavior

The legacy method:
1. returns `0` immediately when alert rows already exist
2. returns `0` immediately when no legacy config rows exist
3. translates each legacy config row into a claims monitoring alert using the
   legacy config row id as the alert id
4. derives `channels_json` from slack/webhook/email fields
5. deletes legacy config rows after successful migration
6. returns the migrated row count

## Risks To Preserve

1. Early-return ordering:
   - existing alerts must short-circuit before reading config rows
2. Explicit-id migration:
   - migrated alerts must preserve the legacy config row id
3. Email channel derivation:
   - JSON list inputs and malformed truthy strings must still enable email
4. Cleanup timing:
   - legacy config rows should be deleted only after migration work completes

## Test Strategy

Direct regressions:
- canonical `MediaDatabase.migrate_legacy_claims_monitoring_alerts(...)` no
  longer uses legacy globals
- legacy `Media_DB_v2` method delegates through a live package-module import

Focused helper tests:
- existing-alert short circuit
- empty-legacy short circuit
- explicit-id migration and delete-after-migrate behavior
- malformed/truthy `email_recipients` still enabling the email channel

Broader guards:
- `tldw_Server_API/tests/Claims/test_claims_monitoring_legacy_migration.py`
- `tldw_Server_API/tests/Claims/test_claims_monitoring_api.py`

## Success Criteria

- canonical ownership count drops from `44` to `43`
- the claims alerts API migration path remains green
- legacy compat shell remains present in `Media_DB_v2.py`
