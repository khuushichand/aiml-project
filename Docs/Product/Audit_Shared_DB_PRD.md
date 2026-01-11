# Audit Shared Storage Mode - PRD

- **Status:** Draft
- **Last Updated:** 2026-01-11
- **Authors:** Codex (coding agent)
- **Stakeholders:** Core Backend, AuthNZ, DevOps, Security, Docs

---

## 1. Overview

### 1.1 Summary
Introduce a shared audit storage mode alongside the current per-user mode. The shared mode stores all audit events in a single database with strict tenant scoping and admin-only cross-user access. The rollout preserves backward compatibility, provides a one-time migration/ETL utility, and includes a rollback flag.

### 1.2 Motivation
- Per-user audit DBs create operational overhead for backups, migrations, and analytics.
- Admin workflows require multi-user visibility while maintaining strict access controls.
- Consolidating audit storage reduces file sprawl and simplifies retention/monitoring.

### 1.3 Goals
1. Add a configurable audit storage mode with `per_user` as default and `shared` as optional.
2. Enforce tenant scoping in write and query paths for shared mode.
3. Provide a safe, repeatable migration tool from per-user DBs to a shared DB.
4. Enable admin-only cross-user export/count in shared mode.
5. Deprecate per-user DBs after a defined release window with a rollback flag.

### 1.4 Non-Goals
- Changing existing audit event semantics or risk scoring logic.
- Introducing new public API endpoints for audit (only routing behavior changes).
- Building a UI for migrations or analytics.

---

## 2. User Stories

| Story | Persona | Description |
| --- | --- | --- |
| US1 | Admin | "I need a single audit DB so I can export across users without managing hundreds of files." |
| US2 | Operator | "I want to back up and restore audit data with a single file and a clear rollback path." |
| US3 | Developer | "I need a migration tool to move per-user audit DBs into a shared DB without duplicates." |
| US4 | Security | "I need tenant scoping enforced so users cannot access audit data from other users." |

---

## 3. Requirements

### 3.1 Functional Requirements
1. **Settings and Defaults**
   - Add `AUDIT_STORAGE_MODE` with values: `per_user` (default) and `shared`.
   - Add `AUDIT_SHARED_DB_PATH` (default `Databases/audit_shared.db`).
   - Add rollback flag `AUDIT_STORAGE_ROLLBACK=true` that forces `per_user` behavior even when shared mode is configured.
   - Rollback flag takes precedence over `AUDIT_STORAGE_MODE`.
2. **Shared Schema**
   - Shared DB must include required `tenant_user_id` column.
   - All writes must populate tenant id in shared mode.
   - All queries must filter by tenant id unless caller has admin permission.
   - System or anonymous events must map to a reserved tenant id (`system`).
3. **Migration / ETL Utility**
   - Provide a tool to merge all per-user audit DBs plus `Databases/unified_audit.db` into the shared DB.
   - Dedupe by `event_id` with idempotent re-runs.
   - Preserve timestamps, metadata, compliance flags, and risk fields.
   - Log a summary: users processed, rows inserted, duplicates skipped.
4. **Export/Count Behavior**
   - `/audit/export` and `/audit/count` must read from shared DB when `AUDIT_STORAGE_MODE=shared`.
   - Non-admins in shared mode are restricted to their own tenant data regardless of filters.
   - Admins can export/count across users with `user_id` filters.
5. **Backward Compatibility**
   - `per_user` mode remains supported during the deprecation window.
   - Shared mode does not delete per-user DBs automatically.
6. **Audit Daily Stats**
   - `audit_daily_stats` must be tenant-scoped in shared mode (includes `tenant_user_id`).
   - Tenant scope applies to summary queries unless caller has admin permission.

### 3.2 Non-Functional Requirements
- Shared mode should not increase p95 export/count latency for single-user queries by more than 20%.
- Migration tool should handle at least 1M events without crashing (streaming or chunked writes).
- All behavior must be deterministic and auditable via logs.

---

## 4. Data Model

### 4.1 Shared Audit Events Table
- Add `tenant_user_id TEXT NOT NULL` to the shared schema (reserved `system` tenant for anonymous/system events).
- Create index on `tenant_user_id`, plus composite indexes for common filters:
  - `(tenant_user_id, timestamp)`
  - `(tenant_user_id, event_type)`

### 4.2 Compatibility
- Per-user schema remains unchanged.
- Shared schema should be versioned to allow future extension.

