# Admin Audio Installer Shared UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose the existing setup audio bundle installer through shared React UI in both the extension/options UI and the Next.js WebUI, while tightening access control for shared UI-triggered installs and expanding curated bundle coverage for major local speech paths.

**Architecture:** Keep the existing setup audio installer backend and install manager, add an admin-oriented access path that remains usable after initial setup, expand the curated bundle catalog conservatively for Apple Silicon and NVIDIA local speech stacks, and build one shared `AudioInstallerPanel` in `apps/packages/ui` mounted by both hosts. Keep V1 limited to curated bundles only.

**Tech Stack:** FastAPI, existing setup/install manager modules, Pydantic, React, shared `apps/packages/ui` component library, Vitest, pytest.

---

### Task 1: Lock down shared audio installer access semantics

**Files:**
- Modify: `tldw_Server_API/app/api/v1/API_Deps/setup_deps.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/setup.py`
- Test: `tldw_Server_API/tests/Setup/test_setup_access_deps.py`
- Test: `tldw_Server_API/tests/Setup/test_setup_audio_installer_access_api.py`

**Step 1: Write the failing test**

```python
def test_remote_audio_recommendations_require_admin_when_shared_installer_enabled(client, auth_headers_for_user):
    response = client.get("/api/v1/setup/audio/recommendations", headers=auth_headers_for_user)
    assert response.status_code == 403


def test_remote_audio_recommendations_allow_admin(client, auth_headers_for_admin):
    response = client.get("/api/v1/setup/audio/recommendations", headers=auth_headers_for_admin)
    assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_setup_access_deps.py tldw_Server_API/tests/Setup/test_setup_audio_installer_access_api.py -q
```

Expected: FAIL because the setup audio endpoints still use the current local-setup guard semantics.

**Step 3: Write minimal implementation**

Add a dedicated dependency for shared audio installer access that:

- requires authenticated admin/server-admin for shared UI requests
- does not rely on loopback bypass
- can coexist with the current legacy setup guard for the static setup flow

Wire audio recommendation / provision / verify / install-status to the appropriate admin-safe dependency used by the shared UI path.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_setup_access_deps.py tldw_Server_API/tests/Setup/test_setup_audio_installer_access_api.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/API_Deps/setup_deps.py tldw_Server_API/app/api/v1/endpoints/setup.py tldw_Server_API/tests/Setup/test_setup_access_deps.py tldw_Server_API/tests/Setup/test_setup_audio_installer_access_api.py
git commit -m "feat: add admin access guard for shared audio installer"
```

### Task 2: Make audio installer endpoints usable after setup completion

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/setup.py`
- Test: `tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py`

**Step 1: Write the failing test**

```python
def test_audio_recommendations_still_available_after_setup_completed(client, admin_headers, mocker):
    mocker.patch("tldw_Server_API.app.core.Setup.setup_manager.get_status_snapshot", return_value={
        "enabled": True,
        "needs_setup": False,
        "completed": True,
    })
    response = client.get("/api/v1/setup/audio/recommendations", headers=admin_headers)
    assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py -q
```

Expected: FAIL if endpoint availability still assumes first-run setup state too broadly.

**Step 3: Write minimal implementation**

Adjust the audio installer endpoint availability rules so:

- recommendation / provision / verify / install-status remain available to admin users after setup completion
- setup config mutation and setup-complete endpoints retain their existing first-run lifecycle rules

Keep failure behavior explicit when the installer is globally disabled.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/setup.py tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py
git commit -m "feat: keep audio installer available after setup completion"
```

### Task 3: Expand curated Apple Silicon and NVIDIA bundle profiles

**Files:**
- Modify: `tldw_Server_API/app/core/Setup/audio_bundle_catalog.py`
- Test: `tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py`

**Step 1: Write the failing test**

```python
def test_apple_silicon_balanced_profile_prefers_parakeet_mlx():
    catalog = get_audio_bundle_catalog()
    profile = catalog.bundle_by_id("apple_silicon_local").profile_by_id("balanced")
    assert profile.stt_plan == [{"engine": "nemo_parakeet_mlx", "models": []}]


