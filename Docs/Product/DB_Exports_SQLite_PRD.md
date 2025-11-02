# Full SQLite Database Export/Import (Single-User Mode) - PRD

- **Status:** Draft
- **Last Updated:** 2024-09-09
- **Authors:** Codex (coding agent)
- **Stakeholders:** Core Backend, WebUI, DevOps, Docs

---

## 1. Overview

### 1.1 Summary
Enable single-user deployments that rely on SQLite to perform complete exports (and later re-imports) of the Media and ChaChaNotes databases through supported server workflows. Today users must stop the service and copy raw `.db` files; this feature delivers a first-class, automated export path that integrates with existing authentication, job management, and storage policies.

### 1.2 Motivation & Background
- Single-user mode defaults to SQLite files (`Media_DB_v2.db`, `ChaChaNotes.db`) located under `Databases/` and `Databases/user_databases/<uid>/`.
- There is no supported API or UI to capture full backups; Chatbooks export/import covers curated content but not full fidelity DB snapshots.
- Operational docs recommend manual filesystem copies, which is error-prone, does not scale to headless deployments, and offers no progress or integrity guarantees.
- Users migrating between machines or preparing for upgrades have asked for a turnkey, documented backup workflow.

### 1.3 Goals
1. Provide an authenticated export workflow (API + WebUI) that packages all SQLite content DBs used in single-user mode into a downloadable artifact.
2. Offer an import workflow that validates an exported artifact and restores the contained DBs safely, including rollback on failure.
3. Integrate with the existing background job system for long-running exports/restores with observable status.
4. Deliver end-to-end documentation and UX guidance for both CLI and WebUI paths.

### 1.4 Non-Goals
- Supporting PostgreSQL exports (covered by `pg_dump` guidance).
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
   - REST endpoint (e.g. `POST /api/v1/maintenance/db/export`) requiring `X-API-KEY`.
   - WebUI control under Maintenance → Backup with progress indicator.
   - Support two modes: synchronous (small DBs <100 MB) and asynchronous job (default). Synchronous mode stages the archive in a temporary location and streams the ZIP directly in the HTTP response before purging the staged copy.
2. **Artifact Contents**
   - All single-user SQLite stores returned by `DatabasePaths.get_all_user_db_paths`, including Media, ChaChaNotes, Prompts, Audit, Evaluations, Personalization, Workflows, and Workflows Scheduler databases (per-store exclusion toggles remain available but default to include all of them).
   - Vector store data (Chroma directories and accompanying meta DBs) with inclusion controlled by config flag (default on).
   - Manifest JSON with metadata (version, timestamp, DB versions, file hashes).
   - Compressed into `.zip` (default) with predictable naming (`tldw-backup-<timestamp>.zip`).
3. **Integrity & Validation**
   - Checkpoint/wrap SQLite connections to ensure consistent export (WAL checkpoint then copy via SQLite backup API).
   - Include SHA256 sum for each file in manifest.
   - On import, verify checksums before replacing production DBs.
4. **Import Workflow**
   - REST endpoint (multipart upload + options) to restore from archive.
   - Enforce compatibility (schema version check; block downgrade without override flag).
   - Automatic pre-import safety snapshot of current DBs.
   - On failure, revert to previous state and surface error details.
5. **Job Management**
   - Introduce a dedicated db-backup worker (`db_backup_jobs_worker`) registered with the Jobs Manager on domain `db_backup`.
   - Expose status endpoints (`/api/v1/jobs/list?domain=db_backup`).
   - Provide download endpoint for export artifacts with signed URL support parity.
6. **Access Control & Quotas**
   - Rate limit exports/imports (e.g. 2/hour) to prevent abuse.
   - Respect per-user storage quotas where applicable (export size vs available disk).
7. **Observability**
   - Structured log entries (`db_backup.export.started`, `.completed`, `.failed`).
   - Audit events capturing export/import attempts and outcomes.
8. **Documentation**
   - Update README + Long-Term Admin Guide + new how-to for backups.
   - Provide example curl scripts and WebUI screenshots.

### 3.2 Non-Functional Requirements
- Complete export cycle (request → downloadable artifact) must finish within 30 minutes for a 10 GB dataset.
- Export archives stored server-side for configurable retention (default 24h) then auto-cleaned.
- Import must block concurrent exports/imports to avoid races.
- All operations must run without requiring manual service restart.

---

## 4. UX & API Design

