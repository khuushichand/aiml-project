# Storage API (Generated Files)

This API manages user-scoped generated files, storage quotas, trash/restore flows, and cleanup helpers.

Code anchors:
- Router: `tldw_Server_API/app/api/v1/endpoints/storage.py:142`
- Schemas: `tldw_Server_API/app/api/v1/schemas/storage_schemas.py:165`
- Quota service: `tldw_Server_API/app/services/storage_quota_service.py:760`
- Cleanup worker: `tldw_Server_API/app/services/storage_cleanup_service.py:176`

Base path: `/api/v1/storage`

## Security and Path Handling

Downloads and cleanup operations validate resolved filesystem paths stay inside the correct per-user base directory:
- Download traversal guard: `tldw_Server_API/app/api/v1/endpoints/storage.py:228`
- Category-based base dir resolution (outputs vs voices): `tldw_Server_API/app/api/v1/endpoints/storage.py:101`
- Cleanup safe resolver: `tldw_Server_API/app/services/storage_cleanup_service.py:32`

Voice clones (`file_category == voice_clone`) are resolved under the voices directory; other files use the outputs directory.

## Core File Endpoints

- `GET /files`
  - List generated files for the current user with pagination and filters.
  - Anchor: `tldw_Server_API/app/api/v1/endpoints/storage.py:142`
- `GET /files/{file_id}`
  - Returns metadata and updates `accessed_at`.
  - Anchor: `tldw_Server_API/app/api/v1/endpoints/storage.py:180`
- `GET /files/{file_id}/download`
  - Streams the file from disk after ownership and traversal checks.
  - Anchor: `tldw_Server_API/app/api/v1/endpoints/storage.py:203`
- `DELETE /files/{file_id}?hard_delete={bool}`
  - Soft delete (default) subtracts usage and moves to trash.
  - Hard delete removes the record; usage subtraction only occurs if the file was not already soft-deleted.
  - Anchor: `tldw_Server_API/app/services/storage_quota_service.py:880`
- `PATCH /files/{file_id}`
  - Update metadata such as tags, folder tag, or retention fields.
  - Anchor: `tldw_Server_API/app/api/v1/endpoints/storage.py:285`

## Bulk Operations

- `POST /files/bulk-delete`
  - Deletes each file through the quota service to ensure usage counters are updated correctly.
  - Anchor: `tldw_Server_API/app/api/v1/endpoints/storage.py:318`
- `POST /files/bulk-move`
  - Bulk folder-tag changes.
  - Anchor: `tldw_Server_API/app/api/v1/endpoints/storage.py:352`

Bulk delete examples (soft vs hard delete):

```bash
BASE_URL="http://127.0.0.1:8000"
API_KEY="${SINGLE_USER_API_KEY}"

# Soft delete (moves to trash, updates usage once)
curl -sS -X POST "$BASE_URL/api/v1/storage/files/bulk-delete" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"file_ids":[101,102,103],"hard_delete":false}' | jq

# Hard delete (immediate removal; safe for already-trashed files)
curl -sS -X POST "$BASE_URL/api/v1/storage/files/bulk-delete" \
  -H "X-API-KEY: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"file_ids":[201,202],"hard_delete":true}' | jq
```

## Cleanup Suggestions

- `GET /files/least-accessed?limit=20`
  - Returns least recently accessed files (oldest first), using `COALESCE(accessed_at, created_at)`.
  - Anchor: `tldw_Server_API/app/api/v1/endpoints/storage.py:420`
  - Repo implementation: `tldw_Server_API/app/core/AuthNZ/repos/generated_files_repo.py:905`

Least-accessed example:

```bash
curl -sS "$BASE_URL/api/v1/storage/files/least-accessed?limit=20" \
  -H "X-API-KEY: $API_KEY" | jq
```

## Usage and Quotas

- `GET /usage`
  - Returns total usage, category breakdown, and quota warnings.
  - Soft limit is 80% and hard limit is 100%.
  - Anchors:
    - Endpoint logic: `tldw_Server_API/app/api/v1/endpoints/storage.py:449`
    - Warning fields: `tldw_Server_API/app/api/v1/schemas/storage_schemas.py:165`
