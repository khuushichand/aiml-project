# KittenTTS And PocketTTS.cpp Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `kitten_tts` the universal fresh default TTS engine and `pocket_tts_cpp` the preferred ready-only fallback across backend selection, backend generation jobs, SDK defaults, and all fresh-profile UI entry points without overwriting existing saved settings.

**Architecture:** Apply the default-policy change in three layers: backend provider ordering and service fallbacks, fresh-profile UI storage/materialization fallbacks, and SDK constructor defaults. Keep PocketTTS.cpp readiness explicit so clone-dependent paths never become the unconditional first-run selection, and preserve all existing stored or explicit request-level overrides.

**Tech Stack:** FastAPI/Python, pytest, React/TypeScript, Vitest, local storage hooks, voice-assistant SDK.

---

## File Map

- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/Config_Files/tts_providers_config.yaml`
  Purpose: move effective default provider priority to `kitten_tts`, then `pocket_tts_cpp`.
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/outputs_service.py`
  Purpose: replace hardcoded Kokoro fallback model/voice with the new default-policy helper or equivalent normalized fallback resolution.
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/audiobook_jobs_worker.py`
  Purpose: align provider/model/voice fallback inference with the same default policy and PocketTTS readiness gate.
- Create or modify tests under: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/TTS/`
  Purpose: lock backend provider ordering and fallback normalization.
- Create or modify tests under: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/Audio/`
  Purpose: cover audiobook/output fallback behavior from service-entry paths.
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useVoiceChatStream.tsx`
  Purpose: change fresh voice-chat fallback defaults from browser/Kokoro to `tldw`/Kitten.
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx`
  Purpose: preserve saved overrides while resolving persona voice defaults to the new Kitten baseline.
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
  Purpose: align fresh Playground voice-chat defaults with the new policy.
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx`
  Purpose: align Speech Playground fresh defaults with the new policy.
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/TTS/TtsPlaygroundPage.tsx`
  Purpose: align standalone TTS Playground defaults and displayed placeholders with Kitten defaults.
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/TTS/TtsProviderPanel.tsx`
  Purpose: remove Kokoro placeholder/display fallbacks from the provider summary.
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/Playground/useMessageState.ts`
  Purpose: align shared message-playback storage fallbacks with the new policy.
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/Playground/Message.tsx`
  Purpose: align message audio replay fallback reads with the new policy.
- Modify as needed: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/hooks/useAudioTtsSettings.tsx`
  Purpose: align workspace helper materialization of fresh defaults if it still injects browser/Kokoro baselines.
- Create or modify tests under: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/__tests__/`
  Purpose: lock fresh-profile voice default resolution and saved-setting override behavior.
- Create or modify tests under: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/TTS/__tests__/`
  Purpose: lock standalone TTS Playground and provider panel defaults.
- Create or modify tests under: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/Playground/__tests__/`
  Purpose: lock shared message playback defaults.
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/voice-assistant-sdk/src/client/VoiceAssistantClient.ts`
  Purpose: switch SDK constructor defaults from Kokoro/`af_heart` to canonical Kitten provider/voice defaults.
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/voice-assistant-sdk/src/types/index.ts`
  Purpose: update inline default documentation so SDK types match runtime defaults.
- Create or modify tests under: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/voice-assistant-sdk/src/client/__tests__/`
  Purpose: lock SDK default config values.

### PocketTTS.cpp Readiness Contract

Implementation should treat PocketTTS.cpp as ready only when all are true:

- server/provider status reports `pocket_tts_cpp` enabled and usable
- required runtime assets exist for the provider
- the active or stored voice is concrete and usable, not empty and not `clone_required`

If any of those fail, the effective default stays on KittenTTS.

### Canonical Default Values

Use one canonical Kitten baseline everywhere fresh defaults are materialized:

- `ttsProvider = "tldw"` for UI storage-backed flows
- `tldwTtsModel = "KittenML/kitten-tts-nano-0.8"` unless code inspection finds a stronger existing canonical Kitten default in the repo
- `tldwTtsVoice = <repo-approved Kitten fallback voice>`
- SDK `ttsProvider = "kitten_tts"`
- SDK `ttsVoice = <same repo-approved Kitten fallback voice or SDK-specific mapped equivalent>`

Before implementation, confirm the exact Kitten fallback voice already used or expected by backend voice catalogs so tests do not bake in an invented voice name.

### Stage 1: Lock Backend Default Policy

**Goal:** Add failing backend tests for provider ordering and non-chat generation fallback behavior before changing service code.
**Success Criteria:** Tests fail against current Kokoro/OpenAI-first behavior and document the expected `kitten_tts` then `pocket_tts_cpp` default order plus explicit-override preservation.
**Tests:** `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS/test_tts_default_policy.py tldw_Server_API/tests/Audio/test_tts_generation_default_policy.py -q`
**Status:** Not Started

**Files:**
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/TTS/test_tts_default_policy.py`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/tests/Audio/test_tts_generation_default_policy.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/Config_Files/tts_providers_config.yaml`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/outputs_service.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/services/audiobook_jobs_worker.py`

