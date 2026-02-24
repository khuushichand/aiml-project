# Alibaba Model Studio Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Alibaba Model Studio support for `qwen` chat/model routing and a new `modelstudio` image backend (sync + async) without breaking existing provider behavior.

**Architecture:** Extend existing `qwen` adapter configuration for region-aware base URL presets and add one new image backend adapter (`modelstudio`) that plugs into the current image adapter registry and file-artifact export path. Keep configuration additive and preserve existing endpoint contracts. Use targeted tests to drive each change, then verify with pytest + Bandit.

**Tech Stack:** FastAPI, Python 3.11+, httpx/shared HTTP client helpers, pytest, Loguru, config.txt parser, file-artifact image adapters.

---

### Task 1: Add Model Studio Image Config Fields and Defaults

**Files:**
- Modify: `tldw_Server_API/app/core/Image_Generation/config.py`
- Modify: `tldw_Server_API/Config_Files/config.txt`
- Test: `tldw_Server_API/tests/Image_Generation/test_image_generation_config_defaults.py`

**Step 1: Write the failing test**

```python
def test_image_generation_config_defaults_include_modelstudio():
    cfg = image_config.get_image_generation_config(reload=True)
    assert cfg.modelstudio_image_base_url is not None
    assert cfg.modelstudio_image_default_model is not None
    assert cfg.modelstudio_image_region in {"sg", "cn", "us"}
    assert cfg.modelstudio_image_mode in {"sync", "async", "auto"}
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Image_Generation/test_image_generation_config_defaults.py -v`

Expected: FAIL with missing dataclass/config fields.

**Step 3: Write minimal implementation**

```python
DEFAULT_MODELSTUDIO_IMAGE_BASE_URL = "https://dashscope-intl.aliyuncs.com/api/v1"
DEFAULT_MODELSTUDIO_IMAGE_MODEL = "qwen-image"
DEFAULT_MODELSTUDIO_IMAGE_REGION = "sg"
DEFAULT_MODELSTUDIO_IMAGE_MODE = "auto"

@dataclass(frozen=True)
class ImageGenerationConfig:
    # ...
    modelstudio_image_base_url: str | None
    modelstudio_image_api_key: str | None
    modelstudio_image_default_model: str | None
    modelstudio_image_region: str
    modelstudio_image_mode: str
    modelstudio_image_poll_interval_seconds: int
    modelstudio_image_timeout_seconds: int
    modelstudio_image_allowed_extra_params: list[str]
```

Add parsing in `get_image_generation_config()` and defaults in `[Image-Generation]` section of `config.txt`.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Image_Generation/test_image_generation_config_defaults.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Image_Generation/config.py tldw_Server_API/Config_Files/config.txt tldw_Server_API/tests/Image_Generation/test_image_generation_config_defaults.py
git commit -m "feat(image): add modelstudio image config defaults"
```

### Task 2: Register `modelstudio` Backend and Allowlist Wiring

**Files:**
- Modify: `tldw_Server_API/app/core/Image_Generation/adapter_registry.py`
- Modify: `tldw_Server_API/app/core/File_Artifacts/adapters/image_adapter.py`
- Test: `tldw_Server_API/tests/Files/test_files_image_endpoint.py`

**Step 1: Write the failing test**

```python
def test_image_extra_params_rejected_for_modelstudio_when_not_allowlisted(...):
    payload = {
        "file_type": "image",
        "payload": {
            "backend": "modelstudio",
            "prompt": "test",
            "extra_params": {"watermark": True},
        },
        "export": {"format": "png", "mode": "inline", "async_mode": "sync"},
    }
    response = client.post("/api/v1/files/create", json=payload)
    assert response.status_code == 422
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Files/test_files_image_endpoint.py -k modelstudio -v`

Expected: FAIL because backend/allowlist is not wired.

**Step 3: Write minimal implementation**

```python
# adapter_registry.py
DEFAULT_ADAPTERS = {
    # ...
    "modelstudio": "tldw_Server_API.app.core.Image_Generation.adapters.modelstudio_image_adapter.ModelStudioImageAdapter",
}

