# Fish Audio S2 Pro TTS Registry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Fish Audio S2 Pro to the tldw TTS registry as a remote-first provider with managed reference workflows, user-safe reference mapping, and honest streaming/validation behavior.

**Architecture:** Implement one canonical `fish_s2` provider in the adapter registry, backed in v1 by a new native HTTP backend that talks to Fish’s upstream server. Reuse `voice_manager` metadata as the authoritative user-scoped reference store, keep Fish-managed references out of the global voices catalog, and expose provider-specific reference CRUD under the audio namespace.

**Tech Stack:** FastAPI, Pydantic, Loguru, tldw `http_client`, adapter registry / `TTSServiceV2`, `voice_manager`, pytest, Bandit.

---

### Task 1: Add Registry, Config, And Validation Scaffolding

**Files:**
- Modify: `tldw_Server_API/app/core/TTS/adapter_registry.py`
- Modify: `tldw_Server_API/app/core/TTS/tts_validation.py`
- Modify: `tldw_Server_API/app/core/TTS/voice_manager.py`
- Modify: `tldw_Server_API/Config_Files/tts_providers_config.yaml`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/test_fish_s2_registry.py`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_fish_s2.py`

**Step 1: Write the failing tests**

```python
from tldw_Server_API.app.core.TTS.adapter_registry import TTSAdapterFactory, TTSProvider
from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.tts_validation import validate_tts_request


def test_fish_s2_aliases_resolve_to_provider():
    factory = TTSAdapterFactory(config={"providers": {"fish_s2": {"enabled": True}}})
    assert factory.get_provider_for_model("s2-pro") == TTSProvider.FISH_S2
    assert factory.get_provider_for_model("fishaudio/s2-pro") == TTSProvider.FISH_S2


def test_fish_s2_streaming_requires_wav():
    request = TTSRequest(
        text="hello",
        provider="fish_s2",
        format=AudioFormat.MP3,
        stream=True,
        extra_params={"reference_id": "voice-123"},
    )
    validate_tts_request(request, provider="fish_s2")
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest -q \
  tldw_Server_API/tests/TTS_NEW/unit/test_fish_s2_registry.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_fish_s2.py
```

Expected:

- FAIL because `TTSProvider.FISH_S2` does not exist yet
- FAIL because Fish-specific validation does not exist yet

**Step 3: Write minimal implementation**

```python
# adapter_registry.py
class TTSProvider(Enum):
    FISH_S2 = "fish_s2"


MODEL_PROVIDER_MAP.update(
    {
        "fish_s2": TTSProvider.FISH_S2,
        "fish-s2": TTSProvider.FISH_S2,
        "fish-s2-pro": TTSProvider.FISH_S2,
        "s2-pro": TTSProvider.FISH_S2,
        "fishaudio/s2-pro": TTSProvider.FISH_S2,
    }
)

# tts_validation.py
ProviderLimits.LIMITS["fish_s2"] = {
    "max_text_length": 5000,
    "valid_formats": {"wav", "mp3", "pcm"},
    "min_speed": 0.25,
    "max_speed": 4.0,
}
```

Also add:

- `DEFAULT_ADAPTERS[TTSProvider.FISH_S2]` pointing at the new adapter path
- a `fish_s2` block in `tts_providers_config.yaml`
- a `fish_s2` entry in `voice_manager.PROVIDER_REQUIREMENTS`

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest -q \
  tldw_Server_API/tests/TTS_NEW/unit/test_fish_s2_registry.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_fish_s2.py
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/TTS/adapter_registry.py \
  tldw_Server_API/app/core/TTS/tts_validation.py \
  tldw_Server_API/app/core/TTS/voice_manager.py \
  tldw_Server_API/Config_Files/tts_providers_config.yaml \
  tldw_Server_API/tests/TTS_NEW/unit/test_fish_s2_registry.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_fish_s2.py
git commit -m "feat(tts): add fish s2 registry and validation scaffold"
```

### Task 2: Implement The Native Fish HTTP Backend

**Files:**
- Create: `tldw_Server_API/app/core/TTS/backends/__init__.py`
- Create: `tldw_Server_API/app/core/TTS/backends/fish_s2_base.py`
- Create: `tldw_Server_API/app/core/TTS/backends/fish_s2_native_http.py`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/adapters/test_fish_s2_native_http_backend.py`

**Step 1: Write the failing test**