- [ ] **Step 1: Write the failing backend policy tests**

Add tests that assert:
- provider priority starts with `kitten_tts`, then `pocket_tts_cpp`
- output-generation fallback no longer resolves to `kokoro` / `af_heart` when request and template settings are empty
- audiobook worker fallback no longer resolves to `kokoro` / `af_heart` when explicit settings are absent
- explicit request/template/provider values still override defaults

- [ ] **Step 2: Run the backend tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS/test_tts_default_policy.py tldw_Server_API/tests/Audio/test_tts_generation_default_policy.py -q`
Expected: FAIL on old Kokoro/OpenAI-first ordering and legacy fallback values.

- [ ] **Step 3: Implement minimal backend default-policy changes**

Change provider ordering in `tts_providers_config.yaml`, then patch service fallback resolution so it uses the new Kitten-first policy and only promotes PocketTTS.cpp when readiness prerequisites are satisfied.

- [ ] **Step 4: Run the backend tests to verify they pass**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS/test_tts_default_policy.py tldw_Server_API/tests/Audio/test_tts_generation_default_policy.py -q`
Expected: PASS

- [ ] **Step 5: Commit the backend policy slice**

```bash
git add tldw_Server_API/Config_Files/tts_providers_config.yaml \
  tldw_Server_API/app/services/outputs_service.py \
  tldw_Server_API/app/services/audiobook_jobs_worker.py \
  tldw_Server_API/tests/TTS/test_tts_default_policy.py \
  tldw_Server_API/tests/Audio/test_tts_generation_default_policy.py
git commit -m "feat: switch backend tts defaults to kitten and pocketcpp"
```

### Stage 2: Lock Fresh UI Default Materialization

**Goal:** Add failing UI tests for all fresh-profile TTS entry points before changing any storage-backed defaults.
**Success Criteria:** New tests show fresh-profile flows still resolve to browser/Kokoro today and define the target Kitten-based defaults while preserving saved overrides.
**Tests:** `bunx vitest run apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.defaults.test.tsx apps/packages/ui/src/components/Option/TTS/__tests__/TtsPlaygroundPage.defaults.test.tsx apps/packages/ui/src/components/Common/Playground/__tests__/message-tts-defaults.test.tsx`
**Status:** Not Started

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.defaults.test.tsx`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/TTS/__tests__/TtsPlaygroundPage.defaults.test.tsx`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/Playground/__tests__/message-tts-defaults.test.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useVoiceChatStream.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/TTS/TtsPlaygroundPage.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/TTS/TtsProviderPanel.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/Playground/useMessageState.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/Playground/Message.tsx`
- Modify as needed: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/hooks/useAudioTtsSettings.tsx`

- [ ] **Step 1: Write the failing fresh-profile UI tests**

Add tests that assert:
- fresh voice-chat defaults resolve to `ttsProvider="tldw"` and the canonical Kitten model/voice
- fresh standalone TTS Playground defaults resolve to the same Kitten baseline
- shared message playback reads the new fallback values on a clean profile
- existing saved values in storage still win and are not migrated

- [ ] **Step 2: Run the UI tests to verify they fail**

Run: `bunx vitest run apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.defaults.test.tsx apps/packages/ui/src/components/Option/TTS/__tests__/TtsPlaygroundPage.defaults.test.tsx apps/packages/ui/src/components/Common/Playground/__tests__/message-tts-defaults.test.tsx`
Expected: FAIL on current browser/Kokoro defaults.

- [ ] **Step 3: Implement minimal UI default changes**

Patch all storage/materialization fallbacks to the canonical Kitten baseline, update visible placeholder text that still implies Kokoro defaults, and leave all persisted values untouched.

- [ ] **Step 4: Run the UI tests to verify they pass**

Run: `bunx vitest run apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.defaults.test.tsx apps/packages/ui/src/components/Option/TTS/__tests__/TtsPlaygroundPage.defaults.test.tsx apps/packages/ui/src/components/Common/Playground/__tests__/message-tts-defaults.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit the UI defaults slice**

```bash
git add apps/packages/ui/src/hooks/useVoiceChatStream.tsx \
  apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Speech/SpeechPlaygroundPage.tsx \
  apps/packages/ui/src/components/Option/TTS/TtsPlaygroundPage.tsx \
  apps/packages/ui/src/components/Option/TTS/TtsProviderPanel.tsx \
  apps/packages/ui/src/components/Common/Playground/useMessageState.ts \
  apps/packages/ui/src/components/Common/Playground/Message.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/hooks/useAudioTtsSettings.tsx \
  apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx \
  apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.defaults.test.tsx \
  apps/packages/ui/src/components/Option/TTS/__tests__/TtsPlaygroundPage.defaults.test.tsx \
  apps/packages/ui/src/components/Common/Playground/__tests__/message-tts-defaults.test.tsx
