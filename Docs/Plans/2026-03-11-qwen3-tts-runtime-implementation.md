# Qwen3-TTS Runtime Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add runtime-aware `qwen3_tts` support so `tldw_server` can run Qwen3-TTS in-process on Apple Silicon with an MLX-backed preset-speaker path, continue supporting upstream in-process execution, and optionally target a hosted Qwen sidecar without changing the public provider key.

**Architecture:** Keep `qwen3_tts` as the only public provider and split execution behind `Qwen3TTSAdapter` into three runtimes: `upstream`, `mlx`, and `remote`. The adapter remains responsible for request normalization, model/mode selection, voice metadata reuse, and response shaping; each runtime owns dependency loading, backend-specific generation, and truthful capability reporting.

**Tech Stack:** Python, FastAPI, existing TTS v2 adapter stack, `qwen_tts`, MLX/`mlx-audio`, JSON-serializable capability metadata, pytest, Bandit.

---

### Task 1: Add Runtime Config And Deterministic Runtime Selection

**Files:**
- Modify: `tldw_Server_API/app/core/TTS/tts_config.py`
- Modify: `tldw_Server_API/Config_Files/tts_providers_config.yaml`
- Modify: `tldw_Server_API/app/core/TTS/adapters/qwen3_tts_adapter.py`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_runtime_selection.py`
- Read first: `Docs/Plans/2026-03-11-qwen3-tts-macos-design.md`

**Step 1: Write the failing test**

```python
import platform

from tldw_Server_API.app.core.TTS.adapters.qwen3_tts_adapter import Qwen3TTSAdapter