# image_adapter.py
if backend == "modelstudio":
    return set(config.modelstudio_image_allowed_extra_params or [])
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Files/test_files_image_endpoint.py -k modelstudio -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Image_Generation/adapter_registry.py tldw_Server_API/app/core/File_Artifacts/adapters/image_adapter.py tldw_Server_API/tests/Files/test_files_image_endpoint.py
git commit -m "feat(image): register modelstudio backend and allowlist enforcement"
```

### Task 3: Implement Model Studio Adapter Sync Path

**Files:**
- Create: `tldw_Server_API/app/core/Image_Generation/adapters/modelstudio_image_adapter.py`
- Test: `tldw_Server_API/tests/Image_Generation/test_modelstudio_image_adapter.py`

**Step 1: Write the failing test**

```python
def test_modelstudio_sync_generation_success(monkeypatch):
    def fake_fetch_json(method, url, headers, json, timeout, **kwargs):
        return {"output": {"choices": [{"message": {"content": [{"image_url": "data:image/png;base64,aGVsbG8="}]}}]}}
    monkeypatch.setattr(modelstudio_module, "fetch_json", fake_fetch_json)
    result = modelstudio_module.ModelStudioImageAdapter().generate(_make_request(mode="sync"))
    assert result.content == b"hello"
    assert result.content_type == "image/png"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Image_Generation/test_modelstudio_image_adapter.py -k sync -v`

Expected: FAIL because adapter file/class does not exist yet.

**Step 3: Write minimal implementation**

```python
class ModelStudioImageAdapter:
    name = "modelstudio"
    supported_formats = {"png", "jpg", "webp"}

    def generate(self, request: ImageGenRequest) -> ImageGenResult:
        mode = self._resolve_mode(request)
        if mode == "sync":
            data = fetch_json(method="POST", url=self._sync_url(), headers=self._headers(), json=self._sync_payload(request), timeout=self._timeout())
            content, content_type = self._extract_image_content(data)
            return ImageGenResult(content=content, content_type=content_type, bytes_len=len(content))
        return self._generate_async(request)
```

Use existing image extraction helpers (`decode_data_url`, `fetch_image_bytes`, `maybe_decode_base64_image`) rather than new abstractions.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Image_Generation/test_modelstudio_image_adapter.py -k sync -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Image_Generation/adapters/modelstudio_image_adapter.py tldw_Server_API/tests/Image_Generation/test_modelstudio_image_adapter.py
git commit -m "feat(image): add modelstudio adapter sync generation path"
```

### Task 4: Add Async Submit + Polling for Model Studio

**Files:**
- Modify: `tldw_Server_API/app/core/Image_Generation/adapters/modelstudio_image_adapter.py`
- Test: `tldw_Server_API/tests/Image_Generation/test_modelstudio_image_adapter.py`

**Step 1: Write the failing test**

```python
def test_modelstudio_async_submit_and_poll_success(monkeypatch):
    calls = []
    def fake_fetch_json(method, url, headers, timeout, **kwargs):
        calls.append((method, url))
        if method == "POST" and url.endswith("/text2image/image-synthesis"):
            return {"output": {"task_id": "task-123"}}
        if method == "GET" and "/tasks/task-123" in url:
            return {"output": {"task_status": "SUCCEEDED", "results": [{"url": "https://cdn.example.com/x.png"}]}}
        raise AssertionError("unexpected call")
    monkeypatch.setattr(modelstudio_module, "fetch_json", fake_fetch_json)
    monkeypatch.setattr(modelstudio_module, "fetch_image_bytes", lambda *_: (b"\x89PNG\r\n\x1a\nabc", "image/png"))
    result = modelstudio_module.ModelStudioImageAdapter().generate(_make_request(mode="async"))
    assert result.content.startswith(b"\x89PNG")
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Image_Generation/test_modelstudio_image_adapter.py -k async -v`

Expected: FAIL due missing async handling.

**Step 3: Write minimal implementation**

```python
submit = fetch_json(method="POST", url=f"{base}/services/aigc/text2image/image-synthesis", ...)
task_id = self._extract_task_id(submit)
while time.monotonic() < deadline:
    polled = fetch_json(method="GET", url=f"{base}/tasks/{task_id}", ...)
    status = self._extract_task_status(polled)
    if status in self._DONE:
        return self._result_from_payload(polled)
    if status in self._FAILED:
        raise ImageGenerationError(...)
    time.sleep(poll_interval)
raise ImageGenerationError("timed out waiting for Model Studio image task")
```

