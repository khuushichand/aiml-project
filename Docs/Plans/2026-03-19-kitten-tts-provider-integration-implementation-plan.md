# KittenTTS Provider Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add first-class `kitten_tts` local-provider support, including PR #25 phonemizer/eSpeak fixes, TTS routing, setup provisioning, and voice catalog support without breaking existing TTS providers.

**Architecture:** Add a new `kitten_tts` adapter to the current TTS registry and route model aliases/HF repo IDs to it. Back the adapter with a small in-repo compatibility runtime that downloads the upstream Kitten model assets, performs PR #25 eSpeak initialization locally, and returns NumPy audio arrays for the existing audio writer/conversion pipeline. Keep voices static so catalog reads do not trigger downloads. Add setup support only in the advanced engine picker and installer path, not curated bundle defaults.

**Tech Stack:** Python 3.11+, FastAPI, ONNX Runtime, Hugging Face Hub, `phonemizer-fork`, `espeakng_loader`, NumPy, Loguru, pytest, setup installer helpers, Bandit.

---

## Stage 1: Provider Routing and Config Plumbing
**Goal**: Make `kitten_tts` a recognized provider everywhere the backend resolves local TTS engines.
**Success Criteria**: Provider aliases and HF repo IDs resolve to `kitten_tts`; YAML config accepts the provider; local-device and auto-download fanout includes `kitten_tts`.
**Tests**: `tldw_Server_API/tests/TTS/test_tts_adapters.py`, `tldw_Server_API/tests/TTS/test_tts_service_v2.py`, `tldw_Server_API/tests/Config/test_effective_config_api.py`
**Status**: Not Started

### Task 1: Add failing routing/config tests

**Files:**
- Modify: `tldw_Server_API/tests/TTS/test_tts_adapters.py`
- Modify: `tldw_Server_API/tests/TTS/test_tts_service_v2.py`
- Modify: `tldw_Server_API/tests/Config/test_effective_config_api.py`

**Step 1: Write the failing tests**

```python
def test_get_provider_for_model_maps_kitten_repo_ids():
    factory = TTSAdapterFactory(config={"providers": {"kitten_tts": {"enabled": True}}})
    assert factory.get_provider_for_model("kitten_tts") == TTSProvider.KITTEN_TTS
    assert factory.get_provider_for_model("KittenML/kitten-tts-nano-0.8") == TTSProvider.KITTEN_TTS


def test_tts_config_local_device_fanout_includes_kitten_tts(tmp_path):
    cfg = TTSConfigManager(
        yaml_path=tmp_path / "tts.yaml",
        config_txt_path=tmp_path / "config.txt",
    )
    # adapt fixture setup to this repo's helpers; assert providers.kitten_tts.device is set
```

**Step 2: Run tests to verify they fail**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/test_tts_adapters.py -k kitten -v
python -m pytest tldw_Server_API/tests/TTS/test_tts_service_v2.py -k kitten -v
```

Expected: FAIL because `kitten_tts` is not registered or routed yet.

**Step 3: Write minimal implementation**

Modify:
- `tldw_Server_API/app/core/TTS/adapter_registry.py`
- `tldw_Server_API/app/core/TTS/tts_config.py`
- `tldw_Server_API/Config_Files/tts_providers_config.yaml`
- `tldw_Server_API/app/api/v1/schemas/audio_schemas.py`
- `tldw_Server_API/app/core/TTS/tts_validation.py`

Implementation notes:
- Add `TTSProvider.KITTEN_TTS`.
- Add adapter path registration for `kitten_tts`.
- Add provider aliases and `MODEL_PROVIDER_MAP` entries for the HF repo IDs and short aliases.
- Add `kitten_tts` to local-provider config fanout for `device` and `auto_download`.
- Add provider defaults in `tts_providers_config.yaml`.
- Extend schema/validation descriptions so `kitten_tts` is a documented valid model/provider choice.

**Step 4: Run tests to verify they pass**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/test_tts_adapters.py -k kitten -v
python -m pytest tldw_Server_API/tests/TTS/test_tts_service_v2.py -k kitten -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/adapter_registry.py tldw_Server_API/app/core/TTS/tts_config.py tldw_Server_API/Config_Files/tts_providers_config.yaml tldw_Server_API/app/api/v1/schemas/audio_schemas.py tldw_Server_API/app/core/TTS/tts_validation.py tldw_Server_API/tests/TTS/test_tts_adapters.py tldw_Server_API/tests/TTS/test_tts_service_v2.py tldw_Server_API/tests/Config/test_effective_config_api.py
git commit -m "feat(tts): register kitten_tts provider routing and config"
```