- `GET /usage/breakdown`
  - Returns folder and category breakdown plus quota numbers.
  - Anchor: `tldw_Server_API/app/api/v1/endpoints/storage.py:500`

Quick usage warning check:

```bash
curl -sS "$BASE_URL/api/v1/storage/usage" \
  -H "X-API-KEY: $API_KEY" | jq '{
    quota_mb,
    quota_used_mb,
    usage_percentage,
    at_soft_limit,
    at_hard_limit,
    warning
  }'
```

Example `GET /usage` response fields that are new/important:

```json
{
  "usage_percentage": 83.4,
  "at_soft_limit": true,
  "at_hard_limit": false,
  "warning": "Approaching storage limit (80%+)"
}
```

Team/org quota checks now surface a soft-limit warning string when appropriate:
- `tldw_Server_API/app/core/AuthNZ/repos/storage_quotas_repo.py:526`

## Trash and Restore

- `GET /trash`
  - List trashed files.
  - Anchor: `tldw_Server_API/app/api/v1/endpoints/storage.py:546`
- `POST /trash/restore/{file_id}`
  - Restores a soft-deleted file and re-adds its usage.
  - Anchor: `tldw_Server_API/app/api/v1/endpoints/storage.py:570`
- `DELETE /trash/{file_id}`
  - Permanently deletes a file already in trash without re-subtracting usage.
  - Anchor: `tldw_Server_API/app/api/v1/endpoints/storage.py:608`

Trash lifecycle examples:

```bash
# 1) List trash
curl -sS "$BASE_URL/api/v1/storage/trash?offset=0&limit=50" \
  -H "X-API-KEY: $API_KEY" | jq

# 2) Restore a trashed file (re-adds usage)
TRASHED_FILE_ID=101
curl -sS -X POST "$BASE_URL/api/v1/storage/trash/restore/$TRASHED_FILE_ID" \
  -H "X-API-KEY: $API_KEY" | jq

# 3) Permanently delete a trashed file (no double subtraction)
curl -sS -X DELETE "$BASE_URL/api/v1/storage/trash/$TRASHED_FILE_ID" \
  -H "X-API-KEY: $API_KEY" | jq
```

## Admin Quota Endpoints

These endpoints require admin privileges and set or inspect quotas at different scopes:
- User quota set: `PUT /admin/quotas/user/{user_id}` (`tldw_Server_API/app/api/v1/endpoints/storage.py:637`)
- Team quota set: `PUT /admin/quotas/team/{team_id}` (`tldw_Server_API/app/api/v1/endpoints/storage.py:670`)
- Org quota set: `PUT /admin/quotas/org/{org_id}` (`tldw_Server_API/app/api/v1/endpoints/storage.py:698`)
- Team quota get: `GET /admin/quotas/team/{team_id}` (`tldw_Server_API/app/api/v1/endpoints/storage.py:726`)
- Org quota get: `GET /admin/quotas/org/{org_id}` (`tldw_Server_API/app/api/v1/endpoints/storage.py:744`)

## Background Cleanup Worker

A background cleanup worker can be enabled to purge expired files, old trash, and temp directories:
- Cleanup cycle: `tldw_Server_API/app/services/storage_cleanup_service.py:176`
- Worker start: `tldw_Server_API/app/main.py:2036`
- Worker stop: `tldw_Server_API/app/main.py:2906`

Environment variables:
- `STORAGE_CLEANUP_ENABLED` (default: true)
- `STORAGE_CLEANUP_INTERVAL_SEC` (default: 3600)
- `STORAGE_TRASH_RETENTION_DAYS` (default: 30)
- `STORAGE_CLEANUP_BATCH_SIZE` (default: 100)

Note: trash purge uses hard delete directly against the repo (no usage subtraction), which is correct for already-soft-deleted files.

## Related Integrations

- TTS download link headers: `tldw_Server_API/app/api/v1/endpoints/audio.py:1166`
- Voice clone registration: `tldw_Server_API/app/core/TTS/voice_manager.py:640`
- File artifacts export registration: `tldw_Server_API/app/core/File_Artifacts/file_artifacts_service.py:356`

For developer-oriented flow details and integration patterns, see:
- `Docs/Code_Documentation/Guides/Generated_Files_Storage_Code_Guide.md:1`
