# Email Search M3-005 Retention and Deletion Enforcement

Last Updated: 2026-02-10  
Owner: Backend and Search Team  
Related PRD: `Docs/Product/Email_Ingestion_Search_PRD.md`

## Scope

Add tenant-safe retention and hard-delete enforcement for normalized email data.

## Implementation

Added retention/deletion methods in `Media_DB_v2`:

1. `enforce_email_retention_policy(...)`
   - Tenant-scoped retention by `internal_date`.
   - Supports soft-delete (default) or hard-delete (`hard_delete=True`) of linked media rows.
   - Optional `limit` and `include_missing_internal_date` controls.
   - Returns execution summary (eligible count, applied count, failures, cleanup counts).
2. `hard_delete_email_tenant_data(...)`
   - Tenant-scoped hard-delete workflow for all normalized email-linked media rows.
   - Cleans tenant sync/backfill state when all media deletions succeed.
3. Internal orphan cleanup helper:
   - Removes tenant orphan `email_labels` and `email_participants`.
   - Optionally removes empty `email_sources`.

Primary code location:

- `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`

## Tenant Safety Guarantees

All retention/deletion selection and cleanup filters include `tenant_id` scope.

1. Candidate selection for retention is read from `email_messages WHERE tenant_id = ?`.
2. Orphan cleanup for labels/participants/sources is scoped by `tenant_id`.
3. Hard-delete tenant workflow only deletes media IDs linked from that tenant's normalized rows.

## Validation

Unit coverage added in:

- `tldw_Server_API/tests/DB_Management/test_email_native_stage1.py`

New tests:

1. `test_enforce_email_retention_policy_soft_delete_scoped_to_tenant`
2. `test_enforce_email_retention_policy_hard_delete_removes_orphans`
3. `test_hard_delete_email_tenant_data_scoped_to_target_tenant`
4. `test_enforce_email_retention_policy_rejects_negative_days`

Execution evidence (2026-02-10):

1. `pytest tldw_Server_API/tests/DB_Management/test_email_native_stage1.py -q`
2. Result: `16 passed`.

