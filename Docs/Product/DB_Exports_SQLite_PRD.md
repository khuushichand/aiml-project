# Full SQLite Database Export/Import (Admin Data Ops Extension) - PRD

- **Status:** Draft v2 (extension of Admin Data Ops backups)
- **Last Updated:** 2026-02-08
- **Authors:** Codex (coding agent)
- **Reviewers:** Claude Opus 4.6 (review pass)
- **Stakeholders:** Core Backend, WebUI, DevOps, Docs

---

## 1. Overview

### 1.1 Summary
Provide an admin-only, full-export workflow that bundles per-dataset backups created by the existing Admin Data Ops backups into a single downloadable artifact, with a matching import workflow for SQLite deployments. This extends `/api/v1/admin/backups` snapshots with a consistent, versioned bundle + manifest so operators no longer rely on raw filesystem copies.

### 1.2 Motivation & Background
- Single-user mode defaults to SQLite files (`Media_DB_v2.db`, `ChaChaNotes.db`) located under `Databases/` and `<USER_DB_BASE_DIR>/<uid>/`. `USER_DB_BASE_DIR` is defined in `tldw_Server_API.app.core.config` (defaults to `Databases/user_databases/` under the project root); override via environment variable or `Config_Files/config.txt` as needed.
- Admin Data Ops now provides per-dataset backup/restore endpoints (`/api/v1/admin/backups`) that create server-local snapshots for `media`, `chacha`, `prompts`, `evaluations`, `audit`, and `authnz`.
- There is still no bundled export/import artifact (zip + manifest) and no download/import workflow; operators still copy raw `.db` files or stitch together per-dataset backups manually.
- Chatbooks export/import remains the curated data path, not a full-fidelity database snapshot.
- Users migrating between machines or preparing for upgrades have asked for a turnkey, documented full backup workflow.

### 1.3 Goals
1. Provide an authenticated admin export workflow (API + WebUI) that packages all relevant SQLite datasets into a downloadable bundle by reusing the existing Admin Data Ops backup helpers.
2. Offer an import workflow that validates a bundle and restores the contained datasets safely, using existing per-dataset restore logic with rollback safeguards.
3. Keep endpoints and UI under the Admin Data Ops surface (`/api/v1/admin/*`) and align with existing dataset keys and auth constraints.
4. Deliver end-to-end documentation and UX guidance for both CLI and WebUI paths.

### 1.4 Non-Goals
- Replacing the existing per-dataset backup endpoints (they remain the foundation).
- Multi-tenant bulk exports across all users without explicit user selection.
- Long-running job orchestration in the first release (sync-first, async later if needed).
- Supporting PostgreSQL exports beyond the existing per-dataset `pg_dump` path (covered by `pg_dump` guidance).
- Providing incremental or continuous backups (future enhancement).
- Encrypting exports at rest (can be tackled later once base flow is stable).
- Backing up raw media ingestion directories or other large binary asset stores that live outside managed DB/vector-store paths.

---

## 2. User Stories

| Story | Persona | Description |
| --- | --- | --- |
| US1 | Hobbyist self-host | “Before I upgrade to the latest release, I want to click ‘Export full DB’ so I have an instant restore point if something breaks.” |
| US2 | IT admin maintaining a lab machine | “I need a scheduled job that hits an API endpoint nightly to fetch full backups and store them offsite.” |
| US3 | Power user migrating machines | “I want to export everything on my laptop, move the archive to a new workstation, and import it there to continue seamlessly.” |
| US4 | Support engineer | “When debugging user issues I need a guided import that performs validation, rejects incompatible versions, and surfaces errors clearly.” |

---

## 3. Requirements

### 3.1 Functional Requirements
1. **Export Triggering**
   - Admin Data Ops endpoint: `POST /api/v1/admin/backups/bundles` (admin auth).
   - Accept a dataset list plus `user_id`.
     - `user_id` is **required** when any per-user dataset (`media`, `chacha`, `prompts`, `evaluations`, `audit`) is included. Omit it only when the request contains exclusively global datasets (`authnz`).
     - In **single-user mode**, the server auto-resolves `user_id` from the authenticated session when the field is omitted. The resolved value is recorded in the manifest.
   - Sync-first: create the bundle and return metadata + download id in a single request; async job support is a follow-up if needed.