## Stage 2: Compatibility Runtime with PR #25 Behavior
**Goal**: Build a small in-repo Kitten runtime that uses the upstream asset layout but performs PR #25 eSpeak initialization itself.
**Success Criteria**: The runtime downloads or locates Kitten assets, initializes eSpeak paths through `espeakng_loader`, and exposes a minimal generation API without importing `misaki`.
**Tests**: `tldw_Server_API/tests/TTS/adapters/test_kittentts_compat.py`
**Status**: Not Started

### Task 2: Add failing compatibility-runtime tests

**Files:**
- Create: `tldw_Server_API/tests/TTS/adapters/test_kittentts_compat.py`

**Step 1: Write the failing tests**

```python
def test_init_espeak_paths_uses_espeakng_loader(monkeypatch):
    calls = []

    class FakeWrapper:
        @staticmethod
        def set_library(path):
            calls.append(("lib", path))

        @staticmethod
        def set_data_path(path):
            calls.append(("data", path))

    monkeypatch.setattr(mod, "EspeakWrapper", FakeWrapper)
    monkeypatch.setattr(mod.espeakng_loader, "get_library_path", lambda: "/tmp/libespeak.so")
    monkeypatch.setattr(mod.espeakng_loader, "get_data_path", lambda: "/tmp/espeak-data")

    mod.initialize_espeak_paths()

    assert calls == [("lib", "/tmp/libespeak.so"), ("data", "/tmp/espeak-data")]


def test_download_model_uses_config_json(monkeypatch, tmp_path):
    # verify config.json drives model_file + voices selection
    ...
```

**Step 2: Run tests to verify they fail**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/adapters/test_kittentts_compat.py -v
```

Expected: FAIL because the compatibility module does not exist.

**Step 3: Write minimal implementation**

**Files:**
- Create: `tldw_Server_API/app/core/TTS/vendors/kittentts_compat.py`

Implementation notes:
- Add `initialize_espeak_paths()`.
- Add a tiny model loader that:
  - downloads `config.json`,
  - downloads the configured ONNX and voice embedding assets,
  - constructs the ONNX session,
  - builds the phonemizer backend.
- Add voice alias handling for Bella/Jasper/Luna/Bruno/Rosie/Hugo/Kiki/Leo.
- Keep the public surface small and adapter-oriented.

Representative shape:

```python
class KittenRuntime:
    def __init__(self, repo_id: str, cache_dir: str | None, auto_download: bool):
        ...

    def available_voices(self) -> list[str]:
        return ["Bella", "Jasper", "Luna", "Bruno", "Rosie", "Hugo", "Kiki", "Leo"]

    def generate(self, text: str, voice: str, speed: float, clean_text: bool) -> np.ndarray:
        ...
```

**Step 4: Run tests to verify they pass**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/adapters/test_kittentts_compat.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/vendors/kittentts_compat.py tldw_Server_API/tests/TTS/adapters/test_kittentts_compat.py
git commit -m "feat(tts): add KittenTTS compatibility runtime"
```

## Stage 3: Adapter Implementation
**Goal**: Add a real `KittenTTSAdapter` that plugs into the current TTS service and exposes static capabilities/voices.
**Success Criteria**: The adapter initializes cleanly, validates voices, emits TTSResponse payloads for streaming and non-streaming requests, and does not download models for voice-catalog reads.
**Tests**: `tldw_Server_API/tests/TTS/adapters/test_kittentts_adapter_mock.py`
**Status**: Not Started

### Task 3: Add failing adapter tests

**Files:**
- Create: `tldw_Server_API/tests/TTS/adapters/test_kittentts_adapter_mock.py`

**Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_kittentts_capabilities_report_static_voices():
    adapter = KittenTTSAdapter({"model": "KittenML/kitten-tts-nano-0.8"})
    caps = await adapter.get_capabilities()
    assert caps.provider_name == "KittenTTS"
    assert "Bella" in [voice.name for voice in caps.supported_voices]
    assert AudioFormat.WAV in caps.supported_formats