### 4.3 Audit Daily Stats
- Shared mode adds `tenant_user_id TEXT NOT NULL` to `audit_daily_stats`.
- Add composite indexes for `(tenant_user_id, date)` and `(tenant_user_id, category)`.

---

## 5. Migration / ETL Plan

1. **Discovery**
   - Scan `Databases/user_databases/*/audit/unified_audit.db` plus `Databases/unified_audit.db`.
2. **Load**
   - For each DB, stream rows in chunks (e.g., 5k) to the shared DB.
3. **Dedupe**
   - Use `event_id` unique constraint in shared DB; `INSERT OR IGNORE`.
4. **Tenant Mapping**
   - Derive `tenant_user_id` from the per-user directory name or user metadata.
   - Map system or anonymous events to the reserved tenant id (`system`).
5. **Verification**
   - Write a summary report and optional per-user counts.
6. **Idempotency**
   - Safe to re-run without inserting duplicates.

---

## 6. API & Access Control

- Shared mode is enforced at the data access layer.
- Non-admin calls always include `tenant_user_id = current_user.id`.
- Admin calls may omit `tenant_user_id` or specify `user_id` filters.
- `system.logs` permission is required for cross-user queries.

---

## 7. Rollout & Deprecation

1. **Release N**: Add settings and shared schema support; default remains `per_user`.
2. **Release N+1**: Ship migration tool and documentation; shared mode opt-in.
3. **Release N+2**: Mark per-user mode deprecated; shared mode recommended.
4. **Release N+3**: Remove per-user default; keep rollback flag for one release.

---

## 8. Observability

- Log storage mode and DB path at startup.
- Migration logs include total rows, duplicates skipped, and per-user counts.
- Export/count logs include whether shared mode is active and tenant scoping applied.

---

## 9. Acceptance Criteria

1. `AUDIT_STORAGE_MODE=per_user` preserves current behavior without schema changes.
2. `AUDIT_STORAGE_MODE=shared` stores new events in the shared DB with `tenant_user_id` populated.
3. Non-admin requests in shared mode cannot read data from other users.
4. Admin requests in shared mode can export/count across users when permitted.
5. Migration tool merges per-user DBs and `Databases/unified_audit.db` into shared DB with no duplicate `event_id` rows.
6. Migration tool preserves original timestamps and metadata fields.
7. Rollback flag forces per-user behavior without requiring DB deletion.
8. Existing per-user DBs remain intact after migration.
9. System or anonymous events in shared mode are stored with `tenant_user_id=system`.
10. `audit_daily_stats` is tenant-scoped in shared mode.

---

## 10. Test Cases

### 10.1 Unit Tests
1. **Storage Mode Routing**
   - Given `AUDIT_STORAGE_MODE=per_user`, queries use per-user DB path.
   - Given `AUDIT_STORAGE_MODE=shared`, queries use shared DB path.
2. **Tenant Enforcement**
   - Non-admin queries automatically apply `tenant_user_id` filter.
   - Admin queries allow cross-user filters.
3. **Shared Schema**
   - Insert fails without `tenant_user_id` in shared mode.
   - Indexes exist for `(tenant_user_id, timestamp)`.
4. **System Tenant Mapping**
   - Events without a user context are stored with `tenant_user_id=system`.

### 10.2 Integration Tests
1. **Export/Count**
   - Admin export/count across users works in shared mode.
   - Non-admin export/count ignores `user_id` filter and returns only own data.
2. **Rollback**
   - With rollback flag enabled, shared mode configuration is ignored.
3. **Audit Daily Stats**
   - Tenant-scoped stats only include events from the requesting user unless admin.

### 10.3 Migration Tests
1. **ETL Dedupe**
   - Re-running the migration does not increase row counts.
2. **Timestamp Preservation**
   - Migrated `timestamp` values match source rows.
3. **Tenant Mapping**
   - Migrated rows have correct `tenant_user_id` based on source DB path.
4. **Default DB Migration**
   - Rows from `Databases/unified_audit.db` are present in the shared DB after migration.

---

## 11. Risks & Mitigations

- **Risk:** Cross-tenant data leaks.
  - **Mitigation:** Enforce tenant filters in the core query layer; add tests for admin vs non-admin paths.
- **Risk:** Migration fails on legacy schemas.
  - **Mitigation:** Add schema compatibility checks and robust error reporting.
- **Risk:** Performance regressions in shared DB.
  - **Mitigation:** Add tenant-indexed queries and monitor p95 latency.

---

## 12. Open Questions

1. Confirm final deprecation window tied to release cadence.
