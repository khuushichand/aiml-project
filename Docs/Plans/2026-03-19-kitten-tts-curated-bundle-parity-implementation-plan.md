# KittenTTS Curated Bundle Parity Implementation Plan

**Goal:** Verify the existing `kitten_tts` speech path and add `kitten_tts` as a curated peer TTS choice to low-resource CPU-local setup profiles.

**Architecture:** Keep the existing bundle/profile recommendation system and add an explicit `tts_choice` dimension only where curated low-resource CPU profiles need peer TTS options. Resolve that choice into a one-engine installer plan, propagate it through readiness/status/offline-pack persistence, and add a focused backend speech integration test proving the existing `kitten_tts` provider route already works.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, pytest, React, Vitest, existing setup installer helpers, existing TTS service and adapter registry.

---

## Stage 1: Prove Existing Kitten Speech Routing
**Goal:** Add a focused failing test that proves `/api/v1/audio/speech` routes `model="kitten_tts"` through the current backend path.
**Success Criteria:** The backend test fails before implementation changes, then passes by exercising the real endpoint/service/provider resolution path with mocked adapter behavior.
**Tests:** `tldw_Server_API/tests/Audio/test_tts_provider_inference.py`, `tldw_Server_API/tests/Audio/test_audio_speech_kittentts_integration.py`
**Status:** Complete

### Task 1: Add the failing endpoint integration test

**Files:**
- Create: `tldw_Server_API/tests/Audio/test_audio_speech_kittentts_integration.py`

**Step 1: Write the failing test**

```python
def test_audio_speech_routes_kitten_model_to_kitten_provider(client, mocker):
    captured = {}

    async def fake_generate(request, provider=None, **kwargs):
        captured["provider"] = provider
        return {
            "audio_data": b"RIFF....",
            "format": "wav",
            "sample_rate": 24000,
            "provider": "kitten_tts",
            "model": "KittenML/kitten-tts-nano-0.8-fp32",
        }

    mocker.patch("tldw_Server_API.app.api.v1.endpoints.audio.tts_service.generate_speech", side_effect=fake_generate)

    response = client.post(
        "/api/v1/audio/speech",
        json={"model": "kitten_tts", "input": "hello", "voice": "Bella", "response_format": "wav"},
    )

    assert response.status_code == 200
    assert captured["provider"] == "kitten_tts"
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Audio/test_audio_speech_kittentts_integration.py -v
```

Expected: FAIL because the endpoint test does not exist yet or because the current provider capture path is not asserted correctly.

**Step 3: Write minimal implementation**

**Files:**
- Modify: `tldw_Server_API/tests/Audio/test_audio_speech_kittentts_integration.py`
- Modify: `tldw_Server_API/tests/Audio/test_tts_provider_inference.py`

Implementation notes:
- Reuse existing endpoint fixtures and mocking patterns from the audio endpoint tests.
- Keep this test at the endpoint/service boundary; do not download real Kitten model assets.
- Add one provider-inference assertion if the endpoint test reveals a missing alias edge case.

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Audio/test_audio_speech_kittentts_integration.py -v
python -m pytest tldw_Server_API/tests/Audio/test_tts_provider_inference.py -k kitten -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Audio/test_audio_speech_kittentts_integration.py tldw_Server_API/tests/Audio/test_tts_provider_inference.py
git commit -m "test(audio): cover kitten_tts speech routing"
```

## Stage 2: Add Curated `tts_choice` To CPU-Local Profiles
**Goal:** Extend the curated bundle model so `cpu_local.light` and `cpu_local.balanced` expose both `kokoro` and `kitten_tts` as peer choices without duplicating bundles.
**Success Criteria:** Bundle/profile data contains explicit curated TTS choices and a stable default choice; no profile provisions both engines by default.
**Tests:** `tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py`
**Status:** Complete

### Task 2: Add the failing catalog tests

**Files:**
- Modify: `tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py`

**Step 1: Write the failing tests**

```python
def test_cpu_local_light_profile_exposes_kokoro_and_kitten_choices():
    profile = get_audio_bundle_catalog().bundle_by_id("cpu_local").profile_by_id("light")

    assert [choice["choice_id"] for choice in profile.tts_choices] == ["kokoro", "kitten_tts"]
    assert profile.default_tts_choice == "kokoro"


