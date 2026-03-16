# Audio Setup Resource Profiles And Offline Packs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the existing bundle-first `/setup` audio flow with profile-aware bundle differentiation and a phased offline-pack import/export path without breaking the current bundle rollout.

**Architecture:** Keep the current hardware-local bundle families, but make provisioning, verification, and persistence operate on `bundle_id + resource_profile + catalog_version`. Start by making catalog, readiness, recommendation, and installer step identity profile-aware. Only then add v1 offline packs for model/manifests and a separate import mode in `/setup`.

**Tech Stack:** FastAPI, Pydantic, existing setup manager/install manager, vanilla JS setup UI, pytest, current docs generator, Bandit.

---

### Task 1: Make the bundle catalog and readiness schema profile-aware

**Files:**
- Modify: `tldw_Server_API/app/core/Setup/audio_bundle_catalog.py`
- Modify: `tldw_Server_API/app/core/Setup/audio_readiness_store.py`
- Test: `tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py`
- Test: `tldw_Server_API/tests/Setup/test_audio_readiness_store.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.Setup.audio_bundle_catalog import get_audio_bundle_catalog
from tldw_Server_API.app.core.Setup.audio_readiness_store import AudioReadinessStore


def test_cpu_local_bundle_exposes_named_resource_profiles():
    bundle = get_audio_bundle_catalog().bundle_by_id("cpu_local")

    assert {"light", "balanced", "performance"} <= set(bundle.resource_profiles.keys())


def test_readiness_defaults_missing_profile_to_balanced(tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")
    store.path.write_text('{"status": "ready", "selected_bundle_id": "cpu_local"}', encoding="utf-8")

    readiness = store.load()
    assert readiness["selected_resource_profile"] == "balanced"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py tldw_Server_API/tests/Setup/test_audio_readiness_store.py -q
```

Expected: FAIL because the catalog and readiness schema do not yet support profiles.

**Step 3: Write minimal implementation**

Add profile-aware catalog models, for example:

```python
class AudioResourceProfile(BaseModel):
    profile_id: str
    label: str
    stt_plan: list[dict[str, Any]] = Field(default_factory=list)
    tts_plan: list[dict[str, Any]] = Field(default_factory=list)
    default_config_updates: dict[str, dict[str, str]] = Field(default_factory=dict)
    estimated_disk_gb: float | None = None
```

Extend the readiness record with:

- `selected_resource_profile`
- `catalog_version`
- `selection_key`
- `installed_profiles`

Default legacy bundle-only records to:

- `selected_resource_profile="balanced"`

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py tldw_Server_API/tests/Setup/test_audio_readiness_store.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Setup/audio_bundle_catalog.py tldw_Server_API/app/core/Setup/audio_readiness_store.py tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py tldw_Server_API/tests/Setup/test_audio_readiness_store.py
git commit -m "feat: add profile-aware audio setup catalog state"
```

### Task 2: Return ranked family/profile recommendations from setup

**Files:**
- Modify: `tldw_Server_API/app/core/Setup/audio_profile_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/setup.py`
- Test: `tldw_Server_API/tests/Setup/test_audio_profile_service.py`
- Test: `tldw_Server_API/tests/integration/test_setup_audio_recommendations.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.Setup.audio_profile_service import MachineProfile, rank_audio_bundles


def test_cuda_machine_prefers_balanced_or_performance_nvidia_profile_when_signals_are_strong():
    profile = MachineProfile(
        platform="linux",
        arch="x86_64",
        apple_silicon=False,
        cuda_available=True,
        ffmpeg_available=True,
        espeak_available=True,
        free_disk_gb=120.0,
        network_available_for_downloads=True,
    )

    ranked = rank_audio_bundles(profile, prefer_offline_runtime=True, allow_hosted_fallbacks=True)
    assert ranked[0].bundle_id == "nvidia_local"
    assert ranked[0].resource_profile in {"balanced", "performance"}
