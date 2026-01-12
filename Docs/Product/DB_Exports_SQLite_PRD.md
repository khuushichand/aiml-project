# Full SQLite Database Export/Import (Admin Data Ops Extension) - PRD

- **Status:** Draft (extension of Admin Data Ops backups)
- **Last Updated:** 2026-01-12
- **Authors:** Codex (coding agent)
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
   - Accept a dataset list plus optional `user_id` (required for per-user datasets).
   - Sync-first: create the bundle and return metadata + download id in a single request; async job support is a follow-up if needed.
2. **Artifact Contents**
   - Bundle includes per-dataset snapshots created via `DB_Backups` for selected datasets: `media`, `chacha`, `prompts`, `evaluations`, `audit`, `authnz`.
   - Optional vector store data (Chroma directories + meta DBs) controlled by a flag (default off unless explicitly enabled).
   - Manifest JSON with metadata (app version, timestamp, user_id, dataset list, backup filenames, file sizes, file hashes, schema versions).
   - Compressed into `.zip` with predictable naming (`tldw-backup-bundle-<timestamp>.zip`).
3. **Integrity & Validation**
   - Use the existing SQLite backup API via `DB_Backups` to create consistent snapshots.
   - Include SHA256 sums for each file in the manifest.
   - On import, verify manifest + checksums before restoring datasets.
4. **Import Workflow**
   - Admin Data Ops endpoint: `POST /api/v1/admin/backups/bundles/import` (multipart upload + options).
   - Enforce compatibility (schema version check; block downgrade without override flag).
   - Create pre-import safety snapshots per dataset using existing restore safeguards.
   - On failure, revert the affected datasets and surface error details.
5. **Storage & Retention**
   - Store bundle artifacts under `TLDW_DB_BACKUP_PATH` (default `./tldw_DB_Backups`) in a `bundles/` subdirectory.
   - Retention policy and cleanup align with existing backup retention settings.
6. **Access Control & Quotas**
   - Admin auth only; enforce `user_id` for per-user datasets.
   - Rate limit bundle exports/imports and validate available disk space.
7. **Observability**
   - Structured log entries (`backup.bundle.create`, `.completed`, `.failed`).
   - Audit events capturing bundle export/import attempts and outcomes.
8. **Documentation**
   - Update Admin Data Ops docs + Long-Term Admin Guide + new how-to for full bundles.
   - Provide example curl scripts and WebUI screenshots.

### 3.2 Non-Functional Requirements
- Complete export cycle (request → downloadable artifact) must finish within 30 minutes for a 10 GB dataset.
- Export archives stored server-side for configurable retention (default 24h) then auto-cleaned.
- Import must block concurrent exports/imports to avoid races.
- All operations must run without requiring manual service restart.

---

## 4. UX & API Design

### 4.1 API
- `POST /api/v1/admin/backups/bundles`
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
  Response:
  ```json
  {
    "bundle_id": "tldw-backup-bundle-20260112_101530.zip",
    "status": "ready",
    "size_bytes": 123456,
    "message": "Bundle created"
  }
  ```
- `GET /api/v1/admin/backups/bundles` → list bundles + metadata.
- `GET /api/v1/admin/backups/bundles/{bundle_id}/download` → artifact stream.
- `POST /api/v1/admin/backups/bundles/import` (multipart file + options).

Per-dataset snapshots remain available via `POST /api/v1/admin/backups`. All bundle endpoints require admin auth and enforce `user_id` for per-user datasets.

### 4.2 WebUI
- Admin Data Ops page gains “Full Backup Bundle” card with:
  - Export button + spinner + link to download when ready.
  - History table of last N bundles with size, timestamp, status.
- “Restore from Bundle” dialog:
  - File picker, advanced settings (force schema upgrade, skip prompts DB).
  - Warning modal summarizing current DB snapshot creation.
  - Progress bar with log tail (first 20 lines).

### 4.3 CLI / Helper Script
- Optional: ship `Helper_Scripts/db_backup_bundle.py` (or extend existing helpers) to wrap Admin Data Ops bundle APIs for cron usage.

---

## 5. Technical Approach

1. **Service Layer**
   - Extend `admin_data_ops_service.py` with bundle orchestration that reuses `DB_Backups` for per-dataset snapshots.
   - Use `DatabasePaths` and existing dataset resolvers to keep paths consistent with Admin Data Ops.
2. **API Layer**
   - Add bundle endpoints in `tldw_Server_API/app/api/v1/endpoints/admin.py` alongside existing backup endpoints.
   - Reuse admin auth + audit event emission.
3. **Storage Layout**
   - Use `TLDW_DB_BACKUP_PATH` (default `./tldw_DB_Backups`) for staging artifacts.
   - Subdirectories per bundle ID containing manifest + DB copies + vector store snapshots + zipped output.
4. **Safety Mechanisms**
   - Rely on SQLite backup API (existing `DB_Backups`) for consistent per-dataset snapshots.
   - Pre-import snapshots are created per dataset by existing restore logic.
   - Use file locks to serialize bundle operations.
   - For vector stores, use filesystem snapshots or pause Chroma if consistency requires it.
5. **Schema Compatibility**
   - Manifest includes schema version integers; import validates against current constants.
   - Provide flag `allow_downgrade` (default false).
6. **Cleanup**
   - Reuse existing retention cleanup; extend to purge expired bundle artifacts.

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
   - Implement bundle service + admin endpoints.
   - Unit + integration tests (export/import success, schema mismatch, checksum failure).
3. **Phase 2 - WebUI + Helper Script**
   - Extend Admin Data Ops UI.
   - Add CLI helper for cron usage.
4. **Phase 3 - Documentation & Release**
   - Update Admin Data Ops docs, Long-Term Admin Guide, and a new how-to.
   - Include migration notes in release changelog.
5. **Phase 4 - Hardening**
   - Gather community feedback.
   - Consider optional async jobs and encryption enhancements.

Feature flag and default behavior: align with Admin Data Ops configuration (TBD).

---

## 9. Open Questions

1. What is the most reliable strategy for snapshotting active Chroma directories without prolonged downtime?
2. Do we need built-in encryption (password-protected ZIP) for first release?
3. How do we expose progress for long-running exports in WebUI (per-file vs aggregate)?
4. Should imports be allowed while the server is handling user traffic, or do we require maintenance mode?

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Import overwrites data irreversibly | High | Mandatory pre-import snapshot, confirmation dialogs, audit trail |
| Disk space exhaustion during export | Medium | Quota checks + configurable staging path + early warnings |
| Large exports block main event loop | Medium | Stream archives, enforce size limits, and add optional async job handling if needed |
| Schema drift between releases | Medium | Manifest versioning + migration path detection |
| User confusion between Chatbooks vs DB exports | Low | Clear UI copy + docs comparison table |

---

## 11. Appendix

- Existing helpers:
  - `Media_DB_v2.backup_database(path)`
  - `ChaChaNotes_DB.backup_database(path)`
  - `DB_Backups.create_backup(...)`
- Related docs: `Docs/Product/Completed/Admin_Data_Ops.md`, `Docs/Design/Content_Collections_PRD.md`, `Docs/Design/Workflows_PRD.md`
- Reference operations guide: `Docs/Published/Deployment/Long_Term_Admin_Guide.md`
