# Chatterbox Upstream Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update tldw's Chatterbox integration to support the current upstream TTS family (standard, multilingual, Turbo) and add dedicated voice-conversion support while keeping watermark removal enabled by default.

**Architecture:** Keep `chatterbox` as one provider for TTS, add a Chatterbox family mode resolver inside the adapter/validation layers, and expose voice conversion through a dedicated audio endpoint instead of as a text-to-speech model alias. Refactor shared audio response helpers so TTS and VC can reuse persistence/history/header behavior without duplicating endpoint logic.

**Tech Stack:** FastAPI, Pydantic, existing TTS adapter registry/service, Chatterbox upstream package, pytest, Bandit.

---

## Stage 1: Establish Chatterbox Catalog And Config Surface
**Goal**: Create one backend source of truth for Chatterbox TTS model aliases and update config/install surfaces for the current upstream family.
**Success Criteria**: Canonical model ids exist in one place, registry/schema/config reference them consistently, and the Chatterbox install extra covers the runtime imports needed for Turbo/VC.
**Tests**: Alias resolution unit tests; config/registry smoke tests.
**Status**: Not Started

### Task 1: Add a canonical Chatterbox model catalog

**Files:**
- Modify: `tldw_Server_API/app/core/TTS/adapter_registry.py`
- Modify: `tldw_Server_API/app/core/Audio/tts_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/audio_schemas.py`
- Test: `tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py`

**Step 1: Write the failing test**

Add assertions covering new aliases and the rule that VC is not part of the TTS model alias set.

```python
def test_chatterbox_model_aliases_resolve_to_provider():
    assert model_to_provider_map["chatterbox"] == TTSProvider.CHATTERBOX
    assert model_to_provider_map["chatterbox-emotion"] == TTSProvider.CHATTERBOX
    assert model_to_provider_map["chatterbox-multilingual"] == TTSProvider.CHATTERBOX
    assert model_to_provider_map["chatterbox-turbo"] == TTSProvider.CHATTERBOX
    assert "chatterbox-vc" not in model_to_provider_map
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py -k aliases -v
```

Expected: FAIL because the new aliases are not registered yet.

**Step 3: Write minimal implementation**

- Add a Chatterbox alias catalog constant.
- Reuse that constant in registry alias mapping and provider inference.
- Update `OpenAISpeechRequest.model` description to list canonical Chatterbox TTS ids only.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py -k aliases -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/adapter_registry.py tldw_Server_API/app/core/Audio/tts_service.py tldw_Server_API/app/api/v1/schemas/audio_schemas.py tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py
git commit -m "feat: centralize chatterbox model aliases"
```

### Task 2: Update config and install extras for current upstream family

**Files:**
- Modify: `pyproject.toml`
- Modify: `tldw_Server_API/Config_Files/tts_providers_config.yaml`
- Modify: `Docs/STT-TTS/CHATTERBOX_SETUP.md`
- Test: `tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py`

**Step 1: Write the failing test**

Add a config-focused test that expects the adapter to understand a `variant` setting and preserve `disable_watermark=True`.

```python
def test_chatterbox_variant_config_defaults():
    adapter = ChatterboxAdapter({"variant": "turbo", "disable_watermark": True})
    assert adapter.config.get("variant") == "turbo"
    assert adapter.disable_watermark is True
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py -k variant_config -v
```

Expected: FAIL or require adapter changes.

**Step 3: Write minimal implementation**

- Expand `TTS_chatterbox` extras to include current runtime imports needed by Turbo/VC.
- Replace the stale `model_path ... unused` config note with real `model_path`, `turbo_model_path`, and `variant` fields.
- Update Chatterbox setup docs accordingly.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py -k variant_config -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml tldw_Server_API/Config_Files/tts_providers_config.yaml Docs/STT-TTS/CHATTERBOX_SETUP.md tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py
git commit -m "feat: refresh chatterbox config and install surface"
```

## Stage 2: Implement Chatterbox Family Mode Resolution
**Goal**: Teach the adapter to resolve standard, multilingual, and Turbo families cleanly and clean them up correctly.
**Success Criteria**: Request model aliases and config variant select the right upstream runtime, watermark stripping still works, and cleanup clears every loaded family.
**Tests**: Adapter unit tests for family selection, cleanup, and unsupported Turbo controls.
**Status**: Not Started

