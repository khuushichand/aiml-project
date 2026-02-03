# PRD: Audio Endpoint Split (audio.py)

## Summary
Refactor `tldw_Server_API/app/api/v1/endpoints/audio.py` into focused endpoint modules with shared orchestration logic moved into `tldw_Server_API/app/core/` services. Preserve all existing API behavior, paths, response formats, headers, and WebSocket protocols.

## Background
`audio.py` (~5.3k lines) combines HTTP endpoints, WebSocket handlers, tokenizer helpers, TTS/STT orchestration, quota enforcement, and health endpoints in one file. This complexity increases review risk, slows feature delivery, and makes testing brittle.

## Goals
- Preserve full API compatibility (paths, payloads, headers, status codes).
- Reduce `audio.py` to a thin router aggregator and re-export shim.
- Move heavy logic into dedicated core services for unit testing.
- Eliminate mixed concerns within endpoint modules (TTS/STT/streaming/tokenizer/voices).
- Keep existing test monkeypatch points intact.

## Non-Goals
- No new features.
- No behavior changes or provider changes.
- No database schema or storage changes.
- No dependency upgrades.

## Decisions (Resolved)
- **Service modules live in core:** `tldw_Server_API/app/core/`.
- **Non-streaming `/chat` lives with streaming endpoints.**
- **`/providers` and `/voices/catalog` stay in TTS endpoints (not a shared voices module).**

## Scope

### Endpoint Modules (New)
All modules keep the same public routes and FastAPI behavior.

- `tldw_Server_API/app/api/v1/endpoints/audio.py`
  - Aggregates routers and exports `router`, `ws_router`.
  - Re-exports test monkeypatch points: `can_start_job`, `finish_job`, `increment_jobs_started`, `get_limits_for_user` (if used).

- `tldw_Server_API/app/api/v1/endpoints/audio_tts.py`
  - `POST /speech`
  - `POST /speech/metadata`
  - `GET /providers`
  - `GET /voices/catalog`
  - `POST /reset-metrics`
  - Keeps TTS sanitization, BYOK resolution, and error mapping helpers.

- `tldw_Server_API/app/api/v1/endpoints/audio_tokenizer.py`
  - `POST /tokenizer/encode`
  - `POST /tokenizer/decode`
  - Tokenizer helper functions moved here or into core service.

- `tldw_Server_API/app/api/v1/endpoints/audio_transcriptions.py`
  - `POST /transcriptions`
  - `POST /translations`
  - `POST /segment/transcript`
  - Whisper model mapping helpers live here or in core service.

- `tldw_Server_API/app/api/v1/endpoints/audio_streaming.py`
  - WebSocket:
    - `WS /stream/transcribe`
    - `WS /chat/stream`
    - `WS /stream/tts`
    - `WS /stream/tts/realtime`
  - HTTP:
    - `GET /stream/status`
    - `GET /stream/limits`
    - `POST /stream/test`
    - `POST /chat` (non-streaming STT → LLM → TTS)

- `tldw_Server_API/app/api/v1/endpoints/audio_health.py`
  - `GET /health`
  - `GET /transcriptions/health`

- `tldw_Server_API/app/api/v1/endpoints/audio_voices.py`
  - `POST /voices/upload`
  - `POST /voices/encode`
  - `GET /voices`
  - `GET /voices/{voice_id}`
  - `DELETE /voices/{voice_id}`
  - `POST /voices/{voice_id}/preview`

### Core Services (New)
Move orchestration logic into core-level services for testability. TTS-specific behavior stays in `core/TTS`.

- `tldw_Server_API/app/core/Audio/tts_service.py`
  - Endpoint-level TTS orchestration (sanitization, BYOK override prep, error translation).
- `tldw_Server_API/app/core/Audio/transcription_service.py`
  - File validation, temp file handling, model resolution, quota enforcement, transcription orchestration.
- `tldw_Server_API/app/core/Audio/tokenizer_service.py`
  - Tokenizer configuration, payload limits, encode/decode helpers.
- `tldw_Server_API/app/core/Audio/streaming_service.py`
  - Shared streaming helpers, fail-open quota logic, WS auth helpers.
- `tldw_Server_API/app/core/Audio/error_payloads.py`
  - `_http_error_detail`, `_ws_error_payload`, debug detail toggles.
- `tldw_Server_API/app/core/Audio/quota_helpers.py`
  - `EXPECTED_DB_EXC`, `EXPECTED_REDIS_EXC`, `_get_failopen_cap_minutes`.

## Concrete Extraction Map
Function-by-function move list from `audio.py` into new modules.