def test_nvidia_balanced_profile_uses_parakeet_path():
    catalog = get_audio_bundle_catalog()
    profile = catalog.bundle_by_id("nvidia_local").profile_by_id("balanced")
    assert profile.stt_plan[0]["engine"] in {"nemo_parakeet_standard", "nemo_parakeet_onnx"}
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py -q
```

Expected: FAIL because bundles still point only at `faster_whisper`.

**Step 3: Write minimal implementation**

Update curated bundle resource profiles conservatively:

- Apple Silicon:
  - `light` keeps `faster_whisper + kokoro`
  - `balanced` / `performance` move to `nemo_parakeet_mlx + kokoro`
- NVIDIA:
  - `light` keeps `faster_whisper + kokoro`
  - `balanced` uses a Parakeet path plus `kokoro`
  - `performance` uses a stronger Parakeet path and optionally richer TTS (`dia` or `higgs`) only if verification/remediation can support it

Do not add `qwen2_audio`, `qwen3-asr`, `vibevoice`, or cloud TTS providers to curated bundles.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Setup/audio_bundle_catalog.py tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py
git commit -m "feat: expand curated audio bundle profiles"
```

### Task 4: Make verification profile-aware for expanded curated bundles

**Files:**
- Modify: `tldw_Server_API/app/core/Setup/install_manager.py`
- Modify: `tldw_Server_API/app/core/Setup/audio_bundle_catalog.py`
- Test: `tldw_Server_API/tests/Setup/test_audio_bundle_verification.py`

**Step 1: Write the failing test**

```python
def test_verify_audio_bundle_uses_selected_profile_targets(mocker):
    result = verify_audio_bundle("apple_silicon_local", resource_profile="balanced")
    assert result["bundle_id"] == "apple_silicon_local"
    assert result["resource_profile"] == "balanced"
    assert "stt_default" in result["targets_checked"]
```

Add a second test that asserts remediation references the expected selected engine when the chosen profile requires a missing dependency.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_verification.py -q
```

Expected: FAIL because verification/remediation is still too generic for expanded profiles.

**Step 3: Write minimal implementation**

Update bundle verification so it:

- carries `bundle_id` and `resource_profile` through the result
- validates the profile’s expected default STT/TTS path
- emits remediation tied to the selected profile rather than only generic readiness

Keep the verification API surface stable where possible.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Setup/test_audio_bundle_verification.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Setup/install_manager.py tldw_Server_API/app/core/Setup/audio_bundle_catalog.py tldw_Server_API/tests/Setup/test_audio_bundle_verification.py
git commit -m "feat: make audio bundle verification profile-aware"
```

### Task 5: Add a shared React audio installer panel

**Files:**
- Create: `apps/packages/ui/src/components/Option/Setup/AudioInstallerPanel.tsx`
- Create: `apps/packages/ui/src/components/Option/Setup/hooks/useAudioInstaller.ts`
- Test: `apps/packages/ui/src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx`

**Step 1: Write the failing test**

```tsx
it("loads and shows the recommended audio bundle", async () => {
  render(<AudioInstallerPanel />)

  expect(await screen.findByText("Recommended audio bundle")).toBeInTheDocument()
  expect(screen.getByText("Apple Silicon Local")).toBeInTheDocument()
})
```

Add tests for:

- provision action
- install-status polling
- verify action
- forbidden/unavailable state

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx
```

Expected: FAIL because the component and hook do not exist.

**Step 3: Write minimal implementation**

Implement a shared panel that:

- fetches `/api/v1/setup/audio/recommendations`
- renders machine profile and recommended bundle
- allows resource profile selection
- calls `/api/v1/setup/audio/provision`
- polls `/api/v1/setup/install-status` while active
- calls `/api/v1/setup/audio/verify`
- renders remediation items and readiness output

Keep all installer logic inside the shared hook/component.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Setup/AudioInstallerPanel.tsx apps/packages/ui/src/components/Option/Setup/hooks/useAudioInstaller.ts apps/packages/ui/src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx
git commit -m "feat: add shared admin audio installer panel"
```

