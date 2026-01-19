# File Artifacts Exports Runbook

## Scope
Operational guidance for async file artifact exports created via `POST /api/v1/files/create`
when `export.async_mode` is `async` or `auto`.

## Worker Modes
- In-process: set `FILES_JOBS_WORKER_ENABLED=true` on the API server.
- External: run `python -m tldw_Server_API.app.core.File_Artifacts.jobs_worker`.
- If no worker is running, exports stay in `pending` until a worker starts.

## Required Configuration
- `JOBS_DB_URL` (optional): set for Postgres-backed Jobs.
- `FILES_JOBS_QUEUE` (optional, default `default`): ensure API + worker match.
- `FILES_JOBS_LEASE_SECONDS` (optional): job lease duration.
- `FILES_INLINE_MAX_BYTES` or config.txt `[Files] inline_max_bytes` (optional): inline export size cap (default 256KB).

## Verification
1. Submit an async export:
   - `POST /api/v1/files/create` with `export.async_mode=async`.
2. Poll status:
   - `GET /api/v1/files/{file_id}` returns `export.status=pending` then `ready`.
3. Download:
   - `GET /api/v1/files/{file_id}/export?format=...` returns file once; subsequent download returns 404.
4. Inspect Jobs (admin):
   - `GET /api/v1/jobs/list?domain=files&status=queued`.

## Troubleshooting
- **Pending forever**: worker not running or queue mismatch; confirm `FILES_JOBS_QUEUE` and Jobs backend config.
- **404 on download immediately**: export may have expired or been consumed; verify `export_expires_at` on the artifact.
- **Failed jobs**: use `POST /api/v1/jobs/retry-now` with `domain=files` (admin) after fixing the underlying issue.