| Function or Constant | Destination | Notes |
| --- | --- | --- |
| `router` | `app/api/v1/endpoints/audio.py` | Aggregator router; include subrouters. |
| `ws_router` | `app/api/v1/endpoints/audio_streaming.py` | WebSocket router. |
| `CHAT_HISTORY_MAX_MESSAGES` | `app/core/Audio/streaming_service.py` | Used by streaming chat. |
| `_get_chat_history_max_messages` | `app/core/Audio/streaming_service.py` | Streaming chat helper. |
| `_debug_error_details_enabled` | `app/core/Audio/error_payloads.py` | Shared HTTP/WS error payloads. |
| `_maybe_debug_details` | `app/core/Audio/error_payloads.py` | Shared HTTP/WS error payloads. |
| `_http_error_detail` | `app/core/Audio/error_payloads.py` | Shared HTTP error payloads. |
| `_ws_error_payload` | `app/core/Audio/error_payloads.py` | Shared WS error payloads. |
| `_coerce_int` | `app/core/Audio/tokenizer_service.py` | Tokenizer config parsing. |
| `_get_qwen3_tokenizer_settings` | `app/core/Audio/tokenizer_service.py` | Tokenizer config. |
| `_decode_base64_payload` | `app/core/Audio/tokenizer_service.py` | Tokenizer payload parsing. |
| `_enforce_payload_limit` | `app/core/Audio/tokenizer_service.py` | Tokenizer payload limit. |
| `_enforce_payload_size` | `app/core/Audio/tokenizer_service.py` | Tokenizer payload limit. |
| `_read_audio_from_bytes` | `app/core/Audio/tokenizer_service.py` | Tokenizer audio load. |
| `_resolve_tokenizer_sample_rate` | `app/core/Audio/tokenizer_service.py` | Tokenizer output metadata. |
| `_resolve_tokenizer_frame_rate` | `app/core/Audio/tokenizer_service.py` | Tokenizer output metadata. |
| `_instantiate_tokenizer` | `app/core/Audio/tokenizer_service.py` | Tokenizer load helper. |
| `_load_qwen3_tokenizer` | `app/core/Audio/tokenizer_service.py` | Tokenizer load helper. |
| `_normalize_tokens` | `app/core/Audio/tokenizer_service.py` | Tokenizer output normalization. |
| `_serialize_tokens` | `app/core/Audio/tokenizer_service.py` | Tokenizer response formatting. |
| `_coerce_tokens_payload` | `app/core/Audio/tokenizer_service.py` | Tokenizer response formatting. |
| `_serialize_audio_output` | `app/core/Audio/tokenizer_service.py` | Tokenizer decode output. |
| `_stream_tts_to_websocket` | `app/core/Audio/streaming_service.py` | Shared TTS stream helper. |
| Metrics registration block (`audio_failopen_*`) | `app/core/Audio/streaming_service.py` | Keep idempotent registration. |
| `EXPECTED_DB_EXC` | `app/core/Audio/quota_helpers.py` | Imported by transcription + streaming. |
| `EXPECTED_REDIS_EXC` | `app/core/Audio/quota_helpers.py` | Imported by streaming. |
| `_get_failopen_cap_minutes` | `app/core/Audio/quota_helpers.py` | Fail-open cap helper. |
| `_infer_tts_provider_from_model` | `app/core/Audio/tts_service.py` | TTS sanitization helper. |
| `_valid_whisper_model_sizes` | `app/core/Audio/transcription_service.py` | Shared STT helper. |
| `_map_openai_audio_model_to_whisper` | `app/core/Audio/transcription_service.py` | Shared STT helper. |
| `get_tts_service` | `app/api/v1/endpoints/audio_tts.py` | FastAPI dependency wrapper. |
| `_raise_for_tts_error` | `app/core/Audio/tts_service.py` | Endpoint-level error mapping. |
| `_sanitize_speech_request` | `app/core/Audio/tts_service.py` | Input validation. |
| `_tts_fallback_resolver` | `app/core/Audio/tts_service.py` | BYOK fallback resolver. |
| `_resolve_tts_byok` | `app/core/Audio/tts_service.py` | BYOK resolution. |
| `create_speech` | `app/api/v1/endpoints/audio_tts.py` | Endpoint wrapper. |
| `create_speech_metadata` | `app/api/v1/endpoints/audio_tts.py` | Endpoint wrapper. |
| `encode_audio_tokenizer` | `app/api/v1/endpoints/audio_tokenizer.py` | Endpoint wrapper. |
| `decode_audio_tokenizer` | `app/api/v1/endpoints/audio_tokenizer.py` | Endpoint wrapper. |
| `create_transcription` | `app/api/v1/endpoints/audio_transcriptions.py` | Endpoint wrapper; calls core service. |
| `create_translation` | `app/api/v1/endpoints/audio_transcriptions.py` | Endpoint wrapper. |
| `segment_transcript` | `app/api/v1/endpoints/audio_transcriptions.py` | Endpoint wrapper. |
| `audio_chat_turn` | `app/api/v1/endpoints/audio_streaming.py` | Non-streaming chat stays with streaming. |
| `get_tts_health` | `app/api/v1/endpoints/audio_health.py` | Endpoint wrapper. |
| `get_stt_health` | `app/api/v1/endpoints/audio_health.py` | Endpoint wrapper; uses transcription service helpers. |
| `list_tts_providers` | `app/api/v1/endpoints/audio_tts.py` | Endpoint wrapper. |
| `list_tts_voices` | `app/api/v1/endpoints/audio_tts.py` | Endpoint wrapper. |
| `reset_tts_metrics` | `app/api/v1/endpoints/audio_tts.py` | Endpoint wrapper. |
| `_audio_ws_authenticate` | `app/core/Audio/streaming_service.py` | Shared WS auth helper. |
| `websocket_transcribe` | `app/api/v1/endpoints/audio_streaming.py` | WS endpoint. |
| `websocket_audio_chat_stream` | `app/api/v1/endpoints/audio_streaming.py` | WS endpoint. |
| `websocket_tts` | `app/api/v1/endpoints/audio_streaming.py` | WS endpoint. |
| `websocket_tts_realtime` | `app/api/v1/endpoints/audio_streaming.py` | WS endpoint. |
| `streaming_status` | `app/api/v1/endpoints/audio_streaming.py` | HTTP endpoint. |
| `streaming_limits` | `app/api/v1/endpoints/audio_streaming.py` | HTTP endpoint. |
| `test_streaming` | `app/api/v1/endpoints/audio_streaming.py` | HTTP endpoint. |
| `upload_voice` | `app/api/v1/endpoints/audio_voices.py` | HTTP endpoint. |
| `encode_voice_reference` | `app/api/v1/endpoints/audio_voices.py` | HTTP endpoint. |
| `list_voices` | `app/api/v1/endpoints/audio_voices.py` | HTTP endpoint. |
| `get_voice_details` | `app/api/v1/endpoints/audio_voices.py` | HTTP endpoint. |
| `delete_voice` | `app/api/v1/endpoints/audio_voices.py` | HTTP endpoint. |
| `preview_voice` | `app/api/v1/endpoints/audio_voices.py` | HTTP endpoint. |