2. **Artifact Contents**
   - Bundle includes per-dataset snapshots created via `DB_Backups` for selected datasets: `media`, `chacha`, `prompts`, `evaluations`, `audit`, `authnz`.
   - **Vector store data (Chroma) is deferred to Phase 2.** The `include_vector_store` field is accepted in the schema for forward compatibility but the server returns `422 Unprocessable Entity` if set to `true` until Phase 2 is implemented. This avoids shipping a non-functional flag.
   - Manifest JSON (`manifest.json` at ZIP root) with metadata:
     - `app_version` (string, e.g. `"0.1.0"`), `manifest_version` (integer, initially `1`).
     - `timestamp` (ISO 8601 UTC), `user_id` (int or `null` for global-only bundles).
     - `datasets` (list of dataset key strings included).
     - `files` (list of objects: `{"filename": "...", "dataset": "...", "size_bytes": N, "hash": "...", "hash_algorithm": "sha256"}`).
     - `schema_versions` (object mapping dataset key to its schema version integer, see Section 5.5).
     - `platform` (object: `{"os": "...", "python_version": "...", "sqlite_version": "..."}`).
   - Compressed into `.zip` with predictable naming: `tldw-backup-bundle-<user_id>-<timestamp>.zip` (e.g. `tldw-backup-bundle-user1-20260112_101530.zip`). For global-only bundles, `<user_id>` is replaced with `global`.
3. **Integrity & Validation**
   - Use the existing SQLite backup API via `DB_Backups` to create consistent snapshots.
   - Include SHA256 checksums for each file in the manifest. Each entry carries a `hash_algorithm` field (initially `"sha256"`) so future versions can upgrade the algorithm without breaking older manifest parsers.
   - On import, verify manifest structure, `hash_algorithm` support, and per-file checksums before restoring any datasets. Reject the bundle immediately if any checksum fails.
4. **Import Workflow**
   - Admin Data Ops endpoint: `POST /api/v1/admin/backups/bundles/import` (multipart upload + options).
   - **Dry-run mode**: accept a `dry_run` boolean (default `false`). When `true`, the endpoint validates the manifest, checksums, schema compatibility, and disk space without restoring anything. Returns a detailed compatibility report. Addresses US4 (support engineer validation).
   - **App version validation**: compare `manifest.app_version` against the running server version. Warn (in response) if the major version differs. Block import if `manifest.manifest_version` is higher than the server supports.
   - **Schema compatibility**: check per-dataset schema versions against current constants (see Section 5.5). Block downgrade unless `allow_downgrade: true` is provided. When `allow_downgrade` is used, the server runs the standard migration path (`_migrate_schema()` or equivalent) **after** restore to bring the older schema up to the current version. The import fails and rolls back if migration fails.
   - Create pre-import safety snapshots per dataset using existing restore safeguards.
   - On failure, revert **all** affected datasets atomically and surface error details including which dataset failed and why.
5. **Storage & Retention**
   - Store bundle artifacts under `TLDW_DB_BACKUP_PATH` (default `./tldw_DB_Backups`) in a `bundles/` subdirectory.
   - Retention policy and cleanup align with existing backup retention settings.
   - **Failure cleanup**: all bundle operations (export and import) wrap staging work in a `try/finally` block. On failure, partial staging directories and incomplete ZIP files are removed before returning the error response. The cleanup is logged at `warning` level.
6. **Access Control & Quotas**
   - Admin auth only; enforce `user_id` for per-user datasets.
   - **Rate limits**: at most 1 concurrent bundle operation (export or import) server-wide. Additionally, limit to 5 bundle exports and 5 bundle imports per hour per admin user. Return `429 Too Many Requests` with `Retry-After` header when exceeded.
   - **Disk space pre-check**: before starting an export, estimate the required space as `sum(dataset file sizes) * 2` (raw copies + ZIP overhead) and verify that the staging volume has at least that much free space. Before starting an import, require `bundle_size * 3` free space (extraction + pre-import safety snapshots + restored files). Return `507 Insufficient Storage` with a human-readable message if the check fails.