```

Integration example:

```python
def test_setup_audio_recommendations_endpoint_returns_profile_fields(client, mocker):
    response = client.get("/api/v1/setup/audio/recommendations")

    assert response.status_code == 200
    first = response.json()["recommendations"][0]
    assert "resource_profile" in first
    assert "confidence" in first
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_profile_service.py tldw_Server_API/tests/integration/test_setup_audio_recommendations.py -q
```

Expected: FAIL because ranking is still bundle-only.

**Step 3: Write minimal implementation**

Extend recommendation objects with:

- `resource_profile`
- `selection_key`
- `confidence`

Keep the V1 policy conservative:

- default to `balanced`
- recommend `light` when disk is constrained
- recommend `performance` only with positive hardware evidence

Update the setup endpoint to return catalog data with profile metadata attached to the selected recommendation.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_profile_service.py tldw_Server_API/tests/integration/test_setup_audio_recommendations.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Setup/audio_profile_service.py tldw_Server_API/app/api/v1/endpoints/setup.py tldw_Server_API/tests/Setup/test_audio_profile_service.py tldw_Server_API/tests/integration/test_setup_audio_recommendations.py
git commit -m "feat: add profile-aware audio recommendations"
```

### Task 3: Make provisioning and safe rerun exact-match for family/profile selections

**Files:**
- Modify: `tldw_Server_API/app/core/Setup/install_manager.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/setup.py`
- Test: `tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py`
- Test: `tldw_Server_API/tests/integration/test_setup_audio_readiness.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.Setup.install_manager import _plan_step_names, build_install_plan_from_bundle


def test_step_names_include_profile_identity():
    plan = build_install_plan_from_bundle("cpu_local", resource_profile="performance")
    step_names = _plan_step_names(plan, bundle_id="cpu_local", resource_profile="performance", catalog_version="v2")

    assert any("cpu_local" in step for step in step_names)
    assert any("performance" in step for step in step_names)


def test_safe_rerun_does_not_skip_when_profile_changes(mocker):
    mocker.patch(
        "tldw_Server_API.app.core.Setup.install_manager.get_install_status_snapshot",
        return_value={"steps": [{"name": "v2:cpu_local:light:stt:faster_whisper:tiny", "status": "completed"}]},
    )
```

Integration example:

```python
def test_provision_endpoint_accepts_resource_profile(client):
    response = client.post("/api/v1/setup/audio/provision", json={"bundle_id": "cpu_local", "resource_profile": "balanced"})
    assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py tldw_Server_API/tests/integration/test_setup_audio_readiness.py -q
```

Expected: FAIL because provisioning still accepts only `bundle_id`.

**Step 3: Write minimal implementation**

Update:

- `build_install_plan_from_bundle(bundle_id, resource_profile="balanced")`
- `AudioBundleProvisionRequest`
- step identity generation to include family/profile/catalog version and model detail

Persist into readiness:

- `selected_bundle_id`
- `selected_resource_profile`
- `selection_key`

Keep `safe_rerun` semantics exact-match only.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py tldw_Server_API/tests/integration/test_setup_audio_readiness.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Setup/install_manager.py tldw_Server_API/app/api/v1/endpoints/setup.py tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py tldw_Server_API/tests/integration/test_setup_audio_readiness.py
git commit -m "feat: make audio provisioning profile aware"
```

### Task 4: Make verification and readiness classification profile-aware

**Files:**
- Modify: `tldw_Server_API/app/core/Setup/install_manager.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/audio_health.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/setup.py`
- Test: `tldw_Server_API/tests/Setup/test_audio_bundle_verification.py`
- Test: `tldw_Server_API/tests/integration/test_setup_audio_verification.py`

**Step 1: Write the failing test**

```python
def test_verify_audio_bundle_uses_selected_profile_expectations(mocker):
    mocker.patch(
        "tldw_Server_API.app.core.Setup.install_manager.audio_health.collect_setup_stt_health",
        return_value={"usable": True, "active_model": "small"},
    )
    result = run_verify(bundle_id="cpu_local", resource_profile="light")
    assert result["selected_resource_profile"] == "light"
```

Integration example:

```python
def test_verify_endpoint_requires_profile_when_not_using_default(client):
    response = client.post("/api/v1/setup/audio/verify", json={"bundle_id": "nvidia_local", "resource_profile": "performance"})
    assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_verification.py tldw_Server_API/tests/integration/test_setup_audio_verification.py -q