## New File Stubs
Minimal scaffolding for the new modules (placeholders; actual logic moved verbatim).

```python
# tldw_Server_API/app/api/v1/endpoints/audio.py
from fastapi import APIRouter
from tldw_Server_API.app.api.v1.endpoints import (
    audio_tts,
    audio_tokenizer,
    audio_transcriptions,
    audio_streaming,
    audio_health,
    audio_voices,
)
from tldw_Server_API.app.core.Usage.audio_quota import (
    can_start_job as can_start_job,
    finish_job as finish_job,
    increment_jobs_started as increment_jobs_started,
    get_limits_for_user as get_limits_for_user,
)

router = APIRouter(tags=["Audio"])
router.include_router(audio_tts.router)
router.include_router(audio_tokenizer.router)
router.include_router(audio_transcriptions.router)
router.include_router(audio_streaming.router)
router.include_router(audio_health.router)
router.include_router(audio_voices.router)

ws_router = audio_streaming.ws_router
```

```python
# tldw_Server_API/app/api/v1/endpoints/audio_tts.py
from fastapi import APIRouter

router = APIRouter(tags=["Audio"])

async def create_speech(...): ...
async def create_speech_metadata(...): ...
async def list_tts_providers(...): ...
async def list_tts_voices(...): ...
async def reset_tts_metrics(...): ...
```

```python
# tldw_Server_API/app/api/v1/endpoints/audio_tokenizer.py
from fastapi import APIRouter

router = APIRouter(tags=["Audio"])

async def encode_audio_tokenizer(...): ...
async def decode_audio_tokenizer(...): ...
```

```python
# tldw_Server_API/app/api/v1/endpoints/audio_transcriptions.py
from fastapi import APIRouter

router = APIRouter(tags=["Audio"])

async def create_transcription(...): ...
async def create_translation(...): ...
async def segment_transcript(...): ...
```

