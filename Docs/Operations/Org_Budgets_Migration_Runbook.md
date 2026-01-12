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
- Restore the database snapshot taken before the migration.
- Re-run the automatic migration by applying migrations (SQLite) or triggering
  the billing-table ensure/backfill path (PostgreSQL).

## 5) Notes
- The backfill runs implicitly (SQLite at migration time; PostgreSQL when admin
  budgets endpoints are first accessed).
- If you need a conflict-aware or offline migration flow, it must be implemented
  separately from the current auto-migration behavior.