```python
import pytest

from tldw_Server_API.app.core.TTS.backends.fish_s2_native_http import FishS2NativeHttpBackend


@pytest.mark.asyncio
async def test_backend_builds_tts_payload_from_request(monkeypatch):
    backend = FishS2NativeHttpBackend(
        {"base_url": "http://fish.local", "api_key": "secret", "timeout": 30}
    )

    captured = {}

    async def fake_fetch(*, method, url, json=None, headers=None, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return b"fake-audio"

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.backends.fish_s2_native_http.afetch",
        fake_fetch,
    )

    await backend.synthesize(
        text="hello",
        response_format="wav",
        streaming=False,
        reference_id="tldw_u1_vabc",
        extra_params={"chunk_length": 200, "normalize": True},
    )

    assert captured["url"].endswith("/v1/tts")
    assert captured["json"]["reference_id"] == "tldw_u1_vabc"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/adapters/test_fish_s2_native_http_backend.py
```

Expected:

- FAIL because the backend module does not exist yet

**Step 3: Write minimal implementation**

```python
class FishS2Backend(Protocol):
    async def synthesize(...): ...
    async def add_reference(...): ...
    async def list_references(...): ...
    async def delete_reference(...): ...


class FishS2NativeHttpBackend:
    async def synthesize(self, *, text, response_format, streaming, reference_id=None, extra_params=None):
        payload = {
            "text": text,
            "format": response_format,
            "streaming": streaming,
        }
        if reference_id:
            payload["reference_id"] = reference_id
        if extra_params:
            payload.update(extra_params)
        return await afetch(method="POST", url=f"{self.base_url}/v1/tts", json=payload, headers=self._headers())
```

Implement the remaining backend methods:

- `health_check()` via `/v1/health`
- `add_reference()` via multipart form to `/v1/references/add`
- `list_references()` via `/v1/references/list`
- `delete_reference()` via `/v1/references/delete`
- HTTP status to TTS exception mapping

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/adapters/test_fish_s2_native_http_backend.py
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/TTS/backends/__init__.py \
  tldw_Server_API/app/core/TTS/backends/fish_s2_base.py \
  tldw_Server_API/app/core/TTS/backends/fish_s2_native_http.py \
  tldw_Server_API/tests/TTS_NEW/unit/adapters/test_fish_s2_native_http_backend.py
git commit -m "feat(tts): add fish s2 native http backend"
```

### Task 3: Implement The Fish S2 Adapter

**Files:**
- Create: `tldw_Server_API/app/core/TTS/adapters/fish_s2_adapter.py`
- Modify: `tldw_Server_API/app/core/TTS/adapters/__init__.py`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/adapters/test_fish_s2_adapter.py`

**Step 1: Write the failing test**

```python
import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.fish_s2_adapter import FishS2Adapter


@pytest.mark.asyncio
async def test_adapter_reports_honest_capabilities():
    adapter = FishS2Adapter({"backend": "native_http", "base_url": "http://fish.local"})
    caps = await adapter.get_capabilities()
    assert caps.supports_voice_cloning is True
    assert caps.supported_formats == {AudioFormat.WAV, AudioFormat.MP3, AudioFormat.PCM}
    assert caps.supported_voices == []


@pytest.mark.asyncio
async def test_adapter_maps_request_into_backend_call(monkeypatch):
    adapter = FishS2Adapter({"backend": "native_http", "base_url": "http://fish.local"})
    called = {}

    async def fake_synthesize(**kwargs):
        called.update(kwargs)
        return b"audio"

    adapter._backend = type("B", (), {"synthesize": fake_synthesize})()
    await adapter.generate(TTSRequest(text="hello", format=AudioFormat.WAV, extra_params={"reference_id": "voice-1"}))
    assert called["reference_id"] == "voice-1"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/adapters/test_fish_s2_adapter.py
```

Expected:

- FAIL because the adapter module does not exist yet

**Step 3: Write minimal implementation**

```python
class FishS2Adapter(TTSAdapter):
    PROVIDER_KEY = "fish_s2"

    async def get_capabilities(self) -> TTSCapabilities:
        return TTSCapabilities(
            provider_name="Fish Audio S2",
            supported_languages=set(),
            supported_voices=[],
            supported_formats={AudioFormat.WAV, AudioFormat.MP3, AudioFormat.PCM},
            max_text_length=5000,
            supports_streaming=True,
            supports_voice_cloning=True,
            supports_multi_speaker=False,
            default_format=AudioFormat.WAV,
        )

    async def generate(self, request: TTSRequest) -> TTSResponse:
        audio = await self._backend.synthesize(...)
        return TTSResponse(audio_data=audio, format=request.format, provider=self.PROVIDER_KEY)
```

Be explicit that:

- built-in voices are empty
- v1 does not advertise multi-speaker support
- `lang_code` is ignored / best-effort only for the native backend

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/adapters/test_fish_s2_adapter.py
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/TTS/adapters/fish_s2_adapter.py \
  tldw_Server_API/app/core/TTS/adapters/__init__.py \
  tldw_Server_API/tests/TTS_NEW/unit/adapters/test_fish_s2_adapter.py
git commit -m "feat(tts): add fish s2 adapter"
```

### Task 4: Reuse Voice Metadata And Wire `TTSServiceV2`

**Files:**
- Modify: `tldw_Server_API/app/core/TTS/voice_manager.py`
- Modify: `tldw_Server_API/app/core/TTS/tts_service_v2.py`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/test_tts_service.py`

**Step 1: Write the failing test**

```python
import pytest
from unittest.mock import AsyncMock

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.tts_service_v2 import TTSServiceV2


@pytest.mark.asyncio
async def test_fish_reference_id_resolves_from_local_voice_metadata(tts_service, monkeypatch):
    request = TTSRequest(
        text="hello",
        provider="fish_s2",
        format=AudioFormat.WAV,
        extra_params={"reference_id": "voice-123"},
    )

    metadata = type(
        "Meta",
        (),
        {
            "provider_artifacts": {
                "fish_s2": {"remote_reference_id": "tldw_u1_vvoice-123", "reference_text": "hello ref"}
            },
            "reference_text": "hello ref",
        },
    )()

    fake_manager = type(
        "VM",
        (),
        {
            "load_reference_metadata": AsyncMock(return_value=metadata),
            "load_voice_reference_audio": AsyncMock(return_value=b"RIFF...."),
        },
    )()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_service_v2.get_voice_manager",
        lambda: fake_manager,
    )

    await tts_service._resolve_fish_s2_reference(request, user_id=1)
    assert request.extra_params["remote_reference_id"] == "tldw_u1_vvoice-123"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/test_tts_service.py -k fish_s2
```

Expected:

- FAIL because the Fish-specific resolution helper does not exist yet

**Step 3: Write minimal implementation**

```python
async def _resolve_fish_s2_reference(self, request: TTSRequest, user_id: int | None) -> None:
    if not user_id:
        return
    extras = request.extra_params or {}
    reference_id = extras.get("reference_id")
    if not reference_id:
        return
    metadata = await voice_manager.load_reference_metadata(user_id, reference_id)
    fish = (metadata.provider_artifacts or {}).get("fish_s2", {})
    if fish.get("remote_reference_id"):
        extras["remote_reference_id"] = fish["remote_reference_id"]
    request.extra_params = extras
```

Extend this to:

- create the remote Fish reference on demand when `voice=custom:<voice_id>` is used and no mapping exists
- save `provider_artifacts["fish_s2"]`
- remove Fish artifacts cleanly during provider-route delete flow

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest -q tldw_Server_API/tests/TTS_NEW/unit/test_tts_service.py -k fish_s2
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/core/TTS/voice_manager.py \
  tldw_Server_API/app/core/TTS/tts_service_v2.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_tts_service.py
git commit -m "feat(tts): wire fish s2 references through voice metadata"
```

### Task 5: Add Fish Provider Reference Routes

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/audio/audio_fish.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/audio.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/__init__.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/audio_schemas.py`
- Test: `tldw_Server_API/tests/TTS_NEW/integration/test_fish_s2_reference_endpoints.py`

**Step 1: Write the failing test**

```python
def test_create_fish_reference_from_existing_voice(test_client, auth_headers, monkeypatch):
    async def fake_create_reference(*args, **kwargs):
        return {"reference_id": "voice-123", "remote_reference_id": "tldw_u1_vvoice-123"}

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.audio.audio_fish.create_fish_reference_for_voice",
        fake_create_reference,
    )

    response = test_client.post(
        "/api/v1/audio/providers/fish_s2/references",
        json={"voice_id": "voice-123", "reference_text": "Reference transcript"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["reference_id"] == "voice-123"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest -q tldw_Server_API/tests/TTS_NEW/integration/test_fish_s2_reference_endpoints.py
```

Expected:

- FAIL because the route module and schemas do not exist yet

**Step 3: Write minimal implementation**

```python
router = APIRouter(tags=["Audio"])


@router.post("/providers/fish_s2/references")
async def create_fish_reference(...):
    ...


@router.get("/providers/fish_s2/references")
async def list_fish_references(...):
    ...


@router.delete("/providers/fish_s2/references/{reference_id}")
async def delete_fish_reference(...):
    ...
```

Route rules:

- keep auth posture aligned with existing audio voice endpoints
- support `voice_id`-based creation from an existing stored voice
- support new-upload creation by first calling `voice_manager.upload_voice`
- list from local metadata, not upstream global reference listing
- delete remote Fish mapping but keep the local voice record

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest -q tldw_Server_API/tests/TTS_NEW/integration/test_fish_s2_reference_endpoints.py
```

Expected:

- PASS

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/endpoints/audio/audio_fish.py \
  tldw_Server_API/app/api/v1/endpoints/audio/audio.py \
  tldw_Server_API/app/api/v1/endpoints/audio/__init__.py \
  tldw_Server_API/app/api/v1/schemas/audio_schemas.py \
  tldw_Server_API/tests/TTS_NEW/integration/test_fish_s2_reference_endpoints.py
git commit -m "feat(audio): add fish s2 managed reference routes"
```

### Task 6: Cover `/audio/speech`, Docs, And Verification

**Files:**
- Modify: `tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py`
- Create: `Docs/STT-TTS/FISH_S2_SETUP.md`
- Modify: `tldw_Server_API/app/core/TTS/TTS-README.md`
- Modify: `tldw_Server_API/Config_Files/tts_providers_config.yaml`

**Step 1: Write the failing test**

```python
def test_generate_fish_s2_audio(test_client, auth_headers, monkeypatch):
    async def fake_generate(request_obj, *args, **kwargs):
        request_obj._tts_metadata = {"provider": "fish_s2"}
        yield b"RIFF...."

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_service_v2.TTSServiceV2.generate_speech",
        fake_generate,
    )

    response = test_client.post(
        "/api/v1/audio/speech",
        json={
            "input": "Hello Fish",
            "model": "s2-pro",
            "response_format": "wav",
            "stream": False,
            "extra_params": {"reference_id": "voice-123"},
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/")
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest -q \
  tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py -k fish_s2
```

Expected:

- FAIL because the model alias / request path is not fully integrated yet

**Step 3: Write minimal implementation**

```python
# Docs/STT-TTS/FISH_S2_SETUP.md should document:
# - upstream Fish server startup
# - tldw fish_s2 config
# - managed reference routes
# - WAV-only streaming limitation
# - use of custom:<voice_id> and extra_params.reference_id
```

Finish the integration surface:

- ensure `/api/v1/audio/speech` accepts Fish aliases end to end
- update docs and config comments to describe remote-first setup
- explicitly document that managed Fish references do not appear in the global
  voices catalog in v1

**Step 4: Run verification**

Run:

```bash
source .venv/bin/activate
python -m pytest -q \
  tldw_Server_API/tests/TTS_NEW/unit/test_fish_s2_registry.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_fish_s2.py \
  tldw_Server_API/tests/TTS_NEW/unit/adapters/test_fish_s2_native_http_backend.py \
  tldw_Server_API/tests/TTS_NEW/unit/adapters/test_fish_s2_adapter.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_tts_service.py -k fish_s2 \
  tldw_Server_API/tests/TTS_NEW/integration/test_fish_s2_reference_endpoints.py \
  tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py -k fish_s2

python -m bandit -r \
  tldw_Server_API/app/core/TTS/adapters/fish_s2_adapter.py \
  tldw_Server_API/app/core/TTS/backends/fish_s2_native_http.py \
  tldw_Server_API/app/api/v1/endpoints/audio/audio_fish.py \
  tldw_Server_API/app/core/TTS/tts_service_v2.py \
  tldw_Server_API/app/core/TTS/voice_manager.py \
  -f json -o /tmp/bandit_fish_s2.json
```

Expected:

- focused pytest suite PASS
- Bandit completes with no new findings in touched code

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py \
  Docs/STT-TTS/FISH_S2_SETUP.md \
  tldw_Server_API/app/core/TTS/TTS-README.md \
  tldw_Server_API/Config_Files/tts_providers_config.yaml
git commit -m "docs(tts): add fish s2 setup guide and verification"
```

## Notes For The Implementer

- Do not put Fish managed references into `/api/v1/audio/voices/catalog` in v1.
- Treat local `voice_id` as the public `reference_id`; keep backend remote IDs internal.
- Reuse `voice_manager` metadata instead of introducing a second reference store.
- Prefer existing auth / rate-limit posture from audio voice endpoints.
- Do not silently transcode streamed `mp3`; reject it for `fish_s2` native HTTP in v1.
- Keep `lang_code` best-effort or ignored for the native backend until a backend actually supports explicit language selection.

## Suggested Commit Sequence

1. `feat(tts): add fish s2 registry and validation scaffold`
2. `feat(tts): add fish s2 native http backend`
3. `feat(tts): add fish s2 adapter`
4. `feat(tts): wire fish s2 references through voice metadata`
5. `feat(audio): add fish s2 managed reference routes`
6. `docs(tts): add fish s2 setup guide and verification`