Add tests for timeout and failed terminal states.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Image_Generation/test_modelstudio_image_adapter.py -k async -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Image_Generation/adapters/modelstudio_image_adapter.py tldw_Server_API/tests/Image_Generation/test_modelstudio_image_adapter.py
git commit -m "feat(image): add modelstudio async task submit and polling"
```

### Task 5: Add Model Studio to Image Model Listing/Configured Checks

**Files:**
- Modify: `tldw_Server_API/app/core/Image_Generation/listing.py`
- Test: `tldw_Server_API/tests/Image_Generation/test_image_models_listing.py`

**Step 1: Write the failing test**

```python
@pytest.mark.parametrize(
    ("backend", "key_field", "env_var"),
    [("modelstudio", "modelstudio_image_api_key", "DASHSCOPE_API_KEY")],
)
def test_list_image_models_modelstudio_configured_via_api_key(...):
    ...
    assert entry["id"] == "image/modelstudio"
    assert entry["is_configured"] is True
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Image_Generation/test_image_models_listing.py -k modelstudio -v`

Expected: FAIL because listing lacks modelstudio branch.

**Step 3: Write minimal implementation**

```python
def _is_modelstudio_configured(cfg, enabled: bool) -> bool:
    if not enabled:
        return False
    api_key = (
        getattr(cfg, "modelstudio_image_api_key", None)
        or os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("QWEN_API_KEY")
        or ""
    ).strip()
    return bool(api_key)
```

Wire it into `list_image_models_for_catalog()` branch logic.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Image_Generation/test_image_models_listing.py -k modelstudio -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Image_Generation/listing.py tldw_Server_API/tests/Image_Generation/test_image_models_listing.py
git commit -m "feat(image): expose modelstudio backend in model listing"
```

### Task 6: Add Region Presets to `QwenAdapter` Base URL Resolution

**Files:**
- Modify: `tldw_Server_API/app/core/LLM_Calls/providers/qwen_adapter.py`
- Modify: `tldw_Server_API/app/core/config.py`
- Modify: `tldw_Server_API/Config_Files/config.txt`
- Test: `tldw_Server_API/tests/LLM_Adapters/unit/test_qwen_native_http.py`

**Step 1: Write the failing test**

```python
def test_qwen_base_url_uses_region_preset_when_no_override(monkeypatch):
    adapter = QwenAdapter()
    req = {"app_config": {"qwen_api": {"region": "us"}}, "messages": [{"role": "user", "content": "hi"}], "model": "qwen-plus", "api_key": "k"}
    assert adapter._base_url(req.get("app_config"), req) == "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Adapters/unit/test_qwen_native_http.py -k region -v`

Expected: FAIL because region field is ignored.

**Step 3: Write minimal implementation**

```python
REGION_BASE_URLS = {
    "sg": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "us": "https://dashscope-us.aliyuncs.com/compatible-mode/v1",
    "cn": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}

region = ((cfg.get("qwen_api") or {}).get("region") or os.getenv("QWEN_REGION") or "sg").strip().lower()
return (override or env_base or api_base or REGION_BASE_URLS.get(region) or REGION_BASE_URLS["sg"]).rstrip("/")
```

Add `qwen_api_region` parsing in `config.py` and include in returned `qwen_api` section.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Adapters/unit/test_qwen_native_http.py -k region -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/LLM_Calls/providers/qwen_adapter.py tldw_Server_API/app/core/config.py tldw_Server_API/Config_Files/config.txt tldw_Server_API/tests/LLM_Adapters/unit/test_qwen_native_http.py
git commit -m "feat(qwen): add region-based base-url presets"
```

### Task 7: Add Curated Model Studio/Qwen Model Entries for Listing

**Files:**
- Modify: `tldw_Server_API/Config_Files/model_pricing.json`
- Modify: `tldw_Server_API/app/core/Usage/pricing_catalog.py`
- Test: `tldw_Server_API/tests/LLM_Adapters/unit/test_llm_models_filters.py`

**Step 1: Write the failing test**

```python
def test_llm_models_metadata_includes_qwen_curated_model(monkeypatch, client_user_only):
    import tldw_Server_API.app.api.v1.endpoints.llm_providers as llm_providers
    monkeypatch.setattr(llm_providers, "list_provider_models", lambda provider: ["qwen-max"] if provider == "qwen" else [])
    ...
    response = client_user_only.get("/api/v1/llm/models/metadata?provider=qwen")
    assert any(m.get("name") == "qwen-max" for m in response.json().get("models", []))
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Adapters/unit/test_llm_models_filters.py -k qwen -v`

Expected: FAIL if metadata/canonical listing path does not surface curated entries.

**Step 3: Write minimal implementation**

```json
"qwen": {
  "qwen-max": { "prompt": 0.0, "completion": 0.0, "placeholder": true, "note": "Verify latest Model Studio pricing." },
  "qwen-plus": { "prompt": 0.0, "completion": 0.0, "placeholder": true, "note": "Verify latest Model Studio pricing." },
  "qwen-turbo": { "prompt": 0.0, "completion": 0.0, "placeholder": true, "note": "Verify latest Model Studio pricing." }
}
```

Keep this additive and conservative (placeholder where pricing is not yet confirmed).

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Adapters/unit/test_llm_models_filters.py -k qwen -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/Config_Files/model_pricing.json tldw_Server_API/app/core/Usage/pricing_catalog.py tldw_Server_API/tests/LLM_Adapters/unit/test_llm_models_filters.py
git commit -m "feat(models): add curated qwen model entries for provider listing"
```