git commit -m "feat: switch fresh ui tts defaults to kitten"
```

### Stage 3: Align SDK Runtime Defaults And Type Docs

**Goal:** Add failing SDK tests for default config values, then move runtime and documented defaults to Kitten.
**Success Criteria:** SDK constructor defaults no longer resolve to Kokoro/`af_heart`, and public type docs match runtime behavior.
**Tests:** `bunx vitest run apps/packages/voice-assistant-sdk/src/client/__tests__/VoiceAssistantClient.defaults.test.ts`
**Status:** Not Started

**Files:**
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/voice-assistant-sdk/src/client/__tests__/VoiceAssistantClient.defaults.test.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/voice-assistant-sdk/src/client/VoiceAssistantClient.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/voice-assistant-sdk/src/types/index.ts`

- [ ] **Step 1: Write the failing SDK default test**

Add a focused constructor test asserting the default config exposes `ttsProvider="kitten_tts"` and the canonical Kitten fallback voice.

- [ ] **Step 2: Run the SDK test to verify it fails**

Run: `bunx vitest run apps/packages/voice-assistant-sdk/src/client/__tests__/VoiceAssistantClient.defaults.test.ts`
Expected: FAIL because the SDK still defaults to Kokoro/`af_heart`.

- [ ] **Step 3: Implement the minimal SDK default changes**

Patch runtime defaults in `VoiceAssistantClient.ts` and update any inline default documentation in `types/index.ts`.

- [ ] **Step 4: Run the SDK test to verify it passes**

Run: `bunx vitest run apps/packages/voice-assistant-sdk/src/client/__tests__/VoiceAssistantClient.defaults.test.ts`
Expected: PASS

- [ ] **Step 5: Commit the SDK slice**

```bash
git add apps/packages/voice-assistant-sdk/src/client/VoiceAssistantClient.ts \
  apps/packages/voice-assistant-sdk/src/types/index.ts \
  apps/packages/voice-assistant-sdk/src/client/__tests__/VoiceAssistantClient.defaults.test.ts
git commit -m "feat: align sdk tts defaults with kitten"
```

### Stage 4: Cross-Surface Verification And Live Sanity Check

**Goal:** Verify the default-policy change end-to-end across backend, UI, and SDK surfaces without regressing voice availability logic or explicit overrides.
**Success Criteria:** Targeted automated tests pass, Bandit is clean on touched backend code, and a fresh-profile sanity check confirms Kitten-backed defaults in the browser.
**Tests:** Combined targeted pytest and Vitest suites plus Bandit on touched backend files.
**Status:** Not Started

**Files:**
- Verify touched backend files and tests from Stages 1-3
- Verify touched UI files and tests from Stages 2-3
- Verify spec and plan consistency if implementation scope changed during execution

- [ ] **Step 1: Run the full targeted backend verification**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/TTS/test_tts_default_policy.py tldw_Server_API/tests/Audio/test_tts_generation_default_policy.py tldw_Server_API/tests/TTS/test_tts_adapters.py tldw_Server_API/tests/TTS_NEW/integration/test_kokoro_runtime_health_envelope.py -q`
Expected: PASS

- [ ] **Step 2: Run the full targeted UI and SDK verification**

Run: `bunx vitest run apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.defaults.test.tsx apps/packages/ui/src/components/Option/TTS/__tests__/TtsPlaygroundPage.defaults.test.tsx apps/packages/ui/src/components/Common/Playground/__tests__/message-tts-defaults.test.tsx apps/packages/voice-assistant-sdk/src/client/__tests__/VoiceAssistantClient.defaults.test.ts apps/packages/ui/src/components/Option/Playground/__tests__/voice-conversation.cross-surface.contract.test.ts apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.voice-visibility.integration.test.tsx`
Expected: PASS

- [ ] **Step 3: Run Bandit on touched backend application code**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/outputs_service.py tldw_Server_API/app/services/audiobook_jobs_worker.py -f json -o /tmp/bandit_kitten_pocketcpp_defaults.json`
Expected: JSON report written with no new findings in touched code.

- [ ] **Step 4: Perform a fresh-profile browser sanity check**

Run a fresh-storage browser verification against the live UI and confirm:
- default provider path is server-backed, not browser
- the resolved model/voice are Kitten defaults
- existing saved overrides still take precedence when manually seeded

- [ ] **Step 5: Commit final verification-only cleanup if needed**

```bash
git add -A
git commit -m "test: verify kitten and pocketcpp default policy"
```

## Notes For Execution

- Do not migrate or rewrite existing persisted user settings.
- Do not make PocketTTS.cpp the unconditional first-run selection.
- Reuse one canonical Kitten fallback voice across backend, UI, and SDK wherever the code paths allow.
- If implementation uncovers a different existing canonical Kitten voice in the server voice catalog, update tests and constants to match that source of truth rather than inventing a new name.
- If a touched file already has unrelated dirty edits, read carefully and integrate without reverting user changes.