@pytest.mark.asyncio
async def test_kittentts_generate_non_stream(monkeypatch):
    monkeypatch.setattr(mod, "KittenRuntime", FakeRuntimeReturningArray)
    adapter = KittenTTSAdapter({"model": "KittenML/kitten-tts-nano-0.8"})
    request = TTSRequest(text="Hello", voice="Bella", format=AudioFormat.MP3, stream=False)
    response = await adapter.generate(request)
    assert response.audio_data
    assert response.provider == "kitten_tts"
```

**Step 2: Run tests to verify they fail**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/adapters/test_kittentts_adapter_mock.py -v
```

Expected: FAIL because the adapter does not exist.

**Step 3: Write minimal implementation**

**Files:**
- Create: `tldw_Server_API/app/core/TTS/adapters/kitten_tts_adapter.py`

Implementation notes:
- Set `PROVIDER_KEY = "kitten_tts"`.
- Keep a runtime instance behind a lazy init lock.
- Expose static voices via `VoiceInfo`.
- Support `stream=False` and `stream=True` using `StreamingAudioWriter`.
- Accept `clean_text` from provider config or `extra_params`.
- Use PCM/WAV as the base local format and let the existing audio writer handle transcoding.

**Step 4: Run tests to verify they pass**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/adapters/test_kittentts_adapter_mock.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/adapters/kitten_tts_adapter.py tldw_Server_API/tests/TTS/adapters/test_kittentts_adapter_mock.py
git commit -m "feat(tts): add KittenTTS adapter"
```

## Stage 4: Service, Endpoint, and Voice Catalog Integration
**Goal**: Verify the new provider works end-to-end through the service and `/api/v1/audio/voices/catalog`.
**Success Criteria**: Service routing works for both provider aliases and HF model repo IDs; voice catalog returns Kitten voices; endpoint tests pass with mocked adapter output.
**Tests**: `tldw_Server_API/tests/TTS/test_tts_service_v2.py`, `tldw_Server_API/tests/TTS/test_supertonic2_endpoint_integration.py` or new targeted endpoint tests
**Status**: Not Started

### Task 4: Add failing service/endpoint tests

**Files:**
- Modify: `tldw_Server_API/tests/TTS/test_tts_service_v2.py`
- Create or Modify: `tldw_Server_API/tests/TTS/test_kittentts_endpoint_integration.py`

**Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_service_routes_kitten_repo_id_to_adapter(service):
    adapter = MockAdapter({"name": "kitten_tts"})
    await adapter.initialize()
    service.factory.get_adapter_by_model = AsyncMock(return_value=adapter)
    request = OpenAISpeechRequest(
        input="Hello",
        model="KittenML/kitten-tts-nano-0.8",
        voice="Bella",
        response_format="mp3",
    )
    request.stream = False
    payload = b"".join([chunk async for chunk in service.generate_speech(request)])
    assert payload == b"mock audio data"


def test_voice_catalog_returns_kitten_provider(client, monkeypatch):
    ...
```

**Step 2: Run tests to verify they fail**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/test_tts_service_v2.py -k kitten -v
python -m pytest tldw_Server_API/tests/TTS/test_kittentts_endpoint_integration.py -v
```

Expected: FAIL because the provider is not fully wired into catalog/endpoint behavior.

**Step 3: Write minimal implementation**

Implementation notes:
- Ensure `get_capabilities()` and `list_voices()` include `kitten_tts` once the adapter is enabled.
- Add any endpoint-level dependency overrides needed for stable tests.
- Keep voices static so `voices/catalog` does not require model downloads.

**Step 4: Run tests to verify they pass**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/test_tts_service_v2.py -k kitten -v
python -m pytest tldw_Server_API/tests/TTS/test_kittentts_endpoint_integration.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/TTS/test_tts_service_v2.py tldw_Server_API/tests/TTS/test_kittentts_endpoint_integration.py
git commit -m "test(tts): cover KittenTTS service routing and voice catalog"
```

## Stage 5: Setup Provisioning and WebUI Surface
**Goal**: Add KittenTTS to the advanced setup engine picker and dependency provisioning path.
**Success Criteria**: Setup schema accepts `kitten_tts`; installer dependencies and install routine support it; setup JS advertises it in the engine picker.
**Tests**: `tldw_Server_API/tests/Setup/test_install_manager_dependencies.py`, `tldw_Server_API/tests/integration/test_setup_installation.py`
**Status**: Not Started

### Task 5: Add failing setup tests