### Task 8: Documentation and End-to-End Verification

**Files:**
- Modify: `Docs/User_Guides/WebUI_Extension/Image_Generation_Setup.md`
- Modify: `Docs/Operations/Env_Vars.md`
- Modify: `Docs/Published/User_Guides/WebUI_Extension/Image_Generation_Setup.md`
- Modify: `Docs/Published/Env_Vars.md`

**Step 1: Write failing docs checks (lightweight)**

```bash
rg -n "modelstudio_image" Docs/User_Guides/WebUI_Extension/Image_Generation_Setup.md Docs/Operations/Env_Vars.md
```

Expected: no matches before edits.

**Step 2: Update docs**

Add:
- Config examples for `modelstudio` backend.
- Region examples (`sg`, `cn`, `us`).
- Sync/async mode examples.
- `POST /api/v1/files/create` payload example using `"backend": "modelstudio"`.

**Step 3: Run targeted test suite**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Image_Generation/test_modelstudio_image_adapter.py \
  tldw_Server_API/tests/Image_Generation/test_image_models_listing.py \
  tldw_Server_API/tests/Files/test_files_image_endpoint.py \
  tldw_Server_API/tests/LLM_Adapters/unit/test_qwen_native_http.py \
  -v
```

Expected: PASS.

**Step 4: Run Bandit on touched paths**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/Image_Generation \
  tldw_Server_API/app/core/LLM_Calls/providers/qwen_adapter.py \
  tldw_Server_API/app/core/File_Artifacts/adapters/image_adapter.py \
  -f json -o /tmp/bandit_modelstudio_image_qwen.json
```

Expected: no new high-severity issues in touched code.

**Step 5: Commit**

```bash
git add Docs/User_Guides/WebUI_Extension/Image_Generation_Setup.md Docs/Operations/Env_Vars.md Docs/Published/User_Guides/WebUI_Extension/Image_Generation_Setup.md Docs/Published/Env_Vars.md
git commit -m "docs(image): document modelstudio backend config and usage"
```

### Task 9: Final Integration Commit and PR Notes

**Files:**
- Modify: `Docs/Plans/2026-02-24-alibaba-modelstudio-support-design.md` (if implementation deltas occurred)
- Modify: `CHANGELOG.md` (if project policy requires release-note entry for provider additions)

**Step 1: Re-run full touched-test matrix**

Run:

```bash
source .venv/bin/activate && python -m pytest -m "unit or integration" \
  tldw_Server_API/tests/Image_Generation \
  tldw_Server_API/tests/Files/test_files_image_endpoint.py \
  tldw_Server_API/tests/LLM_Adapters/unit/test_qwen_native_http.py \
  -v
```

Expected: PASS for touched scopes.

**Step 2: Verify clean git status**

Run: `git status --short`

Expected: no unintended file changes.

**Step 3: Create final integration commit**

```bash
git add -A
git commit -m "feat(alibaba): add modelstudio image backend and qwen region-aware routing"
```

**Step 4: Prepare concise PR summary**

Include:
- what changed
- endpoints/config added
- test/bandit evidence
- migration/backward-compat notes

**Step 5: Optional follow-up issue list**

Create follow-ups for:
- dynamic model discovery
- automated pricing sync
- expanded image edit/variation API support