def test_cpu_local_balanced_profile_exposes_kokoro_and_kitten_choices():
    profile = get_audio_bundle_catalog().bundle_by_id("cpu_local").profile_by_id("balanced")

    assert {choice["choice_id"] for choice in profile.tts_choices} == {"kokoro", "kitten_tts"}
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py -v
```

Expected: FAIL because `tts_choices` and `default_tts_choice` do not exist yet.

**Step 3: Write minimal implementation**

**Files:**
- Modify: `tldw_Server_API/app/core/Setup/audio_bundle_catalog.py`

Implementation notes:
- Add a small Pydantic model for curated TTS choice metadata.
- Add `tts_choices` and `default_tts_choice` to `AudioResourceProfile`.
- Populate `cpu_local.light` and `cpu_local.balanced` with:
  - Kokoro choice -> one-engine `tts_plan`
  - KittenTTS choice -> one-engine `tts_plan`
- Leave `performance`, Apple Silicon, NVIDIA, and hybrid profiles unchanged in V1.

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Setup/audio_bundle_catalog.py tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py
git commit -m "feat(setup): add curated kitten_tts choices to cpu audio profiles"
```

## Stage 3: Make Selection Identity And Install Resolution Choice-Aware
**Goal:** Add `tts_choice` to setup selection identity and resolve it into a concrete one-engine installer plan.
**Success Criteria:** Provision/install/readiness metadata distinguishes `cpu_local:balanced:kokoro` from `cpu_local:balanced:kitten_tts`, and install-plan generation provisions only the chosen engine.
**Tests:** `tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py`, `tldw_Server_API/tests/Setup/test_audio_readiness_store.py`, `tldw_Server_API/tests/Setup/test_audio_pack_service.py`
**Status:** Complete

### Task 3: Add failing persistence and plan-resolution tests

**Files:**
- Modify: `tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py`
- Modify: `tldw_Server_API/tests/Setup/test_audio_readiness_store.py`
- Modify: `tldw_Server_API/tests/Setup/test_audio_pack_service.py`

**Step 1: Write the failing tests**

```python
def test_build_install_plan_from_bundle_uses_selected_kitten_choice():
    plan = install_manager.build_install_plan_from_bundle(
        "cpu_local",
        resource_profile="balanced",
        tts_choice="kitten_tts",
    )
    assert plan.tts == [{"engine": "kitten_tts", "variants": []}]


def test_selection_key_distinguishes_curated_tts_choice():
    assert build_audio_selection_key("cpu_local", "balanced", "v2", tts_choice="kokoro") != \
           build_audio_selection_key("cpu_local", "balanced", "v2", tts_choice="kitten_tts")


def test_audio_pack_manifest_persists_selected_tts_choice():
    manifest = build_audio_pack_manifest(bundle_id="cpu_local", resource_profile="balanced", tts_choice="kitten_tts")
    assert manifest["selected_tts_choice"] == "kitten_tts"
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py -v
python -m pytest tldw_Server_API/tests/Setup/test_audio_readiness_store.py -v
python -m pytest tldw_Server_API/tests/Setup/test_audio_pack_service.py -v
```

Expected: FAIL because `tts_choice` is not part of the current selection model.

**Step 3: Write minimal implementation**

**Files:**
- Modify: `tldw_Server_API/app/core/Setup/audio_bundle_catalog.py`
- Modify: `tldw_Server_API/app/core/Setup/audio_readiness_store.py`
- Modify: `tldw_Server_API/app/core/Setup/audio_pack_service.py`
- Modify: `tldw_Server_API/app/core/Setup/install_manager.py`

Implementation notes:
- Extend `build_audio_selection_key(...)` with optional `tts_choice`.
- Persist `selected_tts_choice` in readiness.
- Persist `selected_tts_choice` in audio-pack manifests/import metadata.
- Add a helper in `install_manager.py` that resolves a profile’s concrete TTS plan from `tts_choice` or `default_tts_choice`.
- Keep backward compatibility when `tts_choice` is absent.

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py -v
python -m pytest tldw_Server_API/tests/Setup/test_audio_readiness_store.py -v
python -m pytest tldw_Server_API/tests/Setup/test_audio_pack_service.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Setup/audio_bundle_catalog.py tldw_Server_API/app/core/Setup/audio_readiness_store.py tldw_Server_API/app/core/Setup/audio_pack_service.py tldw_Server_API/app/core/Setup/install_manager.py tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py tldw_Server_API/tests/Setup/test_audio_readiness_store.py tldw_Server_API/tests/Setup/test_audio_pack_service.py
git commit -m "feat(setup): persist curated tts choice for cpu audio bundles"
```

## Stage 4: Make Setup API, Verification, And UI Choice-Aware
**Goal:** Carry `tts_choice` through provision/verify requests, verification results, and the shared installer UI selector.
**Success Criteria:** The admin installer renders a TTS selector only for profiles with curated choices, submits `tts_choice`, and verification checks the selected provider path.
**Tests:** `tldw_Server_API/tests/Setup/test_audio_bundle_verification.py`, `tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py`, `apps/packages/ui/src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx`
**Status:** Complete

### Task 4: Add failing API, verification, and UI tests

**Files:**
- Modify: `tldw_Server_API/tests/Setup/test_audio_bundle_verification.py`
- Modify: `tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py`
- Modify: `apps/packages/ui/src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx`

**Step 1: Write the failing tests**

```python
def test_verify_audio_bundle_checks_selected_kitten_provider(mocker, tmp_path):
    result = install_manager.verify_audio_bundle("cpu_local", resource_profile="balanced", tts_choice="kitten_tts")
    assert result["selected_tts_choice"] == "kitten_tts"


