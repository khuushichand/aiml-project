# Audio Setup Bundles Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a bundle-first audio provisioning flow in `/setup` with machine-profile-based bundle recommendation, separate audio readiness tracking, safe reruns, and operator-facing verification.

**Architecture:** Add a versioned audio bundle catalog and a lightweight machine profile detector in the setup backend, expand bundle selections into the existing install manager, persist an `audio_readiness` lifecycle separately from global setup completion, and update the `/setup` UI to guide operators through recommendation, provisioning, and verification. Keep the current provider-level install plan as the execution substrate for v1 and move it behind advanced mode rather than deleting it.

**Tech Stack:** FastAPI, Pydantic, existing setup manager/install manager, vanilla JS setup UI, pytest, existing integration tests.

---

### Task 1: Add an audio bundle catalog and schema

**Files:**
- Create: `tldw_Server_API/app/core/Setup/audio_bundle_catalog.py`
- Modify: `tldw_Server_API/app/core/Setup/install_schema.py`
- Test: `tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.Setup.audio_bundle_catalog import get_audio_bundle_catalog


def test_catalog_contains_expected_v1_bundle_ids():
    catalog = get_audio_bundle_catalog()
    bundle_ids = {bundle.bundle_id for bundle in catalog.bundles}

    assert {"cpu_local", "apple_silicon_local", "nvidia_local", "hosted_plus_local_backup"} <= bundle_ids


def test_bundle_declares_automation_tiers_for_steps():
    catalog = get_audio_bundle_catalog()
    bundle = catalog.bundle_by_id("cpu_local")

    assert any(step.automation_tier == "automatic" for step in bundle.system_prerequisites + bundle.python_dependencies + bundle.model_assets)
    assert any(step.automation_tier == "guided" for step in bundle.system_prerequisites)
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py -q
```

Expected: FAIL because the bundle catalog module and schema do not exist.

**Step 3: Write minimal implementation**

Create a dedicated setup catalog module with small Pydantic models, for example:

```python
class AutomationTier(str, Enum):
    AUTOMATIC = "automatic"
    GUIDED = "guided"
    MANUAL_BLOCKED = "manual_blocked"


class AudioBundleStep(BaseModel):
    step_id: str
    label: str
    automation_tier: AutomationTier
    detail: str | None = None
    linux_hint: str | None = None
    macos_hint: str | None = None
    windows_hint: str | None = None
```

Add a top-level catalog object with:

- bundle ids
- operator-facing labels
- offline suitability
- prerequisite steps
- mapped STT/TTS install plan defaults
- default verification targets

Extend `install_schema.py` only as needed to support bundle expansion inputs later, without breaking existing provider-level plans.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Setup/audio_bundle_catalog.py tldw_Server_API/app/core/Setup/install_schema.py tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py
git commit -m "feat: add audio setup bundle catalog"
```

### Task 2: Add machine profile detection and bundle recommendation

**Files:**
- Create: `tldw_Server_API/app/core/Setup/audio_profile_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/setup.py`
- Test: `tldw_Server_API/tests/Setup/test_audio_profile_service.py`
- Test: `tldw_Server_API/tests/integration/test_setup_audio_recommendations.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.Setup.audio_profile_service import rank_audio_bundles, MachineProfile


def test_nvidia_machine_prefers_nvidia_bundle():
    profile = MachineProfile(
        platform="linux",
        arch="x86_64",
        apple_silicon=False,
        cuda_available=True,
        ffmpeg_available=True,
        espeak_available=True,
        free_disk_gb=80.0,
        network_available_for_downloads=True,
    )

    ranked = rank_audio_bundles(profile, prefer_offline_runtime=True, allow_hosted_fallbacks=True)
    assert ranked[0].bundle_id == "nvidia_local"
```

Integration example:

```python
def test_setup_audio_recommendations_endpoint_returns_profile_and_ranked_bundles(client, mocker):
    mocker.patch("tldw_Server_API.app.core.Setup.audio_profile_service.detect_machine_profile", return_value=...)
    response = client.get("/api/v1/setup/audio/recommendations")
    assert response.status_code == 200
    assert response.json()["recommendations"][0]["bundle_id"] == "cpu_local"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_profile_service.py tldw_Server_API/tests/integration/test_setup_audio_recommendations.py -q