### Task 3: Add family resolution and runtime caching to the adapter

**Files:**
- Modify: `tldw_Server_API/app/core/TTS/adapters/chatterbox_adapter.py`
- Test: `tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py`

**Step 1: Write the failing test**

Add tests for mode resolution and runtime cleanup.

```python
@pytest.mark.asyncio
async def test_chatterbox_resolves_turbo_from_request_model():
    adapter = ChatterboxAdapter({"variant": "standard"})
    request = TTSRequest(text="Hi", model="chatterbox-turbo")
    assert adapter._resolve_family_mode(request, language_id="en") == "turbo"

@pytest.mark.asyncio
async def test_close_clears_all_chatterbox_runtimes():
    adapter = ChatterboxAdapter({})
    adapter.model_en = object()
    adapter.model_multi = object()
    adapter.model_turbo = object()
    adapter.model_vc = object()
    await adapter.close()
    assert adapter.model_en is None
    assert adapter.model_multi is None
    assert adapter.model_turbo is None
    assert adapter.model_vc is None
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py -k "turbo or close_clears" -v
```

Expected: FAIL because Turbo/VC runtime state does not exist yet.

**Step 3: Write minimal implementation**

- Add explicit family resolution helper.
- Add lazy runtime slots for Turbo and VC.
- Route standard/multilingual/turbo generation through the correct upstream loader.
- Expand cleanup/resource-manager registration to cover every family.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py -k "turbo or close_clears" -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/adapters/chatterbox_adapter.py tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py
git commit -m "feat: add chatterbox family mode resolution"
```

### Task 4: Preserve transparent Turbo behavior

**Files:**
- Modify: `tldw_Server_API/app/core/TTS/adapters/chatterbox_adapter.py`
- Test: `tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py`

**Step 1: Write the failing test**

Add a test that Turbo ignores unsupported controls but reports that fact.

```python
@pytest.mark.asyncio
async def test_turbo_ignores_unsupported_cfg_and_exaggeration(monkeypatch):
    adapter = ChatterboxAdapter({})
    request = TTSRequest(
        text="Hello [laugh]",
        model="chatterbox-turbo",
        extra_params={"cfg_weight": 0.5},
        emotion="happy",
    )
    metadata = adapter._build_generation_metadata(request, family_mode="turbo")
    assert metadata["family_mode"] == "turbo"
    assert metadata["ignored_controls"] == ["cfg_weight", "emotion", "emotion_intensity", "exaggeration"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py -k ignored_controls -v
```

Expected: FAIL because the adapter does not expose this metadata yet.

**Step 3: Write minimal implementation**

- Add Turbo-specific metadata reporting.
- Ensure unsupported controls are ignored intentionally rather than applied accidentally.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py -k ignored_controls -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/adapters/chatterbox_adapter.py tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py
git commit -m "feat: make chatterbox turbo control handling explicit"
```

## Stage 3: Make Validation And TTS Request Plumbing Mode-Aware
**Goal**: Update validation and service plumbing so the Chatterbox family behaves correctly without breaking existing callers.
**Success Criteria**: TTS validation distinguishes standard/multilingual/turbo, existing aliases remain backward compatible, and schema/discovery surfaces reflect the new TTS ids.
**Tests**: Validation unit tests and endpoint integration tests.
**Status**: Not Started

### Task 5: Add Chatterbox family-aware validation

**Files:**
- Modify: `tldw_Server_API/app/core/TTS/tts_validation.py`
- Test: `tldw_Server_API/tests/TTS/test_tts_validation.py`

**Step 1: Write the failing test**

Add tests for multilingual languages and Turbo-specific behavior.

```python
def test_chatterbox_multilingual_accepts_fr():
    validator = TTSInputValidator({})
    request = TTSRequest(text="Bonjour", model="chatterbox-multilingual", language="fr")
    ok, error = validator.validate_request(request, provider="chatterbox")
    assert ok is True
    assert error is None

def test_chatterbox_standard_rejects_fr():
    validator = TTSInputValidator({})
    request = TTSRequest(text="Bonjour", model="chatterbox", language="fr")
    ok, error = validator.validate_request(request, provider="chatterbox")
    assert ok is False
    assert "Language" in error
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/test_tts_validation.py -k chatterbox -v
```

Expected: FAIL because validation only knows provider-wide `chatterbox`.

**Step 3: Write minimal implementation**

- Add Chatterbox family resolution in the validator from `request.model`.
- Update supported languages/formats/reference handling to use family-specific rules.
- Keep `model="chatterbox"` and `model="chatterbox-emotion"` backward compatible.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/test_tts_validation.py -k chatterbox -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/tts_validation.py tldw_Server_API/tests/TTS/test_tts_validation.py
git commit -m "feat: add chatterbox family-aware validation"
```

## Stage 4: Add Dedicated Voice Conversion Support
**Goal**: Add a dedicated Chatterbox VC endpoint and adapter path without polluting the text-to-speech model catalog.
**Success Criteria**: VC requests accept source audio plus target voice input, reuse stored custom voices when provided, and return converted audio successfully.
**Tests**: VC adapter unit tests and endpoint integration tests.
**Status**: Not Started

### Task 6: Add VC schema and endpoint with shared response helpers

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/audio/audio_voice_conversion.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/audio.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/__init__.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/audio_schemas.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/audio/audio_response_helpers.py`
- Test: `tldw_Server_API/tests/TTS_NEW/integration/test_chatterbox_voice_conversion_endpoint.py`

**Step 1: Write the failing test**

Add an integration test for the new endpoint.

```python
def test_chatterbox_voice_conversion_requires_target_voice(test_client, auth_headers):
    payload = {
        "input_audio": BASE64_WAV,
        "input_audio_format": "wav",
        "response_format": "wav",
    }
    response = test_client.post("/api/v1/audio/voice-conversion", json=payload, headers=auth_headers)
    assert response.status_code == 422
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS_NEW/integration/test_chatterbox_voice_conversion_endpoint.py -v
```

Expected: FAIL because the endpoint does not exist yet.

**Step 3: Write minimal implementation**

- Add the VC request schema.
- Add a dedicated endpoint that:
  - decodes source audio
  - resolves target voice reference bytes from either raw payload or stored custom voice id
  - calls into the Chatterbox adapter VC path
  - returns a non-streaming audio response
- Extract response/persistence helpers from `audio_tts.py` where reuse is worthwhile.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS_NEW/integration/test_chatterbox_voice_conversion_endpoint.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/audio/audio_voice_conversion.py tldw_Server_API/app/api/v1/endpoints/audio/audio.py tldw_Server_API/app/api/v1/endpoints/audio/__init__.py tldw_Server_API/app/api/v1/schemas/audio_schemas.py tldw_Server_API/app/api/v1/endpoints/audio/audio_response_helpers.py tldw_Server_API/tests/TTS_NEW/integration/test_chatterbox_voice_conversion_endpoint.py
git commit -m "feat: add chatterbox voice conversion endpoint"
```

### Task 7: Add VC runtime support to the Chatterbox adapter

**Files:**
- Modify: `tldw_Server_API/app/core/TTS/adapters/chatterbox_adapter.py`
- Test: `tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py`

**Step 1: Write the failing test**

Add a unit test that checks VC uses separate source audio and target voice inputs.

```python
@pytest.mark.asyncio
async def test_chatterbox_voice_conversion_uses_source_and_target_paths(monkeypatch, tmp_path):
    adapter = ChatterboxAdapter({})
    source = tmp_path / "source.wav"
    target = tmp_path / "target.wav"
    source.write_bytes(b"RIFF" + b"\x00" * 100)
    target.write_bytes(b"RIFF" + b"\x00" * 100)
    call = {}

    class FakeVC:
        sr = 24000
        def generate(self, audio, target_voice_path=None):
            call["audio"] = audio
            call["target_voice_path"] = target_voice_path
            return FAKE_TENSOR

    adapter.model_vc = FakeVC()
    await adapter._convert_voice_with_chatterbox(str(source), str(target), AudioFormat.WAV)
    assert call["audio"] == str(source)
    assert call["target_voice_path"] == str(target)
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py -k voice_conversion -v
```

Expected: FAIL because VC helpers do not exist yet.

**Step 3: Write minimal implementation**

- Add VC lazy loader and conversion helper.
- Add temp-file handling for source/target audio.
- Reuse encoding helpers to return requested output format.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py -k voice_conversion -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/adapters/chatterbox_adapter.py tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py
git commit -m "feat: add chatterbox vc runtime support"
```

## Stage 5: Update Docs, UI Discovery, And Verification
**Goal**: Finish all user-facing surfaces and verify the touched scope.
**Success Criteria**: Docs/UI show the new TTS model family, VC is documented separately, tests pass, and Bandit is clean on touched paths.
**Tests**: Targeted pytest runs plus Bandit.
**Status**: Not Started

### Task 8: Update frontend discovery and voice requirements

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/audio-models.ts`
- Modify: `apps/packages/ui/src/services/tldw/voice-cloning.ts`
- Modify: `Docs/STT-TTS/CHATTERBOX_SETUP.md`
- Modify: `tldw_Server_API/app/core/TTS/TTS-README.md`

**Step 1: Write the failing test**

Add or update a small test/snapshot around Chatterbox model fallback ids if a test exists nearby; if no test exists, add one in the most local UI service test area.

```ts
it("includes canonical chatterbox tts model ids", async () => {
  const models = await fetchTldwTtsModels()
  expect(models.some((m) => m.id === "chatterbox-turbo")).toBe(true)
  expect(models.some((m) => m.id === "chatterbox-multilingual")).toBe(true)
})
```

**Step 2: Run test to verify it fails**

Run the nearest existing frontend test command for the touched scope.

```bash
bunx vitest run apps/packages/ui/src/services/tldw
```

Expected: FAIL or missing coverage until the fallback list/docs are updated.

**Step 3: Write minimal implementation**

- Add canonical Chatterbox TTS ids to the frontend fallback list.
- Update voice requirement copy to stop presenting one hardcoded Chatterbox contract for every family.
- Document VC as a separate endpoint/feature.

**Step 4: Run test to verify it passes**

```bash
bunx vitest run apps/packages/ui/src/services/tldw
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/audio-models.ts apps/packages/ui/src/services/tldw/voice-cloning.ts Docs/STT-TTS/CHATTERBOX_SETUP.md tldw_Server_API/app/core/TTS/TTS-README.md
git commit -m "docs: expose updated chatterbox family and vc support"
```

### Task 9: Verify the touched scope

**Files:**
- Test: `tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py`
- Test: `tldw_Server_API/tests/TTS/test_tts_validation.py`
- Test: `tldw_Server_API/tests/TTS_NEW/integration/test_chatterbox_voice_conversion_endpoint.py`
- Test: nearest touched frontend tests

**Step 1: Run targeted backend tests**

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/TTS/adapters/test_chatterbox_adapter_mock.py \
  tldw_Server_API/tests/TTS/test_tts_validation.py \
  tldw_Server_API/tests/TTS_NEW/integration/test_chatterbox_voice_conversion_endpoint.py -v
```

Expected: PASS.

**Step 2: Run touched frontend tests**

```bash
bunx vitest run apps/packages/ui/src/services/tldw
```

Expected: PASS.

**Step 3: Run Bandit on touched backend paths**

```bash
source .venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/core/TTS/adapters/chatterbox_adapter.py \
  tldw_Server_API/app/core/TTS/tts_validation.py \
  tldw_Server_API/app/api/v1/endpoints/audio \
  -f json -o /tmp/bandit_chatterbox_upstream_parity.json
```

Expected: no new findings in touched code.

**Step 4: Review diff**

```bash
git diff --stat
git diff -- tldw_Server_API/app/core/TTS/adapters/chatterbox_adapter.py
git diff -- tldw_Server_API/app/api/v1/endpoints/audio
```

Expected: only intended Chatterbox parity changes in touched files.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/adapters/chatterbox_adapter.py tldw_Server_API/app/core/TTS/tts_validation.py tldw_Server_API/app/api/v1/endpoints/audio tldw_Server_API/app/api/v1/schemas/audio_schemas.py apps/packages/ui/src/services/tldw/audio-models.ts apps/packages/ui/src/services/tldw/voice-cloning.ts Docs/STT-TTS/CHATTERBOX_SETUP.md tldw_Server_API/app/core/TTS/TTS-README.md pyproject.toml tldw_Server_API/Config_Files/tts_providers_config.yaml
git commit -m "feat: add full chatterbox upstream parity"
```