```python
# tldw_Server_API/app/api/v1/endpoints/audio_streaming.py
from fastapi import APIRouter

router = APIRouter(tags=["Audio"])
ws_router = APIRouter()

async def audio_chat_turn(...): ...
async def streaming_status(...): ...
async def streaming_limits(...): ...
async def test_streaming(...): ...

@ws_router.websocket("/stream/transcribe")
async def websocket_transcribe(...): ...
@ws_router.websocket("/chat/stream")
async def websocket_audio_chat_stream(...): ...
@ws_router.websocket("/stream/tts")
async def websocket_tts(...): ...
@ws_router.websocket("/stream/tts/realtime")
async def websocket_tts_realtime(...): ...
```

```python
# tldw_Server_API/app/api/v1/endpoints/audio_health.py
from fastapi import APIRouter

router = APIRouter(tags=["Audio"])

async def get_tts_health(...): ...
async def get_stt_health(...): ...
```

```python
# tldw_Server_API/app/api/v1/endpoints/audio_voices.py
from fastapi import APIRouter

router = APIRouter(tags=["Audio"])

async def upload_voice(...): ...
async def encode_voice_reference(...): ...
async def list_voices(...): ...
async def get_voice_details(...): ...
async def delete_voice(...): ...
async def preview_voice(...): ...
```

```python
# tldw_Server_API/app/core/Audio/tts_service.py
def _infer_tts_provider_from_model(...): ...
def _raise_for_tts_error(...): ...
def _sanitize_speech_request(...): ...
def _tts_fallback_resolver(...): ...
async def _resolve_tts_byok(...): ...
```

```python
# tldw_Server_API/app/core/Audio/transcription_service.py
def _valid_whisper_model_sizes(...): ...
def _map_openai_audio_model_to_whisper(...): ...
async def run_transcription_pipeline(...): ...
```

```python
# tldw_Server_API/app/core/Audio/tokenizer_service.py
def _get_qwen3_tokenizer_settings(...): ...
def _decode_base64_payload(...): ...
def _read_audio_from_bytes(...): ...
def _load_qwen3_tokenizer(...): ...
def _normalize_tokens(...): ...
def _serialize_tokens(...): ...
def _serialize_audio_output(...): ...
```

```python
# tldw_Server_API/app/core/Audio/streaming_service.py
def _get_chat_history_max_messages(...): ...
async def _stream_tts_to_websocket(...): ...
async def _audio_ws_authenticate(...): ...
```

```python
# tldw_Server_API/app/core/Audio/error_payloads.py
def _debug_error_details_enabled(...): ...
def _maybe_debug_details(...): ...
def _http_error_detail(...): ...
def _ws_error_payload(...): ...
```

```python
# tldw_Server_API/app/core/Audio/quota_helpers.py
EXPECTED_DB_EXC = (...)
EXPECTED_REDIS_EXC = (...)
def _get_failopen_cap_minutes(...): ...
```

## Functional Requirements
- All routes and WS paths remain identical.
- Response bodies, headers, and status codes remain unchanged.
- Rate limits, quotas, and BYOK behavior unchanged.
- Existing logging and metrics remain at equivalent points in the flow.
- Re-exported test shims remain importable from `audio.py`.

## Non-Functional Requirements
- No additional startup latency from imports.
- Avoid circular imports between endpoint modules.
- Keep dependencies and config lookups unchanged.

## Implementation Strategy (Incremental)
1. Extract shared helpers and move them into core services while re-exporting from `audio.py`.
2. Split endpoint routers module-by-module with minimal code changes.
3. Aggregate routers in `audio.py` and confirm OpenAPI parity.
4. Ensure existing tests and monkeypatching remain functional.

## Testing Plan
- Unit tests for new core services (tokenizer, transcription, streaming helpers).
- Integration tests for `/speech`, `/transcriptions`, `/translations`, `/tokenizer/*`.
- WebSocket smoke tests for `/stream/transcribe` and `/stream/tts`.
- Verify OpenAPI route list is unchanged (order can differ).

## Success Criteria
- `audio.py` reduced to <500 lines and primarily aggregates routers.
- No API compatibility regressions.
- Tests pass without changes to client expectations.

## Risks and Mitigations
- **Circular imports:** keep helper modules in core and avoid inter-endpoint dependencies.
- **Behavior drift:** move code verbatim, then refactor incrementally.
- **WebSocket regressions:** keep auth/quota logic centralized and unchanged.

## Open Questions (None)
All key placement decisions are resolved (core services, `/chat` placement, TTS voices location).