7. **Observability**
   - Structured log entries (`backup.bundle.create`, `.completed`, `.failed`).
   - Audit events capturing bundle export/import attempts and outcomes.
8. **Documentation**
   - Update Admin Data Ops docs + Long-Term Admin Guide + new how-to for full bundles.
   - Provide example curl scripts and WebUI screenshots.

### 3.2 Non-Functional Requirements
- Complete export cycle (request → downloadable artifact) must finish within **5 minutes for a 2 GB dataset** on SSD storage. For larger datasets (up to 10 GB), the sync endpoint may approach HTTP gateway timeout limits; this is acceptable in Phase 1. Phase 4 async job support addresses the long-running case.
- Export archives stored server-side for configurable retention (default 24h) then auto-cleaned.
- Import must block concurrent exports/imports to avoid races (see Section 5.4 for locking mechanism).
- All operations must run without requiring manual service restart.

---

## 4. UX & API Design

### 4.1 API

#### Create bundle
`POST /api/v1/admin/backups/bundles`

Request body:
```json
{
  "user_id": 1,
  "datasets": ["media", "chacha", "prompts", "evaluations", "audit", "authnz"],
  "include_vector_store": false,
  "max_backups": 10,
  "retention_hours": 24
}
```
- `user_id`: required when any per-user dataset is included. Omit (or `null`) for global-only bundles. In single-user mode, omitting auto-resolves from the authenticated session.
- `include_vector_store`: accepted for forward compatibility; returns `422` if set to `true` until Phase 2.

Response (`201 Created`):
```json
{
  "bundle_id": "tldw-backup-bundle-user1-20260112_101530.zip",
  "status": "ready",
  "size_bytes": 123456,
  "datasets": ["media", "chacha", "prompts", "evaluations", "audit", "authnz"],
  "user_id": 1,
  "message": "Bundle created"
}
```

#### List bundles
`GET /api/v1/admin/backups/bundles` → list bundles + metadata (paginated, filterable by `user_id`).

#### Get bundle metadata
`GET /api/v1/admin/backups/bundles/{bundle_id}` → returns manifest metadata for a single bundle without downloading the artifact.

#### Download bundle
`GET /api/v1/admin/backups/bundles/{bundle_id}/download` → streams the ZIP artifact using `StreamingResponse` with `Transfer-Encoding: chunked`. Sets `Content-Disposition: attachment; filename="<bundle_id>"` and `Content-Length` headers. Range requests (`Accept-Ranges: bytes`) are not required in Phase 1 but should be considered for Phase 4.

#### Import bundle
`POST /api/v1/admin/backups/bundles/import` → multipart file upload + JSON options.

Options (as form field or query params):
```json
{
  "allow_downgrade": false,
  "dry_run": false
}
```
- `dry_run: true` validates manifest, checksums, schema compatibility, and disk space without restoring. Returns a compatibility report.
- `allow_downgrade: true` permits restoring older schema versions; post-restore migration is run automatically.

#### Delete bundle
`DELETE /api/v1/admin/backups/bundles/{bundle_id}` → deletes a specific bundle artifact from the server. Returns `204 No Content` on success.

Per-dataset snapshots remain available via `POST /api/v1/admin/backups`. All bundle endpoints require admin auth and enforce `user_id` for per-user datasets.

### 4.2 WebUI
- Admin Data Ops page gains "Full Backup Bundle" card with:
  - Export button + spinner + link to download when ready.
  - History table of last N bundles with size, timestamp, status, delete action.
- "Restore from Bundle" dialog:
  - File picker, advanced settings (force schema upgrade, skip prompts DB, dry-run toggle).
  - Warning modal summarizing current DB snapshot creation.
  - **Phase 1 progress**: since the API is synchronous, the UI shows an indeterminate spinner with an estimated duration message (based on dataset count). A "Validate Only" button triggers dry-run mode for pre-flight checks. True progress bars (per-dataset percentage) require the Phase 4 async job system and a polling status endpoint; this is deferred.

