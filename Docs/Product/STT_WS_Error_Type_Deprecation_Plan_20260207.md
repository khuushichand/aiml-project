# STT Audio WS `error_type` Deprecation Plan (2026-02-07)

## Scope
Applies to Audio WebSocket endpoints:
- `WS /api/v1/audio/stream/transcribe`
- `WS /api/v1/audio/stream/tts`
- `WS /api/v1/audio/stream/tts/realtime`
- `WS /api/v1/audio/chat/stream`

## Current Contract
- Canonical error field: `code`
- Legacy compatibility alias: `error_type`
- New toggle: `AUDIO_WS_COMPAT_ERROR_TYPE` (`1` default, `0` disables alias emission)

## Timeline
- **Phase A (2026-02-07)**: Toggle shipped with default compatibility on (`AUDIO_WS_COMPAT_ERROR_TYPE=1`).
- **Phase B (2026-03-01)**: Client notice period starts; all new clients must use `code`.
- **Phase C (2026-04-15)**: Non-prod default target switches to `AUDIO_WS_COMPAT_ERROR_TYPE=0`.
- **Phase D (2026-06-01)**: Remove `error_type` alias from runtime payloads after compatibility window closes.

## Migration Requirements
Client updates must:
1. Read `code` as canonical.
2. Treat `error_type` as optional and removable.
3. Use `data.quota` (not top-level `quota`) for quota context.

## Rollback Plan
If compatibility regressions appear during Phase B/C:
1. Set `AUDIO_WS_COMPAT_ERROR_TYPE=1`.
2. Restart API workers.
3. Re-run Audio WS smoke tests and confirm client recovery.

## Closure Criteria
`STT-KI-002` can close when:
- client compatibility notice is published and acknowledged
- Phase D alias removal is completed
- no critical client regressions for one full release window

