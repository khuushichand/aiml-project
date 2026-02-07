# TTS Voice Registry Rollout Checklist

Last updated: 2026-02-07

## Scope
- Feature: persistent custom-voice registry backing store for TTS voice management.
- Primary artifacts:
  - `tldw_Server_API/app/core/TTS/voice_manager.py`
  - `tldw_Server_API/app/core/DB_Management/Voice_Registry_DB.py`
  - Per-user DB file: `<USER_DB_BASE_DIR>/<user_id>/voices/voice_registry.db`

## Rollout Gates
- [x] Stage 5 auth/rate-limit route granularity for `audio.voices.*` is complete and tested.
- [x] Stage 6 persistent registry implementation is complete and tested.
- [x] Compatibility mode exists via `TTS_VOICE_REGISTRY_ENABLED=false`.
- [x] Compatibility mode deprecation timeline is documented (target removal after 2026-12-31).

## Pre-Deploy Validation
- [x] Unit tests:
  - `tldw_Server_API/tests/TTS_NEW/unit/test_voice_registry_db.py`
  - `tldw_Server_API/tests/TTS_NEW/unit/test_voice_manager.py`
- [x] Integration tests:
  - `tldw_Server_API/tests/Storage/test_voice_storage_integration.py`
  - `tldw_Server_API/tests/TTS_NEW/integration/test_custom_voice_resolution.py`
- [x] Auth/rate-limit regression:
  - `tldw_Server_API/tests/TTS_NEW/integration/test_voice_routes_rate_limit.py`
  - `tldw_Server_API/tests/AuthNZ/unit/test_scoped_token_enforcement.py`

## Deployment Steps
- [x] Deploy code with persistent registry enabled (default behavior).
- [x] Verify creation of per-user `voice_registry.db` after voice upload/list operations.
- [x] Verify voice CRUD APIs continue returning expected payloads:
  - `POST /api/v1/audio/voices/upload`
  - `GET /api/v1/audio/voices`
  - `GET /api/v1/audio/voices/{voice_id}`
  - `DELETE /api/v1/audio/voices/{voice_id}`
- [x] Verify preview path still functions:
  - `POST /api/v1/audio/voices/{voice_id}/preview`

## Monitoring
- [x] Watch application logs for:
  - voice registry migration/SQLite warnings
  - fallback warnings to compatibility mode
  - voice CRUD path errors
- [x] Confirm voice route usage/rate-limit counters remain isolated under `voice_call`.

## Rollback Plan
- [x] Immediate compatibility rollback:
  - set `TTS_VOICE_REGISTRY_ENABLED=false`
  - restart API service
- [x] Rollback verification:
  - list/get/delete voice endpoints continue operating via runtime/filesystem sync
  - no blocking DB migration requirement

## Post-Deploy Follow-up
- [x] Docs updated:
  - `Docs/User_Guides/TTS_Getting_Started.md`
  - `Docs/Published/User_Guides/TTS_Getting_Started.md`
  - `Docs/Product/TTS_Module_PRD.md`
  - `tldw_Server_API/app/core/TTS/README.md`
  - `tldw_Server_API/Config_Files/README.md`
- [x] Plan updated:
  - `IMPLEMENTATION_PLAN_tts_debt_config_observability_auth_registry.md`