```

Expected: FAIL because the service and endpoint do not exist.

**Step 3: Write minimal implementation**

Implement:

- `MachineProfile`
- `detect_machine_profile()`
- `rank_audio_bundles(...)`

Scope v1 detection to signals the current platform can trust:

- OS/platform
- arch
- Apple Silicon
- CUDA
- FFmpeg
- eSpeak
- free disk

Add a setup endpoint that returns:

```json
{
  "machine_profile": {...},
  "recommendations": [
    {"bundle_id": "cpu_local", "score": 100, "reasons": ["Works offline after provisioning"] }
  ],
  "excluded": [
    {"bundle_id": "nvidia_local", "reasons": ["CUDA not detected"] }
  ]
}
```

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_profile_service.py tldw_Server_API/tests/integration/test_setup_audio_recommendations.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Setup/audio_profile_service.py tldw_Server_API/app/api/v1/endpoints/setup.py tldw_Server_API/tests/Setup/test_audio_profile_service.py tldw_Server_API/tests/integration/test_setup_audio_recommendations.py
git commit -m "feat: add setup audio bundle recommendations"
```

### Task 3: Add audio readiness persistence separate from global setup completion

**Files:**
- Create: `tldw_Server_API/app/core/Setup/audio_readiness_store.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/setup.py`
- Modify: `tldw_Server_API/app/core/Setup/install_manager.py`
- Test: `tldw_Server_API/tests/Setup/test_audio_readiness_store.py`
- Test: `tldw_Server_API/tests/integration/test_setup_audio_readiness.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.Setup.audio_readiness_store import AudioReadinessStore


def test_audio_readiness_defaults_to_not_started(tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")
    readiness = store.load()

    assert readiness["status"] == "not_started"
    assert readiness["selected_bundle_id"] is None
```

Integration example:

```python
def test_setup_complete_does_not_imply_audio_ready(client, mocker):
    response = client.post("/api/v1/setup/complete", json={"disable_first_time_setup": False})
    assert response.status_code == 200

    readiness = client.get("/api/v1/setup/audio/readiness")
    assert readiness.json()["status"] == "not_started"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_readiness_store.py tldw_Server_API/tests/integration/test_setup_audio_readiness.py -q
```

Expected: FAIL because audio readiness storage does not exist.

**Step 3: Write minimal implementation**

Create a small persisted readiness record with fields like:

```python
{
  "status": "not_started",
  "selected_bundle_id": None,
  "machine_profile": None,
  "last_verification": None,
  "remediation_items": [],
  "updated_at": "..."
}
```

Add endpoints to:

- fetch current readiness
- reset readiness

Update the install manager entry points so bundle provisioning can write readiness states like:

- `provisioning`
- `partial`
- `ready`
- `failed`

Do not change the semantics of the existing global `setup_completed` flag.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_readiness_store.py tldw_Server_API/tests/integration/test_setup_audio_readiness.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Setup/audio_readiness_store.py tldw_Server_API/app/api/v1/endpoints/setup.py tldw_Server_API/app/core/Setup/install_manager.py tldw_Server_API/tests/Setup/test_audio_readiness_store.py tldw_Server_API/tests/integration/test_setup_audio_readiness.py
git commit -m "feat: persist setup audio readiness state"
```

### Task 4: Expand bundle selections into provisioning steps with safe rerun semantics

**Files:**
- Modify: `tldw_Server_API/app/core/Setup/install_manager.py`
- Modify: `tldw_Server_API/app/core/Setup/audio_bundle_catalog.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/setup.py`
- Test: `tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.Setup.install_manager import build_install_plan_from_bundle


def test_cpu_local_bundle_expands_to_expected_install_plan():
    plan = build_install_plan_from_bundle("cpu_local")

    assert [entry.engine for entry in plan.stt] == ["faster_whisper"]
    assert [entry.engine for entry in plan.tts] == ["kokoro"]