### Task 6: Mount the shared installer in the extension/options UI

**Files:**
- Modify: `apps/packages/ui/src/routes/option-setup.tsx`
- Modify: one relevant extension/options admin or setup wrapper component discovered during implementation
- Test: `apps/packages/ui/src/routes/__tests__/option-setup-audio-installer.test.tsx`

**Step 1: Write the failing test**

```tsx
it("renders the shared audio installer in the options setup/admin surface", async () => {
  render(<OptionSetup />)
  expect(await screen.findByText("Recommended audio bundle")).toBeInTheDocument()
})
```

Add a second test that verifies forbidden responses collapse to an admin-only/unavailable message.

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/option-setup-audio-installer.test.tsx
```

Expected: FAIL because the route does not mount the installer.

**Step 3: Write minimal implementation**

Mount the shared panel in the extension/options admin/setup surface with:

- clear heading that this affects the connected server
- thin host wrapper only

Do not duplicate installer logic in the route.

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/option-setup-audio-installer.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/option-setup.tsx apps/packages/ui/src/routes/__tests__/option-setup-audio-installer.test.tsx
git commit -m "feat: surface audio installer in extension setup"
```

### Task 7: Mount the shared installer in the Next.js WebUI

**Files:**
- Modify: exact Next.js admin/settings page found during implementation
- Test: exact Next.js page/component test covering the installer mount

**Step 1: Write the failing test**

Write a focused render test proving the Next.js admin/settings surface mounts the shared `AudioInstallerPanel`.

**Step 2: Run test to verify it fails**

Run the relevant Vitest or Next.js component test command for that page.

Expected: FAIL because the installer is not mounted.

**Step 3: Write minimal implementation**

Mount the same shared panel in the WebUI admin/configuration surface with:

- host-specific page framing only
- no installer logic divergence from the extension/options surface

**Step 4: Run test to verify it passes**

Run the focused Next.js UI test again.

Expected: PASS.

**Step 5: Commit**

```bash
git add <nextjs_host_files> <nextjs_test_files>
git commit -m "feat: surface audio installer in webui admin"
```

### Task 8: Run focused verification, broader regression, and documentation checks

**Files:**
- Verify only; no required code changes unless regressions are found

**Step 1: Run focused backend tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Setup/test_setup_access_deps.py \
  tldw_Server_API/tests/Setup/test_setup_audio_installer_access_api.py \
  tldw_Server_API/tests/Setup/test_setup_audio_installer_lifecycle_api.py \
  tldw_Server_API/tests/Setup/test_audio_bundle_catalog.py \
  tldw_Server_API/tests/Setup/test_audio_bundle_verification.py -q
```

Expected: PASS.

**Step 2: Run focused frontend tests**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/Setup/__tests__/AudioInstallerPanel.test.tsx \
  apps/packages/ui/src/routes/__tests__/option-setup-audio-installer.test.tsx \
  <nextjs_installer_test_files>
```

Expected: PASS.

**Step 3: Run broader regression**

Run the existing relevant setup/audio/frontend sweeps discovered during implementation so the new installer does not break setup or speech UI behavior.

**Step 4: Run Bandit on touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/API_Deps/setup_deps.py \
  tldw_Server_API/app/api/v1/endpoints/setup.py \
  tldw_Server_API/app/core/Setup \
  -f json -o /tmp/bandit_admin_audio_installer.json
```

Expected: no new findings in touched code.

**Step 5: Run diff sanity check**

Run:

```bash
git diff --check
```

Expected: no whitespace or patch-format issues.

**Step 6: Commit final verification or fixes**

If verification required fixes, commit them with a focused message such as:

```bash
git add <fixed_files>
git commit -m "fix: stabilize shared audio installer integration"
```