**Files:**
- Modify: `tldw_Server_API/tests/Setup/test_install_manager_dependencies.py`
- Modify: `tldw_Server_API/tests/integration/test_setup_installation.py`

**Step 1: Write the failing tests**

```python
def test_install_plan_accepts_kitten_tts():
    plan = InstallPlan(tts=[TTSInstall(engine="kitten_tts")])
    assert plan.tts[0].engine == "kitten_tts"


def test_setup_js_mentions_kitten_tts(client):
    response = client.get("/static/setup/js/setup.js")
    assert response.status_code == 200
    assert "kitten_tts" in response.text
    assert "KittenTTS" in response.text
```

**Step 2: Run tests to verify they fail**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Setup/test_install_manager_dependencies.py -k kitten -v
python -m pytest tldw_Server_API/tests/integration/test_setup_installation.py -k kitten -v
```

Expected: FAIL because setup/install does not know the engine.

**Step 3: Write minimal implementation**

**Files:**
- Modify: `tldw_Server_API/app/core/Setup/install_schema.py`
- Modify: `tldw_Server_API/app/core/Setup/install_manager.py`
- Modify: `tldw_Server_API/app/static/setup/js/setup.js`

Implementation notes:
- Add `kitten_tts` to `TTS_ENGINES`.
- Add direct dependency requirements for the compatibility runtime stack.
- Add `_install_kitten_tts()` that ensures downloads are allowed and prefetches the configured HF assets.
- Add a setup engine card in the advanced TTS picker.
- Do not change curated audio bundle defaults in this task.

**Step 4: Run tests to verify they pass**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Setup/test_install_manager_dependencies.py -k kitten -v
python -m pytest tldw_Server_API/tests/integration/test_setup_installation.py -k kitten -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Setup/install_schema.py tldw_Server_API/app/core/Setup/install_manager.py tldw_Server_API/app/static/setup/js/setup.js tldw_Server_API/tests/Setup/test_install_manager_dependencies.py tldw_Server_API/tests/integration/test_setup_installation.py
git commit -m "feat(setup): add KittenTTS provisioning support"
```

## Stage 6: Documentation and Verification
**Goal**: Update touched documentation and verify the entire change set with tests and Bandit.
**Success Criteria**: Relevant docs mention KittenTTS configuration/setup; targeted tests pass; Bandit is clean on touched backend paths.
**Tests**: targeted pytest suites below, Bandit scan on touched Python paths
**Status**: Not Started

### Task 6: Final verification

**Files:**
- Modify: `tldw_Server_API/Config_Files/README.md`
- Modify: `tldw_Server_API/app/core/TTS/TTS-README.md`
- Modify: `tldw_Server_API/app/core/TTS/TTS-DEPLOYMENT.md`

**Step 1: Update docs**

Add concise sections covering:
- enabling `providers.kitten_tts`,
- model repo selection,
- eSpeak prerequisite,
- setup provisioning behavior,
- supported voices/formats.

**Step 2: Run targeted tests**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/TTS/test_tts_adapters.py -k kitten -v
python -m pytest tldw_Server_API/tests/TTS/test_tts_service_v2.py -k kitten -v
python -m pytest tldw_Server_API/tests/TTS/adapters/test_kittentts_compat.py -v
python -m pytest tldw_Server_API/tests/TTS/adapters/test_kittentts_adapter_mock.py -v
python -m pytest tldw_Server_API/tests/TTS/test_kittentts_endpoint_integration.py -v
python -m pytest tldw_Server_API/tests/Setup/test_install_manager_dependencies.py -k kitten -v
python -m pytest tldw_Server_API/tests/integration/test_setup_installation.py -k kitten -v
```

Expected: PASS.

**Step 3: Run Bandit**

Run:
```bash
source .venv/bin/activate
python -m bandit -r tldw_Server_API/app/core/TTS/adapters/kitten_tts_adapter.py tldw_Server_API/app/core/TTS/vendors/kittentts_compat.py tldw_Server_API/app/core/Setup/install_manager.py -f json -o /tmp/bandit_kitten_tts.json
```

Expected: No new findings in touched code.

**Step 4: Commit**

```bash
git add tldw_Server_API/Config_Files/README.md tldw_Server_API/app/core/TTS/TTS-README.md tldw_Server_API/app/core/TTS/TTS-DEPLOYMENT.md
git commit -m "docs(tts): document KittenTTS provider support"
```
