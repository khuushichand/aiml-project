**Chatbooks Module**

- Path: `tldw_Server_API/app/core/Chatbooks`
- Purpose: Backup, export, import, and preview of user content (conversations, notes, characters, world books, dictionaries, media, embeddings, generated docs) as a portable “chatbook” ZIP with a JSON manifest. Supports multi-user isolation, quotas, and async job processing.

**Overview**
- Produces ZIP archives containing a `manifest.json` plus referenced files (media, documents) based on user selections.
- Supports export/import in both sync and async modes; async jobs can run via either the core Jobs backend or Prompt Studio’s JobManager adapter.
- Enforces strong validation and security: filename/path sanitization, ZIP checks, signed download URLs (optional), per-user storage dirs.

**Key Files**
- `chatbook_service.py`: Main service for export/import/preview and job tracking. Creates per-user storage, writes manifests/archives, manages job rows, optional signed URLs.
- `chatbook_models.py`: Data classes and enums for manifests, content items, relationships, and job records (export/import + statuses).
- `chatbook_validators.py`: Centralized validation and sanitization (filenames, ZIP integrity, traversal checks, ID formats, metadata limits).
- `quota_manager.py`: Per-user quotas (storage, per-day ops, concurrent jobs, file size). DB-backed when available with fallbacks.
- `ps_job_adapter.py`: Optional adapter to route Chatbooks jobs through Prompt Studio’s JobManager when configured.
- `exceptions.py`: Domain-specific exceptions and helpers.
- `job_queue_shim.py`: Legacy shim preserved for reference; not used by the current service.

**Content Types**
- Enum in `chatbook_models.py`: `conversation`, `note`, `character`, `world_book`, `dictionary`, `generated_document`, `media`, `embedding`, `prompt`, `evaluation`.
- API schema mirror in `app/api/v1/schemas/chatbook_schemas.py`.

**Storage Layout**
- Base path resolution in service and quota manager:
  - `TLDW_USER_DATA_PATH` → `<base>/users/<sanitized_user_id>/chatbooks/{exports,imports,temp}`
  - Test/CI → system temp dir under `tldw_test_data`
  - Otherwise → `/var/lib/tldw/user_data`
- File and directory creation uses 0700 perms where possible. Names are sanitized to avoid traversal or unsafe characters.

**Job Backends**
- Core Jobs backend: default. A shared worker can process Chatbooks jobs across users.
  - Worker entry: `tldw_Server_API/app/services/core_jobs_worker.py:run_chatbooks_core_jobs_worker`
  - App startup may launch the worker based on flags (see `app/main.py`).
- Prompt Studio backend: enable via `CHATBOOKS_JOBS_BACKEND=prompt_studio` (or deprecated `TLDW_USE_PROMPT_STUDIO_QUEUE=true`).
  - Adapter: `ps_job_adapter.py` bridges Chatbooks status to Prompt Studio JobManager.

**API Endpoints**
- File: `tldw_Server_API/app/api/v1/endpoints/chatbooks.py`
- Base prefix: `/api/v1/chatbooks`
- `POST /export` → create chatbook (sync or async). Validates metadata, enforces quotas, returns file (sync) or job id (async).
- `POST /import` → import chatbook ZIP (sync or async). Supports conflict resolution strategies and selection filters.
- `POST /preview` → preview manifest without importing.
- `GET  /export/jobs` and `GET /import/jobs` → list jobs; `GET /export/jobs/{id}`/`GET /import/jobs/{id}` → job status.
- `DELETE /export/jobs/{id}` and `DELETE /import/jobs/{id}` → cancel in-flight jobs.
- `GET  /download/{job_id}` → download completed export; supports optional signed URLs.
- `POST /cleanup` → delete expired exports.
- `GET  /health` → lightweight service health for storage checks.

**Export Flow (Sync)**
- Validate request with `ChatbookValidator` and quota checks (`QuotaManager`).
- Build working dir, gather selected content, write `manifest.json`, include optional media/embeddings.
- Create a ZIP in the user’s `exports/` dir. Persist a completed `ExportJob` row to support download URL and expiry.

**Export Flow (Async)**
- Choose backend:
  - Core: create `ExportJob` row (status `pending`), enqueue through core Jobs; worker updates job state and writes archive; job receives `download_url` and `expires_at`.
  - Prompt Studio: create a PS job via adapter; mirror status updates back to PS.
- Download is served from job metadata once `completed`.