### 4.3 CLI / Helper Script
- Optional: ship `Helper_Scripts/db_backup_bundle.py` (or extend existing helpers) to wrap Admin Data Ops bundle APIs for cron usage.

---

## 5. Technical Approach

1. **Service Layer**
   - Extend `admin_data_ops_service.py` with bundle orchestration that reuses `DB_Backups` for per-dataset snapshots.
   - Use `DatabasePaths` and existing dataset resolvers to keep paths consistent with Admin Data Ops.
2. **API Layer**
   - Add bundle endpoints in `tldw_Server_API/app/api/v1/endpoints/admin/__init__.py` alongside existing backup endpoints.
   - Reuse admin auth + audit event emission.
3. **Storage Layout**
   - Use `TLDW_DB_BACKUP_PATH` (default `./tldw_DB_Backups`) for staging artifacts.
   - Subdirectories per bundle ID containing manifest + DB copies + vector store snapshots + zipped output.
4. **Safety Mechanisms**
   - Rely on SQLite backup API (existing `DB_Backups`) for consistent per-dataset snapshots.
   - Pre-import snapshots are created per dataset by existing restore logic.
   - **Concurrency control**: use a module-level `asyncio.Lock` (not file locks) to serialize bundle operations. This is simpler and reliable for the single-process deployment model. File locks are fragile on NFS and across container restarts. If multi-process deployment is needed later, migrate to a database-backed lock or Redis lock.
   - Vector store snapshotting is deferred to Phase 2 (see Section 3.1.2).
5. **Schema Compatibility**
   - **Schema version registry**: introduce a `SCHEMA_VERSIONS` dict in `DB_Backups.py` (or a dedicated `schema_registry.py`) mapping each dataset key to its current schema version integer. Initial values are derived from each database module's migration history (e.g., `Media_DB_v2` migration count, `ChaChaNotes_DB` migration count). Each module's `_migrate_schema()` (or equivalent) increments the version. Example:
     ```python
     SCHEMA_VERSIONS = {
         "media": 3,
         "chacha": 2,
         "prompts": 1,
         "evaluations": 1,
         "audit": 1,
         "authnz": 2,
     }
     ```
   - Manifest records these per-dataset versions. On import, compare each dataset version against the current `SCHEMA_VERSIONS`.
   - **Upgrade path**: if the bundle version is older than current, the existing `_migrate_schema()` runs after restore to bring the database up to date.
   - **Downgrade path**: blocked by default. When `allow_downgrade: true` is provided, the server restores the older schema and then runs the forward migration path. If migration fails, all affected datasets are rolled back and the error is surfaced. This prevents silent schema regression.
   - **Manifest version**: the `manifest_version` field (integer) tracks the manifest format itself, separate from dataset schemas. The server rejects manifests with a `manifest_version` higher than it supports.
6. **Cleanup**
   - Reuse existing retention cleanup; extend to purge expired bundle artifacts.
   - **Failure cleanup**: both export and import operations use `try/finally` to remove partial staging directories and incomplete files. See Section 3.1.5.

---

## 6. Dependencies & Impact

- **Core DB modules:** reuse `DB_Backups` and per-dataset backup helpers already used by Admin Data Ops.
- **Admin Data Ops:** extend existing service and endpoints (`/api/v1/admin/backups`).
- **AuthNZ/Audit:** ensure bundle events are captured in admin audit logs.
- **Docs & WebUI:** align Admin Data Ops UI and documentation updates.

No changes required for MCP or third-party services.

---

## 7. Metrics & Success Criteria

| Metric | Target |
| --- | --- |
| Export success rate | > 99% over last 30 days |
| Import rollback failures | 0 (all restore failures must revert safely) |
| Support tickets about manual DB copying | ↓ 80% within two releases |
| Average export duration for 2 GB dataset | < 5 minutes |

Telemetry is not collected; metrics captured via logs/tests and support feedback.

---

## 8. Rollout Plan

1. **Phase 0 - Design (this document)**
   - Finalize requirements and cross-team agreement.
