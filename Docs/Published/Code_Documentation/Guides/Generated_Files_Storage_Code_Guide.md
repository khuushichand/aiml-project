# Generated Files Storage Code Guide (Developers)

This guide explains how generated files are saved, registered for quota tracking, served back to users, and cleaned up.

See also:
- Storage API reference: `Docs/API-related/Storage_API_Documentation.md:1`
- Storage router: `tldw_Server_API/app/api/v1/endpoints/storage.py:142`

## Scope and Design Intent

Generated files storage is responsible for:
- Persisting file metadata in `generated_files`.
- Enforcing quotas and surfacing soft-limit warnings.
- Ensuring soft delete, restore, and hard delete keep usage counters correct.
- Preventing path traversal on download and cleanup.

Key anchors:
- Register/unregister: `tldw_Server_API/app/services/storage_quota_service.py:760`
- Cleanup worker: `tldw_Server_API/app/services/storage_cleanup_service.py:176`
- Helpers: `tldw_Server_API/app/core/Storage/generated_file_helpers.py:128`

## Quick Map (Where Things Live)

- API surface
  - Router: `tldw_Server_API/app/api/v1/endpoints/storage.py:142`
  - Schemas: `tldw_Server_API/app/api/v1/schemas/storage_schemas.py:165`
- Core services and repos
  - Storage quota service: `tldw_Server_API/app/services/storage_quota_service.py:760`
  - Generated files repo: `tldw_Server_API/app/core/AuthNZ/repos/generated_files_repo.py:848`
  - Storage quotas repo: `tldw_Server_API/app/core/AuthNZ/repos/storage_quotas_repo.py:511`
- Background cleanup
  - Cleanup service: `tldw_Server_API/app/services/storage_cleanup_service.py:176`
  - App lifecycle hooks: `tldw_Server_API/app/main.py:2036`

## Base Directories and File Categories

Files are stored under per-user base directories resolved by category:
- Default: outputs dir via `DatabasePaths.get_user_outputs_dir`.
- Voice clones: voices dir via `DatabasePaths.get_user_voices_dir`.

Anchors:
- Endpoint base-dir resolver: `tldw_Server_API/app/api/v1/endpoints/storage.py:101`
- Cleanup safe resolver: `tldw_Server_API/app/services/storage_cleanup_service.py:32`

Any code that computes a file path must resolve it and verify it stays inside the correct base directory.

## Registering Files (Quota and Metadata)

The main entry point is `StorageQuotaService.register_generated_file(...)`:
- Anchor: `tldw_Server_API/app/services/storage_quota_service.py:760`
- Important behavior:
  - Enforces a hard per-file size limit of 10 GB.
    - Anchor: `tldw_Server_API/app/services/storage_quota_service.py:809`
  - Performs combined quota checks across user/team/org scopes.
  - Persists a `generated_files` row and updates usage counters.

### Recommended Integration Pattern

Use the generated-file helper functions when possible:
- TTS audio: `save_and_register_tts_audio(...)` (`tldw_Server_API/app/core/Storage/generated_file_helpers.py:128`)
- Images: `save_and_register_image(...)` (`tldw_Server_API/app/core/Storage/generated_file_helpers.py:230`)
- Spreadsheets: `save_and_register_spreadsheet(...)` (`tldw_Server_API/app/core/Storage/generated_file_helpers.py:392`)

These helpers:
- Save bytes into the correct per-user outputs directory.
- Compute the relative `storage_path`.
- Register the file with quota tracking.
- Clean up the file if registration fails.

## Deleting Files Without Double-Subtracting Usage

The deletion flow is intentionally careful about usage counters:
- Anchor: `tldw_Server_API/app/services/storage_quota_service.py:880`

Key behavior:
- Soft delete subtracts usage once when the file transitions from active to deleted.
- Hard delete subtracts usage only if the file was not already soft-deleted.
  - Anchor: `tldw_Server_API/app/services/storage_quota_service.py:901`
- Trash purge and hard delete of already-deleted files should not subtract usage again.

### Voice Clone Filesystem Cleanup

On hard delete, voice clone files are also removed from disk:
- Anchor: `tldw_Server_API/app/services/storage_quota_service.py:911`

