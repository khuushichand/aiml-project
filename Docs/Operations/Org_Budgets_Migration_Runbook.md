# Org Budgets Migration Runbook

This runbook covers verification and rollback for the automatic migration of
legacy org budgets from `org_subscriptions.custom_limits_json.budgets` into
`org_budgets.budgets_json`.

## 1) Preconditions
- Ensure a full database snapshot exists and is recoverable.
- Confirm the target schema (`org_budgets` table) is present in all environments.

## 2) Automatic Migration Behavior
- SQLite: AuthNZ migration 042 creates `org_budgets`, inserts legacy budgets
  (replacing any existing row for the org), then strips `budgets` from
  `custom_limits_json`.
- PostgreSQL: the billing-table ensure/backfill path inserts legacy budgets only
  when `org_budgets` is empty, normalizes payloads, and strips legacy `budgets`
  from `custom_limits_json` regardless.
- There is no offline script or conflict report in the current flow.

## 3) Verification Steps
- Confirm no legacy budgets remain in `org_subscriptions.custom_limits_json`.
- Spot-check a sample of orgs to ensure `org_budgets.budgets_json` reflects
  the expected values.
- Verify admin/org budgets endpoints return the migrated budgets.

## 4) Rollback
- Stop all application instances (and any migration jobs) to prevent new writes
  during rollback.
- Restore the database snapshot taken before the migration. This will discard
  all transactions that occurred after the snapshot was taken.
- Choose the path that matches your intent:
  - **Rollback due to a migration bug (plan to stay on the new schema):** fix the
    migration logic first, then re-run the automatic migration by applying
    migrations (SQLite) or triggering the billing-table ensure/backfill path
    (PostgreSQL).
  - **Remain on the old schema temporarily:** pin the deployed application to a
    pre-migration version (e.g., previous container tag or Git SHA), or disable
    the auto-migration step on restart (skip any startup migration/bootstrap
    job) to prevent reapplying migration 042. Do not restart newer builds
    against the old schema.
- Compatibility note: pre-migration builds expect budgets in
  `org_subscriptions.custom_limits_json`; post-migration builds expect
  `org_budgets.budgets_json`. Running a mismatched app version against the
  schema will either reapply migrations or surface errors.

## 5) Notes
- The backfill runs implicitly (SQLite at migration time; PostgreSQL when admin
  budgets endpoints are first accessed).
- If you need a conflict-aware or offline migration flow, it must be implemented
  separately from the current auto-migration behavior.