2. **Phase 1 - Backend API (Admin Data Ops Extension)**
   - Implement bundle service + admin endpoints (create, list, get, download, import, delete).
   - Implement schema version registry (`SCHEMA_VERSIONS`).
   - Implement dry-run import mode.
   - Unit + integration tests (export/import success, schema mismatch, checksum failure, disk space, dry-run, downgrade + migration, failure cleanup).
3. **Phase 2 - WebUI + Helper Script + Vector Store**
   - Extend Admin Data Ops UI (bundle card, restore dialog, validate-only button).
   - Add CLI helper for cron usage.
   - Implement `include_vector_store` support (Chroma directory snapshots).
4. **Phase 3 - Documentation & Release**
   - Update Admin Data Ops docs, Long-Term Admin Guide, and a new how-to.
   - Include migration notes in release changelog.
   - Add comparison table: Chatbooks export vs DB bundle export.
5. **Phase 4 - Hardening**
   - Gather community feedback.
   - Async job support for long-running exports/imports with progress polling.
   - Range request support for download endpoint.
   - Optional encryption (password-protected ZIP).
   - Consider multi-user bulk export (currently a non-goal).

Feature flag and default behavior: align with Admin Data Ops configuration (TBD).

---

## 9. Open Questions

1. ~~What is the most reliable strategy for snapshotting active Chroma directories without prolonged downtime?~~ **Resolved**: deferred to Phase 2. The `include_vector_store` flag returns `422` until then.
2. ~~Do we need built-in encryption (password-protected ZIP) for first release?~~ **Resolved**: no. Listed as a non-goal; deferred to Phase 4 hardening.
3. ~~How do we expose progress for long-running exports in WebUI (per-file vs aggregate)?~~ **Resolved**: Phase 1 uses an indeterminate spinner with estimated duration. True progress bars require async jobs (Phase 4). See Section 4.2.
4. ~~Should imports be allowed while the server is handling user traffic, or do we require maintenance mode?~~ **Resolved**: imports are allowed during normal operation. The `asyncio.Lock` serializes bundle operations, and pre-import snapshots provide rollback safety. Maintenance mode is not required but is recommended in documentation for large imports.
5. How should `SCHEMA_VERSIONS` be bootstrapped for databases that predate the registry? Should we introspect the live schema or assume the latest version?
6. Should the `DELETE` endpoint require confirmation (e.g., a `confirm=true` query param) or is admin auth sufficient?

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Import overwrites data irreversibly | High | Mandatory pre-import snapshot, confirmation dialogs, audit trail, dry-run mode |
| Schema downgrade silently breaks runtime | High | `allow_downgrade` runs forward migration after restore; rollback on migration failure (Section 5.5) |
| Disk space exhaustion during export | Medium | Pre-check requires 2x dataset size free; returns `507` with message (Section 3.1.6) |
| Disk space exhaustion during import | Medium | Pre-check requires 3x bundle size free (extraction + snapshots + restore); returns `507` (Section 3.1.6) |
| Large exports block main event loop | Medium | Stream archives, enforce size limits; async jobs in Phase 4 |
| Partial staging artifacts left after failure | Medium | `try/finally` cleanup in all bundle operations (Section 5.6) |
| Schema drift between releases | Medium | Per-dataset schema version registry + manifest versioning + migration path detection |
| SQLite version mismatch across platforms | Low | Manifest records `sqlite_version`; import logs a warning if versions differ significantly |
| User confusion between Chatbooks vs DB exports | Low | Clear UI copy + docs comparison table |

---

## 11. Appendix

- Existing helpers:
  - `Media_DB_v2.backup_database(path)`
  - `ChaChaNotes_DB.backup_database(path)`
  - `DB_Backups.create_backup(...)`
- Related docs: `Docs/Product/Completed/Admin_Data_Ops.md`, `Docs/Product/Completed/Content_Collections_PRD.md`, `Docs/Product/Completed/Workflows_PRD.md`
- Reference operations guide: `Docs/Published/Deployment/Long_Term_Admin_Guide.md`