```

Safe rerun example:

```python
def test_safe_rerun_skips_satisfied_steps(mocker):
    mocker.patch("tldw_Server_API.app.core.Setup.install_manager._install_faster_whisper")
    mocker.patch("tldw_Server_API.app.core.Setup.install_manager._install_kokoro")

    # seed readiness/store/status to show prerequisites satisfied and models present
    ...
    result = execute_audio_bundle("cpu_local", rerun=True)

    assert "skipped" in {step["status"] for step in result["steps"]}
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py -q
```

Expected: FAIL because bundle expansion and safe rerun support do not exist.

**Step 3: Write minimal implementation**

Add:

- bundle id -> install plan expansion helper
- bundle provisioning entry point
- layered step execution for:
  - system prerequisites
  - Python dependencies
  - model assets
  - config defaults
  - verification trigger

Use explicit step statuses:

- `completed`
- `failed`
- `skipped`
- `guided_action_required`

Do not label the action `resume`. Use:

- `safe_rerun`

Only skip work when it can be positively detected as already satisfied.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Setup/install_manager.py tldw_Server_API/app/core/Setup/audio_bundle_catalog.py tldw_Server_API/app/api/v1/endpoints/setup.py tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py
git commit -m "feat: add bundle-based audio provisioning"
```

### Task 5: Add verification endpoints and readiness classification

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/setup.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/audio_health.py`
- Modify: `tldw_Server_API/app/core/Setup/install_manager.py`
- Test: `tldw_Server_API/tests/Setup/test_audio_bundle_verification.py`
- Test: `tldw_Server_API/tests/integration/test_setup_audio_verification.py`

**Step 1: Write the failing test**

```python
def test_verification_marks_partial_when_tts_prereq_missing(mocker):
    mocker.patch("tldw_Server_API.app.api.v1.endpoints.audio.audio_health.get_stt_health", return_value={"usable": True})
    mocker.patch("tldw_Server_API.app.api.v1.endpoints.audio.audio_health.get_tts_health", return_value={
        "status": "healthy",
        "providers": {"kokoro": {"espeak_lib_exists": False}}
    })

    result = verify_audio_bundle("cpu_local")

    assert result["status"] == "partial"
    assert any("eSpeak" in item["message"] for item in result["remediation_items"])
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_verification.py tldw_Server_API/tests/integration/test_setup_audio_verification.py -q
```

Expected: FAIL because bundle verification and readiness classification do not exist.

**Step 3: Write minimal implementation**

Add a setup-scoped verification service that:

- evaluates one primary STT path
- evaluates one primary TTS path
- checks required assets/prerequisites
- classifies readiness as:
  - `ready`
  - `ready_with_warnings`
  - `partial`
  - `failed`

Persist remediation items like:

```python
{
  "code": "KOKORO_ESPEAK_MISSING",
  "message": "Install espeak-ng and rerun verification.",
  "action": "safe_rerun"
}
```

Keep secondary providers advisory-only in v1.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_verification.py tldw_Server_API/tests/integration/test_setup_audio_verification.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/setup.py tldw_Server_API/app/api/v1/endpoints/audio/audio_health.py tldw_Server_API/app/core/Setup/install_manager.py tldw_Server_API/tests/Setup/test_audio_bundle_verification.py tldw_Server_API/tests/integration/test_setup_audio_verification.py
git commit -m "feat: add setup audio verification and readiness classification"
```

### Task 6: Add the bundle-first audio stage to the setup UI

**Files:**
- Modify: `tldw_Server_API/app/static/setup/js/setup.js`
- Modify: `tldw_Server_API/app/Setup_UI/setup.html`
- Modify: `tldw_Server_API/app/static/setup/css/setup.css`
- Test: `tldw_Server_API/tests/integration/test_setup_installation.py`
- Test: `apps/tldw-frontend/__tests__/vitest.setup-contract.test.ts`

**Step 1: Write the failing test**

Add a setup contract/integration test that expects:

- audio recommendations to be requested
- a recommended bundle card to render
- a provisioning action to submit the selected bundle id instead of raw provider lists

Example JS expectation:

```ts
expect(screen.getByText(/recommended audio bundle/i)).toBeInTheDocument()
expect(screen.getByRole('button', { name: /provision recommended bundle/i })).toBeInTheDocument()
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/integration/test_setup_installation.py -q
```

If there is browser-contract coverage for the setup UI:

```bash
bunx vitest run apps/tldw-frontend/__tests__/vitest.setup-contract.test.ts
```

Expected: FAIL because the UI still centers provider-level selection.

**Step 3: Write minimal implementation**

Update `/setup` UI to:

- fetch machine profile + bundle recommendations
- render recommended and alternative bundles
- show automation tiers and guided prerequisites
- expose actions:
  - `Provision recommended bundle`
  - `Choose different bundle`
  - `Run verification`
  - `Safe rerun`
  - `View readiness report`

Keep the current provider-level installer as an advanced fallback, not the default step.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/integration/test_setup_installation.py -q
```

And, if applicable:

```bash
bunx vitest run apps/tldw-frontend/__tests__/vitest.setup-contract.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/static/setup/js/setup.js tldw_Server_API/app/Setup_UI/setup.html tldw_Server_API/app/static/setup/css/setup.css tldw_Server_API/tests/integration/test_setup_installation.py apps/tldw-frontend/__tests__/vitest.setup-contract.test.ts
git commit -m "feat: add bundle-first audio setup UI"
```

### Task 7: Align generated docs and setup guides with the bundle model

**Files:**
- Modify: `Docs/Deployment/setup-wizard-guide.md`
- Modify: `Docs/User_Guides/WebUI_Extension/Getting-Started-STT_and_TTS.md`
- Modify: `Docs/User_Guides/WebUI_Extension/TTS_Getting_Started.md`
- Create: `Helper_Scripts/generate_audio_bundle_docs.py`
- Test: `tldw_Server_API/tests/Docs/test_audio_bundle_docs.py`

**Step 1: Write the failing test**

```python
def test_generated_bundle_docs_reference_all_v1_bundle_ids():
    content = generate_bundle_docs_text()
    assert "cpu_local" in content
    assert "apple_silicon_local" in content
    assert "nvidia_local" in content
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Docs/test_audio_bundle_docs.py -q
```

Expected: FAIL because docs are still manually maintained and bundle-driven generation does not exist.

**Step 3: Write minimal implementation**

Create a small generator that reads the audio bundle catalog and emits:

- bundle names
- offline suitability
- automated vs guided prerequisites
- default STT/TTS stacks

Use that generated output to update the setup wizard guide and speech quickstart so the bundle path is the default operator story.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Docs/test_audio_bundle_docs.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add Docs/Deployment/setup-wizard-guide.md Docs/User_Guides/WebUI_Extension/Getting-Started-STT_and_TTS.md Docs/User_Guides/WebUI_Extension/TTS_Getting_Started.md Helper_Scripts/generate_audio_bundle_docs.py tldw_Server_API/tests/Docs/test_audio_bundle_docs.py
git commit -m "docs: align setup guides with audio bundles"
```

### Task 8: Run focused verification and security checks for the touched scope

**Files:**
- Modify: `Docs/Plans/2026-03-15-audio-setup-bundles-implementation-plan.md`

**Step 1: Run backend test suites for touched setup scope**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py \
  tldw_Server_API/tests/Setup/test_audio_profile_service.py \
  tldw_Server_API/tests/Setup/test_audio_readiness_store.py \
  tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py \
  tldw_Server_API/tests/Setup/test_audio_bundle_verification.py \
  tldw_Server_API/tests/integration/test_setup_audio_recommendations.py \
  tldw_Server_API/tests/integration/test_setup_audio_readiness.py \
  tldw_Server_API/tests/integration/test_setup_audio_verification.py \
  tldw_Server_API/tests/integration/test_setup_installation.py -q
```

Expected: PASS.

**Step 2: Run any setup UI contract tests**

Run:

```bash
bunx vitest run apps/tldw-frontend/__tests__/vitest.setup-contract.test.ts
```

Expected: PASS.

**Step 3: Run Bandit on the touched backend setup scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/Setup \
  tldw_Server_API/app/api/v1/endpoints/setup.py \
  tldw_Server_API/app/api/v1/endpoints/audio/audio_health.py \
  -f json -o /tmp/bandit_audio_setup_bundles.json
```

Expected: no new high-signal findings in changed code.

**Step 4: Update plan execution notes if commands need adjustment**

If any command paths or filenames changed during implementation, update this plan with the exact final verification commands before handoff or execution.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-15-audio-setup-bundles-implementation-plan.md
git commit -m "docs: finalize audio setup bundles verification plan"
```

Plan complete and saved to `Docs/Plans/2026-03-15-audio-setup-bundles-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