```

Expected: FAIL because verification is still bundle-level.

**Step 3: Write minimal implementation**

Update verification to:

- accept `resource_profile`
- resolve expected engines/models from the selected profile
- include `selected_resource_profile` and `selection_key` in result payloads
- record profile-aware verification state in readiness

Keep secondary fallbacks advisory.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_verification.py tldw_Server_API/tests/integration/test_setup_audio_verification.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Setup/install_manager.py tldw_Server_API/app/api/v1/endpoints/audio/audio_health.py tldw_Server_API/app/api/v1/endpoints/setup.py tldw_Server_API/tests/Setup/test_audio_bundle_verification.py tldw_Server_API/tests/integration/test_setup_audio_verification.py
git commit -m "feat: add profile-aware audio verification"
```

### Task 5: Update the `/setup` UI for profile selection with progressive disclosure

**Files:**
- Modify: `tldw_Server_API/app/static/setup/js/setup.js`
- Modify: `tldw_Server_API/app/static/setup/css/setup.css`
- Modify: `tldw_Server_API/app/Setup_UI/setup.html`
- Test: `apps/tldw-frontend/__tests__/vitest.setup-contract.test.ts`
- Test: `tldw_Server_API/tests/integration/test_setup_installation.py`

**Step 1: Write the failing test**

```ts
it('mentions resource profiles in the setup contract', () => {
  expect(scriptContents).toContain('Recommended profile');
  expect(scriptContents).toContain('Light');
  expect(scriptContents).toContain('Balanced');
  expect(scriptContents).toContain('Performance');
});
```

Integration example:

```python
def test_setup_script_references_audio_profile_payload_fields():
    assert '"resource_profile"' in setup_js_text
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/integration/test_setup_installation.py -q
cd apps/tldw-frontend && bunx vitest run __tests__/vitest.setup-contract.test.ts
```

Expected: FAIL because the UI does not expose profile selection yet.

**Step 3: Write minimal implementation**

Update the selected family card to render profile chips or compact cards for:

- `Light`
- `Balanced`
- `Performance`

Send `resource_profile` with:

- `/api/v1/setup/audio/provision`
- `/api/v1/setup/audio/verify`

Keep offline-pack import out of the main path for now; only reserve a secondary mode container if needed.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/integration/test_setup_installation.py -q
cd apps/tldw-frontend && bunx vitest run __tests__/vitest.setup-contract.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/static/setup/js/setup.js tldw_Server_API/app/static/setup/css/setup.css tldw_Server_API/app/Setup_UI/setup.html apps/tldw-frontend/__tests__/vitest.setup-contract.test.ts tldw_Server_API/tests/integration/test_setup_installation.py
git commit -m "feat: add setup audio resource profile selection"
```

### Task 6: Add v1 audio bundle pack export/import for model and manifest portability

**Files:**
- Create: `tldw_Server_API/app/core/Setup/audio_pack_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/setup.py`
- Modify: `tldw_Server_API/app/core/Setup/audio_readiness_store.py`
- Test: `tldw_Server_API/tests/Setup/test_audio_pack_service.py`
- Test: `tldw_Server_API/tests/integration/test_setup_audio_packs.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.Setup.audio_pack_service import build_audio_pack_manifest


def test_audio_pack_manifest_captures_selection_identity():
    manifest = build_audio_pack_manifest(
        bundle_id="cpu_local",
        resource_profile="balanced",
        catalog_version="v2",
    )

    assert manifest["bundle_id"] == "cpu_local"
    assert manifest["resource_profile"] == "balanced"
    assert "checksums" in manifest
```

Integration example:

```python
def test_setup_audio_pack_import_updates_readiness(client, tmp_path):
    response = client.post("/api/v1/setup/audio/packs/import", json={"pack_path": str(tmp_path / "pack.json")})
    assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_pack_service.py tldw_Server_API/tests/integration/test_setup_audio_packs.py -q