def test_provision_audio_bundle_accepts_tts_choice(client, mocker):
    response = client.post(
        "/api/v1/setup/admin/audio/provision",
        json={"bundle_id": "cpu_local", "resource_profile": "balanced", "tts_choice": "kitten_tts"},
    )
    assert response.status_code in {200, 202}
```

```tsx
it("renders and submits curated tts choices for cpu_local balanced", async () => {
  // mock recommendations payload with profile.tts_choices and assert kitten_tts is posted
})
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_verification.py -v
python -m pytest tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py -v
cd apps/packages/ui && bunx vitest run src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx
```

Expected: FAIL because the setup API and UI do not carry `tts_choice` yet.

**Step 3: Write minimal implementation**

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/setup.py`
- Modify: `tldw_Server_API/app/core/Setup/install_manager.py`
- Modify: `apps/packages/ui/src/components/Option/Setup/hooks/useAudioInstaller.ts`
- Modify: `apps/packages/ui/src/components/Option/Setup/AudioInstallerPanel.tsx`

Implementation notes:
- Add optional `tts_choice` to provision and verify request models.
- Include profile-level `tts_choices` and `default_tts_choice` in the recommendation payload.
- Make verification/readiness results include `selected_tts_choice`.
- In the React hook, store `selectedTtsChoice` alongside bundle/profile.
- In the panel, render the selector only when the current profile exposes curated choices.

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_verification.py -v
python -m pytest tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py -v
cd apps/packages/ui && bunx vitest run src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/setup.py tldw_Server_API/app/core/Setup/install_manager.py apps/packages/ui/src/components/Option/Setup/hooks/useAudioInstaller.ts apps/packages/ui/src/components/Option/Setup/AudioInstallerPanel.tsx tldw_Server_API/tests/Setup/test_audio_bundle_verification.py tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py apps/packages/ui/src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx
git commit -m "feat(setup): add curated kitten_tts choice to audio installer"
```

## Stage 5: Verify The Slice End To End
**Goal:** Run the focused verification suite, update docs if needed, and leave the branch ready for execution or PR work.
**Success Criteria:** Focused backend and frontend tests pass, touched scope is Bandit-clean, and the plan reflects completion status.
**Tests:** Focused pytest + Vitest + Bandit on touched paths
**Status:** Complete

### Task 5: Run focused verification and update plan status

**Files:**
- Modify: `Docs/Plans/2026-03-19-kitten-tts-curated-bundle-parity-implementation-plan.md`

**Step 1: Run focused backend tests**

Run:
```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Audio/test_audio_speech_kittentts_integration.py \
  tldw_Server_API/tests/Audio/test_tts_provider_inference.py \
  tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py \
  tldw_Server_API/tests/Setup/test_audio_bundle_provisioning.py \
  tldw_Server_API/tests/Setup/test_audio_bundle_verification.py \
  tldw_Server_API/tests/Setup/test_audio_pack_service.py \
  tldw_Server_API/tests/Setup/test_audio_readiness_store.py \
  tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py -q
```

Expected: PASS.

**Step 2: Run focused frontend tests**

Run:
```bash
cd apps/packages/ui
bunx vitest run src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx
```

Expected: PASS.

**Step 3: Run safety checks**

Run:
```bash
git diff --check
source .venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/setup.py \
  tldw_Server_API/app/core/Setup/audio_bundle_catalog.py \
  tldw_Server_API/app/core/Setup/audio_readiness_store.py \
  tldw_Server_API/app/core/Setup/audio_pack_service.py \
  tldw_Server_API/app/core/Setup/install_manager.py \
  -f json -o /tmp/bandit_kitten_tts_curated_bundle.json
```

Expected: clean diff check and no new findings in touched code.

**Step 4: Mark plan complete**

Update this file so each stage status is `Complete` once the work lands.

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-19-kitten-tts-curated-bundle-parity-implementation-plan.md
git commit -m "docs(setup): mark kitten_tts curated bundle plan complete"
```