**Import Flow**
- Save uploaded ZIP to secure per-user temp; validate ZIP thoroughly.
- If async, create `ImportJob` row and process in background (core or PS). Track `progress`, `conflicts`, `warnings`.
- Apply conflict resolution: `skip`, `overwrite`, `rename`, `merge` (where supported).

**Security & Validation**
- Filename and path sanitization, symlink rejection, traversal prevention.
- ZIP validation: magic number, integrity, per-file size caps, suspicious compression ratio checks, unsafe extensions rejection, required `manifest.json`.
- Optional signed download URLs: HMAC(SHA256) over `{job_id}:{exp}` with `CHATBOOKS_SIGNING_SECRET`.
- Access control: jobs and files are scoped to the authenticated user. Download validates ownership and path containment.

**Quotas**
- Managed by `quota_manager.py` with tiered limits (free, premium, enterprise). Defaults:
  - Storage: 1GB free; 5GB premium
  - Daily ops: 10 exports/imports free; 50 premium
  - Concurrent jobs: 2 free; 5 premium
  - File size caps enforced per tier

**Database**
- The service initializes job tables in the per-user ChaChaNotes DB (`export_jobs`, `import_jobs`).
- Interacts via `CharactersRAGDB.execute_query(...)`; no raw SQL outside DB abstractions elsewhere in the project.

**Configuration**
- `CHATBOOKS_JOBS_BACKEND`: `core` (default) or `prompt_studio`.
- `TLDW_JOBS_BACKEND`: legacy module default override; prefer `CHATBOOKS_JOBS_BACKEND`.
- `TLDW_USE_PROMPT_STUDIO_QUEUE`: legacy boolean; deprecated.
- `TLDW_USER_DATA_PATH`: base path for per-user data (useful for dev/testing).
- `CHATBOOKS_URL_TTL_SECONDS`: download URL expiry TTL (default 86400).
- `CHATBOOKS_ENFORCE_EXPIRY`: `true|false` enforce expiry at download.
- `CHATBOOKS_SIGNED_URLS`: `true|false` enable HMAC signing of download URLs.
- `CHATBOOKS_SIGNING_SECRET`: secret key for HMAC token.
- Core Jobs worker tuning: `JOBS_POLL_INTERVAL_SECONDS`, `JOBS_LEASE_SECONDS`, `JOBS_LEASE_RENEW_SECONDS`, `JOBS_LEASE_RENEW_JITTER_SECONDS`.

**Local Development Tips**
- Start API: `python -m uvicorn tldw_Server_API.app.main:app --reload`
- Health check: `GET /api/v1/chatbooks/health`
- Use `TLDW_USER_DATA_PATH` to direct per-user storage somewhere writable in dev.
- Async exports: ensure core Jobs worker is enabled via app startup, or switch to sync for quick iteration.

**Testing**
- Run tests from repo root: `python -m pytest -v`
- Jobs metrics/health tests live under `tldw_Server_API/tests` and target domain `chatbooks`.
- When adding features, mirror existing test patterns and add:
  - Unit tests for validators and service behavior
  - Integration tests for endpoints (`export`, `import`, `download`, `preview`)
  - Mock external dependencies (e.g., Prompt Studio JobManager) when applicable

**Adding or Changing Features**
- New content type:
  - Add enum to `chatbook_models.py` and `app/api/v1/schemas/chatbook_schemas.py`.
  - Implement selection/export/import handling in `chatbook_service.py`.
  - Extend validators and update manifest serialization if needed.
  - Add tests and update Docs references.
- Job backend behavior:
  - Keep status transitions consistent: `pending → in_progress → completed|failed|cancelled`.
  - Reflect terminal state back to adapters (PS) and persist URLs/expiries for exports.
- Security:
  - All file I/O goes through validators and sanitized paths.
  - Never trust client filenames or paths; never log secrets.

**Error Handling & Logging**
- Use `loguru` for structured logs.
- Raise HTTP 4xx for validation/quota errors; 5xx for unexpected failures (API layer handles mapping).
- Persist error messages to job rows and surface in job status endpoints.

**Cross-Module References**
- Endpoints: `tldw_Server_API/app/api/v1/endpoints/chatbooks.py`
- Schemas: `tldw_Server_API/app/api/v1/schemas/chatbook_schemas.py`
- Jobs core: `tldw_Server_API/app/core/Jobs/`
- DB: `tldw_Server_API/app/core/DB_Management/`

**Contributing**
- Follow project guidelines (PEP8, typing, docstrings). Keep changes minimal and consistent with existing patterns.
- Add or update tests for all behavioral changes.
- Document new env vars and flows here and in `Docs` when appropriate.