```

Expected: FAIL because pack service and endpoints do not exist.

**Step 3: Write minimal implementation**

Create a v1 pack service that supports:

- manifest creation
- checksum validation
- platform/arch/Python compatibility checks
- import registration into readiness

Scope v1 to model and manifest portability only. Do not promise offline dependency installation yet.

Add setup endpoints for:

- export manifest
- import pack

Persist imported pack metadata in readiness.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_pack_service.py tldw_Server_API/tests/integration/test_setup_audio_packs.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Setup/audio_pack_service.py tldw_Server_API/app/api/v1/endpoints/setup.py tldw_Server_API/app/core/Setup/audio_readiness_store.py tldw_Server_API/tests/Setup/test_audio_pack_service.py tldw_Server_API/tests/integration/test_setup_audio_packs.py
git commit -m "feat: add setup audio bundle pack import export"
```

### Task 7: Update docs, generated bundle docs, and final verification

**Files:**
- Modify: `Helper_Scripts/generate_audio_bundle_docs.py`
- Modify: `Docs/Deployment/setup-wizard-guide.md`
- Modify: `Docs/User_Guides/WebUI_Extension/Getting-Started-STT_and_TTS.md`
- Modify: `Docs/User_Guides/WebUI_Extension/TTS_Getting_Started.md`
- Test: `tldw_Server_API/tests/Docs/test_audio_bundle_docs.py`
- Test: `tldw_Server_API/tests/Docs/test_stt_tts_guide_roles.py`
- Test: `tldw_Server_API/tests/Docs/test_stt_tts_link_hygiene.py`
- Test: `tldw_Server_API/tests/Docs/test_speech_api_guide_map.py`

**Step 1: Write the failing test**

```python
def test_generated_audio_bundle_docs_include_profiles():
    text = generate_bundle_docs_text()
    assert "Balanced" in text
    assert "Performance" in text
    assert "Offline pack compatibility" in text
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Docs/test_audio_bundle_docs.py -q
```

Expected: FAIL because docs output is still family-level.

**Step 3: Write minimal implementation**

Update the docs generator and guides to show:

- family plus profile distinctions
- disk/resource expectations
- the difference between online provisioning and offline-pack import
- the limited v1 scope of offline packs

**Step 4: Run full touched verification**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py tldw_Server_API/tests/Setup/test_audio_profile_service.py tldw_Server_API/tests/Setup/test_audio_readiness_store.py tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py tldw_Server_API/tests/Setup/test_audio_bundle_verification.py tldw_Server_API/tests/Setup/test_audio_pack_service.py tldw_Server_API/tests/integration/test_setup_audio_recommendations.py tldw_Server_API/tests/integration/test_setup_audio_readiness.py tldw_Server_API/tests/integration/test_setup_audio_verification.py tldw_Server_API/tests/integration/test_setup_audio_packs.py tldw_Server_API/tests/integration/test_setup_installation.py tldw_Server_API/tests/Docs/test_audio_bundle_docs.py tldw_Server_API/tests/Docs/test_stt_tts_guide_roles.py tldw_Server_API/tests/Docs/test_stt_tts_link_hygiene.py tldw_Server_API/tests/Docs/test_speech_api_guide_map.py -q
cd apps/tldw-frontend && bunx vitest run __tests__/vitest.setup-contract.test.ts
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Setup tldw_Server_API/app/api/v1/endpoints/setup.py tldw_Server_API/app/api/v1/endpoints/audio/audio_health.py -f json -o /tmp/bandit_audio_setup_profiles_packs.json
git diff --check
```

Expected: PASS, Bandit JSON with no new findings in touched scope, and clean diff check.

**Step 5: Commit**

```bash
git add Helper_Scripts/generate_audio_bundle_docs.py Docs/Deployment/setup-wizard-guide.md Docs/User_Guides/WebUI_Extension/Getting-Started-STT_and_TTS.md Docs/User_Guides/WebUI_Extension/TTS_Getting_Started.md tldw_Server_API/tests/Docs/test_audio_bundle_docs.py tldw_Server_API/tests/Docs/test_stt_tts_guide_roles.py tldw_Server_API/tests/Docs/test_stt_tts_link_hygiene.py tldw_Server_API/tests/Docs/test_speech_api_guide_map.py
git commit -m "docs: align audio setup profiles and offline packs"
```