def test_runtime_auto_prefers_mlx_on_macos_arm64(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    adapter = Qwen3TTSAdapter({"runtime": "auto"})
    assert adapter._resolve_runtime_name() == "mlx"


def test_runtime_explicit_remote_wins_over_platform(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    adapter = Qwen3TTSAdapter({"runtime": "remote", "base_url": "http://127.0.0.1:8000/v1/audio/speech"})
    assert adapter._resolve_runtime_name() == "remote"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_runtime_selection.py -v`

Expected: FAIL because `runtime` is not modeled and `_resolve_runtime_name()` does not exist.

**Step 3: Write minimal implementation**

```python
# tts_config.py
class ProviderConfig(BaseModel):
    ...
    runtime: Optional[str] = None


# qwen3_tts_adapter.py
def _resolve_runtime_name(self) -> str:
    configured = str(self.config.get("runtime") or "auto").strip().lower()
    if configured in {"upstream", "mlx", "remote"}:
        return configured
    if platform.system() == "Darwin" and platform.machine().lower() == "arm64":
        return "mlx"
    return "upstream"
```

Update `tts_providers_config.yaml` with:

```yaml
  qwen3_tts:
    runtime: "auto"
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_runtime_selection.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/tts_config.py \
        tldw_Server_API/Config_Files/tts_providers_config.yaml \
        tldw_Server_API/app/core/TTS/adapters/qwen3_tts_adapter.py \
        tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_runtime_selection.py
git commit -m "feat: add qwen3 runtime selection"
```

### Task 2: Extract A Runtime Interface And Move Current Upstream Logic Behind It

**Files:**
- Create: `tldw_Server_API/app/core/TTS/adapters/qwen3_runtime_base.py`
- Create: `tldw_Server_API/app/core/TTS/adapters/qwen3_runtime_upstream.py`
- Modify: `tldw_Server_API/app/core/TTS/adapters/qwen3_tts_adapter.py`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_upstream_runtime.py`

**Step 1: Write the failing test**

```python
import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.qwen3_tts_adapter import Qwen3TTSAdapter


@pytest.mark.asyncio
async def test_upstream_runtime_handles_existing_custom_voice_flow(fake_qwen_module):
    adapter = Qwen3TTSAdapter({"runtime": "upstream", "device": "cpu"})
    await adapter.ensure_initialized()
    request = TTSRequest(text="hello", voice="Vivian", format=AudioFormat.PCM, stream=False)
    request.model = "auto"
    response = await adapter.generate(request)
    assert response.audio_content
    assert response.metadata["runtime"] == "upstream"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_upstream_runtime.py -v`

Expected: FAIL because no runtime abstraction exists and no runtime metadata is returned.

**Step 3: Write minimal implementation**

Create a runtime protocol:

```python
# qwen3_runtime_base.py
class Qwen3Runtime(Protocol):
    runtime_name: str

    async def initialize(self) -> bool: ...
    async def get_capabilities(self) -> dict[str, Any]: ...
    async def generate(self, request: TTSRequest, resolved_model: str, mode: str) -> TTSResponse: ...
```

Extract the current `qwen_tts`-based generation path into `qwen3_runtime_upstream.py` and have the adapter delegate:

```python
self._runtime = self._build_runtime()
response = await self._runtime.generate(request, resolved_model, mode)
response.metadata.setdefault("runtime", self._runtime.runtime_name)
return response
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_upstream_runtime.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/adapters/qwen3_runtime_base.py \
        tldw_Server_API/app/core/TTS/adapters/qwen3_runtime_upstream.py \
        tldw_Server_API/app/core/TTS/adapters/qwen3_tts_adapter.py \
        tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_upstream_runtime.py
git commit -m "refactor: extract qwen3 upstream runtime"
```

### Task 3: Add The MLX Runtime And Gate Unsupported Modes

**Files:**
- Create: `tldw_Server_API/app/core/TTS/adapters/qwen3_runtime_mlx.py`
- Modify: `tldw_Server_API/app/core/TTS/adapters/qwen3_tts_adapter.py`
- Modify: `tldw_Server_API/app/core/TTS/tts_validation.py`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_mlx_runtime.py`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_qwen3_mlx.py`

**Step 1: Write the failing tests**

```python
import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.tts_exceptions import TTSValidationError
from tldw_Server_API.app.core.TTS.tts_validation import validate_tts_request


@pytest.mark.asyncio
async def test_mlx_runtime_reports_preset_custom_voice_only(fake_mlx_runtime):
    adapter = Qwen3TTSAdapter({"runtime": "mlx"})
    await adapter.ensure_initialized()
    caps = await adapter.get_capabilities()
    assert caps.metadata["runtime"] == "mlx"
    assert caps.metadata["supported_modes"] == ["custom_voice_preset"]
    assert caps.metadata["supports_uploaded_custom_voices"] is False


def test_mlx_runtime_rejects_uploaded_custom_voice_request():
    request = TTSRequest(text="hello", voice="custom:voice-1", format=AudioFormat.MP3)
    request.model = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    with pytest.raises(TTSValidationError):
        validate_tts_request(request, provider="qwen3_tts", config={"providers": {"qwen3_tts": {"runtime": "mlx"}}})
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_mlx_runtime.py tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_qwen3_mlx.py -v`

Expected: FAIL because MLX runtime and runtime-aware validation do not exist.

**Step 3: Write minimal implementation**

Create `qwen3_runtime_mlx.py` with strict mode gating:

```python
class MlxQwenRuntime:
    runtime_name = "mlx"

    async def get_capabilities(self) -> dict[str, Any]:
        return {
            "runtime": "mlx",
            "supported_modes": ["custom_voice_preset"],
            "supports_uploaded_custom_voices": False,
        }

    def validate_mode(self, request: TTSRequest, mode: str) -> None:
        if request.voice and str(request.voice).startswith("custom:"):
            raise TTSValidationError("Uploaded custom voices are not supported by the MLX runtime in v1")
        if mode in {"voice_clone", "voice_design"}:
            raise TTSValidationError(f"Mode '{mode}' is not supported by the MLX runtime")
```

Update adapter and validation code to pass the configured runtime into Qwen-specific validation.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_mlx_runtime.py tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_qwen3_mlx.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/adapters/qwen3_runtime_mlx.py \
        tldw_Server_API/app/core/TTS/adapters/qwen3_tts_adapter.py \
        tldw_Server_API/app/core/TTS/tts_validation.py \
        tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_mlx_runtime.py \
        tldw_Server_API/tests/TTS_NEW/unit/test_tts_validation_qwen3_mlx.py
git commit -m "feat: add qwen3 mlx runtime gating"
```

### Task 4: Add The Remote Runtime With An Explicit Qwen Extension Contract

**Files:**
- Create: `tldw_Server_API/app/core/TTS/adapters/qwen3_runtime_remote.py`
- Modify: `tldw_Server_API/app/core/TTS/adapters/qwen3_tts_adapter.py`
- Modify: `tldw_Server_API/app/core/TTS/tts_config.py`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_remote_runtime.py`

**Step 1: Write the failing test**

```python
import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.qwen3_runtime_remote import RemoteQwenRuntime


@pytest.mark.asyncio
async def test_remote_runtime_maps_qwen_clone_fields_into_extended_payload(httpx_mock):
    runtime = RemoteQwenRuntime({"base_url": "http://127.0.0.1:8001/v1/audio/speech", "api_key": "test-key"})
    request = TTSRequest(
        text="hello",
        format=AudioFormat.PCM,
        voice_reference=b"VOICE_BYTES",
        extra_params={"reference_text": "ref", "voice_clone_prompt": "UFJPTVBU"},
    )
    payload = runtime._build_payload(request, resolved_model="Qwen/Qwen3-TTS-12Hz-0.6B-Base", mode="voice_clone")
    assert payload["extra_body"]["ref_text"] == "ref"
    assert payload["extra_body"]["voice_clone_prompt"] == "UFJPTVBU"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_remote_runtime.py -v`

Expected: FAIL because remote runtime and Qwen extension payload mapping do not exist.

**Step 3: Write minimal implementation**

```python
class RemoteQwenRuntime:
    runtime_name = "remote"

    def _build_payload(self, request: TTSRequest, resolved_model: str, mode: str) -> dict[str, Any]:
        payload = {
            "model": resolved_model,
            "input": request.text,
            "voice": request.voice or "",
            "response_format": request.format.value,
            "speed": request.speed,
            "extra_body": {},
        }
        if mode == "voice_clone":
            payload["extra_body"]["ref_text"] = request.extra_params["reference_text"]
            payload["extra_body"]["voice_clone_prompt"] = request.extra_params.get("voice_clone_prompt")
        return payload
```

Use `base_url` and `api_key` from provider config when `runtime=remote`; do not add `remote_base_url` or `remote_api_key`.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_remote_runtime.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/adapters/qwen3_runtime_remote.py \
        tldw_Server_API/app/core/TTS/adapters/qwen3_tts_adapter.py \
        tldw_Server_API/app/core/TTS/tts_config.py \
        tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_remote_runtime.py
git commit -m "feat: add qwen3 remote runtime"
```

### Task 5: Make Capabilities, Health, And Breakers Runtime-Aware

**Files:**
- Modify: `tldw_Server_API/app/core/TTS/adapters/base.py`
- Modify: `tldw_Server_API/app/core/TTS/tts_service_v2.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/audio_health.py`
- Modify: `tldw_Server_API/app/core/TTS/circuit_breaker.py`
- Test: `tldw_Server_API/tests/TTS_NEW/unit/test_qwen3_capabilities_runtime_metadata.py`
- Test: `tldw_Server_API/tests/TTS_NEW/integration/test_qwen3_runtime_health_envelope.py`

**Step 1: Write the failing tests**

```python
def test_qwen3_capability_payload_includes_runtime_metadata():
    caps = TTSCapabilities(
        provider_name="Qwen3-TTS",
        supported_languages={"en"},
        supported_voices=[],
        supported_formats={AudioFormat.PCM},
        max_text_length=5000,
        supports_streaming=True,
        metadata={"runtime": "mlx", "supported_modes": ["custom_voice_preset"]},
    )
    serialized = TTSServiceV2()._serialize_capabilities(caps)
    assert serialized["metadata"]["runtime"] == "mlx"


def test_runtime_breaker_key_is_namespaced():
    key = build_qwen_runtime_breaker_key("qwen3_tts", "mlx")
    assert key == "qwen3_tts:mlx"
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS_NEW/unit/test_qwen3_capabilities_runtime_metadata.py tldw_Server_API/tests/TTS_NEW/integration/test_qwen3_runtime_health_envelope.py -v`

Expected: FAIL because `TTSCapabilities` has no metadata field and runtime namespacing does not exist.

**Step 3: Write minimal implementation**

```python
# base.py
@dataclass
class TTSCapabilities:
    ...
    metadata: dict[str, Any] = field(default_factory=dict)


# tts_service_v2.py
data["metadata"] = dict(data.get("metadata") or {})


# circuit_breaker.py
def build_qwen_runtime_breaker_key(provider_name: str, runtime_name: str) -> str:
    return f"{provider_name}:{runtime_name}"
```

Update the Qwen adapter/runtime path so health details and breaker/metric labels include runtime metadata while the public provider key remains `qwen3_tts`.

**Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS_NEW/unit/test_qwen3_capabilities_runtime_metadata.py tldw_Server_API/tests/TTS_NEW/integration/test_qwen3_runtime_health_envelope.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/adapters/base.py \
        tldw_Server_API/app/core/TTS/tts_service_v2.py \
        tldw_Server_API/app/api/v1/endpoints/audio/audio_health.py \
        tldw_Server_API/app/core/TTS/circuit_breaker.py \
        tldw_Server_API/tests/TTS_NEW/unit/test_qwen3_capabilities_runtime_metadata.py \
        tldw_Server_API/tests/TTS_NEW/integration/test_qwen3_runtime_health_envelope.py
git commit -m "feat: add qwen3 runtime metadata"
```

### Task 6: Update Documentation And Manual Apple Silicon Verification

**Files:**
- Modify: `tldw_Server_API/app/core/TTS/TTS-README.md`
- Modify: `tldw_Server_API/app/core/TTS/TTS-DEPLOYMENT.md`
- Modify: `Docs/Plans/2026-03-11-qwen3-tts-macos-design.md`

**Step 1: Write the documentation changes first**

Add explicit docs covering:

- runtime selector values
- MLX v1 scope: preset-speaker `CustomVoice` only
- remote Qwen extension contract
- sample config blocks for `runtime=mlx` and `runtime=remote`
- manual Apple Silicon smoke checklist

Use concrete snippets like:

```yaml
providers:
  qwen3_tts:
    enabled: true
    runtime: "mlx"
    model: "auto"
```

**Step 2: Run a docs-focused smoke check**

Run: `rg -n "runtime:|preset-speaker|remote Qwen extension|Apple Silicon smoke" tldw_Server_API/app/core/TTS/TTS-README.md tldw_Server_API/app/core/TTS/TTS-DEPLOYMENT.md`

Expected: matching lines for each new topic

**Step 3: Add or update example commands**

Document commands like:

```bash
source .venv/bin/activate
python -m uvicorn tldw_Server_API.app.main:app --reload
curl -X POST http://127.0.0.1:8000/api/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3_tts","input":"hello","voice":"Vivian","response_format":"wav","stream":false}'
```

**Step 4: Re-run the targeted Qwen test subset**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_runtime_selection.py tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_upstream_runtime.py tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_mlx_runtime.py tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_remote_runtime.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/TTS/TTS-README.md \
        tldw_Server_API/app/core/TTS/TTS-DEPLOYMENT.md \
        Docs/Plans/2026-03-11-qwen3-tts-macos-design.md
git commit -m "docs: document qwen3 runtimes"
```

### Task 7: Final Verification And Security Check

**Files:**
- Modify: none unless verification exposes a defect
- Test: touched Qwen runtime files and tests from Tasks 1-6

**Step 1: Run the focused pytest suite**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_runtime_selection.py \
  tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_upstream_runtime.py \
  tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_mlx_runtime.py \
  tldw_Server_API/tests/TTS_NEW/unit/adapters/test_qwen3_remote_runtime.py \
  tldw_Server_API/tests/TTS_NEW/unit/test_qwen3_capabilities_runtime_metadata.py \
  tldw_Server_API/tests/TTS_NEW/integration/test_qwen3_runtime_health_envelope.py -v
```

Expected: PASS

**Step 2: Run Bandit on the touched scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/TTS/adapters/qwen3_tts_adapter.py \
  tldw_Server_API/app/core/TTS/adapters/qwen3_runtime_base.py \
  tldw_Server_API/app/core/TTS/adapters/qwen3_runtime_upstream.py \
  tldw_Server_API/app/core/TTS/adapters/qwen3_runtime_mlx.py \
  tldw_Server_API/app/core/TTS/adapters/qwen3_runtime_remote.py \
  tldw_Server_API/app/core/TTS/tts_config.py \
  tldw_Server_API/app/core/TTS/tts_validation.py \
  tldw_Server_API/app/core/TTS/tts_service_v2.py \
  tldw_Server_API/app/api/v1/endpoints/audio/audio_health.py \
  -f json -o /tmp/bandit_qwen3_runtimes.json
```

Expected: JSON report generated with no new high-severity findings in touched code

**Step 3: Review git diff for drift**

Run: `git diff --stat`

Expected: only Qwen runtime, config, test, and documentation files changed

**Step 4: Write a short release note entry if needed**

If the repo is currently tracking release notes for this window, add a concise note covering:

- new `qwen3_tts` runtime selector
- MLX Apple Silicon preset-speaker support
- hosted sidecar support

**Step 5: Commit**

```bash
git add .
git commit -m "chore: verify qwen3 runtime support"
```