### 4.1 API
- `POST /api/v1/maintenance/db/export`
  Request body:
  ```json
  {
    "include_prompts": true,
    "include_evaluations": false,
    "include_vector_store": true,
    "async_mode": true,
    "retention_hours": 24
  }
  ```
  Response (async):
  ```json
  {
    "success": true,
    "job_id": "uuid",
    "message": "Export job queued"
  }
  ```
- `GET /api/v1/maintenance/db/export/jobs` → list jobs + download URLs.
- `GET /api/v1/maintenance/db/export/download/{job_id}` → artifact stream.
- `POST /api/v1/maintenance/db/import` (multipart file + query params).
- `GET /api/v1/maintenance/db/import/jobs` → status + logs.

When `async_mode` is `false`, the server blocks until the ZIP archive is ready, then responds with a streaming download while marking the staged artifact for cleanup once the transfer completes (or after a short TTL fallback). All endpoints require single-user auth (`X-API-KEY`) and are hidden in multi-user mode.

### 4.2 WebUI
- Maintenance tab gains “Full Backup” card with:
  - Export button + spinner + link to download when ready.
  - History table of last N backups with size, timestamp, status.
- “Restore from Backup” dialog:
  - File picker, advanced settings (force schema upgrade, skip prompts DB).
  - Warning modal summarizing current DB snapshot creation.
  - Progress bar with log tail (first 20 lines).

### 4.3 CLI / Helper Script
- Optional: ship `Helper_Scripts/db_backup.py` that wraps API calls for cron usage.

---

## 5. Technical Approach

1. **Service Layer**
   - New `DBExportService` under `app/core/DB_Management` orchestrating export/import leveraging existing `backup_database` APIs.
   - Abstraction to gather DB paths from `DatabasePaths` ensuring config consistency.
2. **Job Integration**
   - Register new job domain `db_backup` with job payload describing action (`export`/`import`), options, archive paths.
   - Implement dedicated `db_backup_jobs_worker` that leases `db_backup` jobs and executes `DBExportService` operations end-to-end.
3. **Storage Layout**
   - Use `TLDW_BACKUP_PATH` (default `./tldw_DB_Backups/full`) for staging artifacts.
   - Subdirectories per job ID containing manifest + DB copies + vector store snapshots + zipped output.
4. **Safety Mechanisms**
   - WAL checkpoint + `VACUUM INTO` to temporary file before packaging.
   - Pre-import snapshot stored alongside job data for same retention horizon.
   - Use file locks to serialise backup operations.
   - For vector stores, pause Chroma processes (if running) or use filesystem-level copy-on-write helpers to ensure consistency.
5. **Schema Compatibility**
   - Manifest includes schema version integers; import validates against current constants.
   - Provide flag `allow_downgrade` (default false).
6. **Cleanup**
   - Background task (`jobs_metrics_service` adjunct) to purge expired artifacts.

---

## 6. Dependencies & Impact

- **Core DB modules:** reuse `Media_DB_v2.backup_database`, `ChaChaNotes_DB.backup_database`.
- **Jobs system:** new domain requires worker updates and metric dashboards.
- **AuthNZ/Audit:** ensure events are captured and visible in admin audit logs.
- **Docs & WebUI:** cross-team coordination to ship UI and documentation updates simultaneously.

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
2. **Phase 1 - Backend API & Jobs**
   - Implement service, API endpoints, job worker changes.
   - Unit + integration tests (export/import success, schema mismatch, checksum failure).
3. **Phase 2 - WebUI + Helper Script**
   - Build Maintenance UI.
   - Add CLI helper for cron.
4. **Phase 3 - Documentation & Release**
   - Update README, Admin Guide, new How-To.
   - Include migration notes in release changelog.
5. **Phase 4 - Hardening**
   - Gather community feedback.
   - Consider optional encryption & scheduling enhancements.

Feature flagged via config (`ENABLE_DB_EXPORTS=true`). Default enabled in single-user builds once beta feedback is positive.

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
| Large exports block main event loop | Medium | Run in worker thread/process via job system |
| Schema drift between releases | Medium | Manifest versioning + migration path detection |
| User confusion between Chatbooks vs DB exports | Low | Clear UI copy + docs comparison table |

---

## 11. Appendix

- Existing helpers:
  - `Media_DB_v2.backup_database(path)`
  - `ChaChaNotes_DB.backup_database(path)`
  - `DB_Backups.create_backup(...)`
- Related design docs: `Docs/Design/Content_Collections_PRD.md`, `Docs/Design/Workflows_PRD.md`
- Reference operations guide: `Docs/Published/Deployment/Long_Term_Admin_Guide.md`