This hard-delete cleanup:
- Uses the voices base directory.
- Resolves and validates the path before unlinking.
- Is best-effort and logs a debug message on failure.

## API Behaviors Worth Knowing

### Download Security and Access Tracking

Downloads:
- Validate ownership.
- Block deleted files with HTTP 410.
- Resolve and validate the path to prevent traversal.
- Update `accessed_at` on success.

Anchors:
- Download endpoint: `tldw_Server_API/app/api/v1/endpoints/storage.py:203`
- Traversal guard: `tldw_Server_API/app/api/v1/endpoints/storage.py:228`
- Access updates: `tldw_Server_API/app/core/AuthNZ/repos/generated_files_repo.py:887`

### Bulk Delete Tracks Usage Correctly

Bulk delete routes each file through `unregister_generated_file` so usage counters are updated correctly:
- Anchor: `tldw_Server_API/app/api/v1/endpoints/storage.py:318`

### Soft-Limit Warnings in Usage Responses

`GET /api/v1/storage/usage` now includes soft/hard limit flags and a warning message:
- Endpoint calculation: `tldw_Server_API/app/api/v1/endpoints/storage.py:478`
- Schema fields: `tldw_Server_API/app/api/v1/schemas/storage_schemas.py:172`

Soft limit is 80% usage and hard limit is 100%.

### Least-Accessed Listing for Cleanup Suggestions

A least-accessed endpoint and repo method support LRU-style cleanup suggestions:
- Endpoint: `tldw_Server_API/app/api/v1/endpoints/storage.py:420`
- Repo method: `tldw_Server_API/app/core/AuthNZ/repos/generated_files_repo.py:905`

The sort order uses `COALESCE(accessed_at, created_at)`.

## Background Cleanup Worker

The cleanup worker handles three things per cycle:
- Expired files: hard delete via the quota service (usage updates).
  - Anchor: `tldw_Server_API/app/services/storage_cleanup_service.py:55`
- Old trash: remove from disk (if present) and hard delete the row without touching usage.
  - Anchor: `tldw_Server_API/app/services/storage_cleanup_service.py:104`
- Temp directories: clean up old temporary files.
  - Anchor: `tldw_Server_API/app/services/storage_cleanup_service.py:217`

Worker lifecycle:
- Started on app startup when `STORAGE_CLEANUP_ENABLED` is truthy.
  - Anchor: `tldw_Server_API/app/main.py:2036`
- Stopped on app shutdown.
  - Anchor: `tldw_Server_API/app/main.py:2906`

Environment variables:
- `STORAGE_CLEANUP_ENABLED`
- `STORAGE_CLEANUP_INTERVAL_SEC`
- `STORAGE_TRASH_RETENTION_DAYS`
- `STORAGE_CLEANUP_BATCH_SIZE`

## Integrations Added in This Cycle

### TTS: download-link headers and storage registration

The TTS endpoint can save generated audio into storage and return a download path in headers:
- Endpoint constraint: `return_download_link` requires `stream=false`.
  - Anchor: `tldw_Server_API/app/api/v1/endpoints/audio.py:1045`
- Headers on success:
  - `X-Download-Path`: `/api/v1/storage/files/{id}/download`
  - `X-Generated-File-Id`: generated file id
  - Anchor: `tldw_Server_API/app/api/v1/endpoints/audio.py:1179`
- Registration helper: `save_and_register_tts_audio(...)`.
  - Anchor: `tldw_Server_API/app/core/Storage/generated_file_helpers.py:128`

### Voice Studio: voice clone registration

Voice uploads are registered as `voice_clone` generated files for quota tracking:
- Anchor: `tldw_Server_API/app/core/TTS/voice_manager.py:640`

### File Artifacts: image and spreadsheet exports

Image and spreadsheet exports now register generated files and map storage errors to file-artifact error codes:
- Export registration: `tldw_Server_API/app/core/File_Artifacts/file_artifacts_service.py:374`
- Error codes: `storage_quota_exceeded` and `storage_persist_failed`.
  - Anchor: `tldw_Server_API/app/core/exceptions.py:158`

## Testing Anchors

Storage-specific tests live here:
- `tldw_Server_API/tests/Storage/`

A good focused check after storage changes:

```bash
python -m pytest tldw_Server_API/tests/Storage -q
```
