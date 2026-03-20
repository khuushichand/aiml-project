# Persona Turn Detection Defaults Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist persona turn-detection defaults into `voice_defaults`, make new Live sessions start from those saved values, and add an explicit `Save current settings as defaults` action without hot-overriding connected sessions.

**Architecture:** Extend backend and UI persona defaults with exact VAD fields, split the route into `savedPersonaVoiceDefaults` and `liveSessionVoiceDefaultsBaseline`, and reuse one shared turn-detection controls component in both Profiles and Live Session. The Live controller still owns session-local edits; explicit save merges them back into the persona profile.

**Tech Stack:** FastAPI, Pydantic, SQLite profile storage, React, TypeScript, Ant Design, Vitest, React Testing Library.

---

### Task 1: Red-Test Persona Profile VAD Default Persistence

**Files:**
- Modify: `tldw_Server_API/tests/Persona/test_persona_profiles_api.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/persona.py`

**Step 1: Write the failing test**

Extend the persona profile voice-defaults test with the new fields:

```python
assert payload["voice_defaults"]["auto_commit_enabled"] is True
assert payload["voice_defaults"]["vad_threshold"] == 0.35
assert payload["voice_defaults"]["min_silence_ms"] == 150
assert payload["voice_defaults"]["turn_stop_secs"] == 0.1
assert payload["voice_defaults"]["min_utterance_secs"] == 0.25
```

Add one more test for invalid values:

```python
def test_persona_profile_voice_defaults_clamps_turn_detection_values(...):
    ...
    assert payload["voice_defaults"]["vad_threshold"] == 1.0
    assert payload["voice_defaults"]["min_silence_ms"] == 50
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q -k "voice_defaults"
```

Expected: failures because the schema does not yet include or normalize the new
turn-detection fields.

**Step 3: Write minimal implementation**

In `tldw_Server_API/app/api/v1/schemas/persona.py`:

- extend `PersonaVoiceDefaults` with:
  - `auto_commit_enabled`
  - `vad_threshold`
  - `min_silence_ms`
  - `turn_stop_secs`
  - `min_utterance_secs`
- add validators that keep these ranges aligned with the live runtime:
  - `vad_threshold`: `0.0..1.0`
  - `min_silence_ms`: `50..10000`
  - `turn_stop_secs`: `0.05..10.0`
  - `min_utterance_secs`: `0.0..10.0`

Keep fields nullable so absent persona settings still fall back cleanly.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q -k "voice_defaults"
```

Expected: persona profile VAD default round-trip coverage passes.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/tests/Persona/test_persona_profiles_api.py
git commit -m "feat: persist persona turn detection defaults"
```

### Task 2: Red-Test Resolved Persona Voice Defaults For VAD

**Files:**
- Modify: `apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx`
- Modify: `apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx`

**Step 1: Write the failing tests**

Add resolver tests for:

```tsx
it("prefers explicit persona turn detection defaults")
it("fills missing persona turn detection defaults from the balanced baseline")
```

Assert:

- explicit persona VAD values appear in the resolved output
- missing persona VAD values resolve to the balanced baseline
- existing STT/TTS fallback behavior still holds

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx
```

Expected: failures because the resolver does not yet return VAD defaults.

**Step 3: Write minimal implementation**

In `apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx`:

- extend `PersonaVoiceDefaults` and `ResolvedPersonaVoiceDefaults` with the new
  turn-detection fields
- add a shared balanced baseline constant for:
  - `autoCommitEnabled: true`
  - `vadThreshold: 0.5`
  - `minSilenceMs: 250`
  - `turnStopSecs: 0.2`
  - `minUtteranceSecs: 0.4`
- resolve turn detection from:
  1. explicit persona defaults
  2. balanced baseline

Keep preset derivation out of this hook.

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx
```

Expected: resolver tests pass with the new fields.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx
git commit -m "feat: resolve persona turn detection defaults"
```

### Task 3: Red-Test Shared Turn Detection Controls In Profiles

**Files:**
- Create: `apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionControls.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx`

**Step 1: Write the failing tests**

Extend `AssistantDefaultsPanel.test.tsx` with:

```tsx
it("loads and saves turn detection defaults from the persona profile")
it("shows custom as the saved preset when advanced values diverge")
```

Add assertions for:

- `Auto-commit`
- preset buttons
- advanced drawer values
- saved payload containing:
  - `auto_commit_enabled`
  - `vad_threshold`
  - `min_silence_ms`
  - `turn_stop_secs`
  - `min_utterance_secs`

In `LiveSessionPanel.test.tsx`, keep one small render assertion proving the Live
card still shows the same turn-detection controls after extraction.

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx
```

Expected: failures because the saved-defaults panel does not yet expose the new
controls.

**Step 3: Write minimal implementation**

Create `apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionControls.tsx`
as a shared presentational control block.

In `AssistantDefaultsPanel.tsx`:

- extend form state with saved turn-detection fields
- add helpers to build/parse the saved defaults payload
- render the shared turn-detection controls with copy for saved defaults
- keep save behavior under the existing `Save assistant defaults` button

In `AssistantVoiceCard.tsx`:

- switch to the shared controls component while preserving current session-only
  helper text and disabled rules

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx
```

Expected: Assistant Defaults and Live Session tests pass with shared controls.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionControls.tsx apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx
git commit -m "feat: add saved persona turn detection defaults controls"
```

### Task 4: Red-Test Route Baseline Snapshot And Live Save CTA

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing tests**

Add route tests for:

```tsx
it("initializes live turn detection from saved persona defaults on connect")
it("does not hot-reset the connected live session when assistant defaults are saved")
it("shows save current settings as defaults only when explicit saved turn detection defaults are absent or different")
it("saves merged voice defaults from the live session without dropping saved non-vad fields")
it("uses updated saved turn detection defaults after reconnect")
```

Assert:

- initial `voice_config` reflects saved persona VAD defaults
- the Live save CTA appears only on explicit divergence or absent saved VAD fields
- the PATCH body includes merged `voice_defaults`, not only VAD fields
- saving defaults does not force an extra live reset while still connected
- reconnect picks up the newly saved VAD defaults

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "saved persona defaults on connect|does not hot-reset|save current settings as defaults|merged voice defaults|after reconnect"
```

Expected: failures because the route still uses one shared defaults object and
the live controller still resets to hardcoded balanced values.

**Step 3: Write minimal implementation**

In `apps/packages/ui/src/routes/sidepanel-persona.tsx`:

- split voice defaults into:
  - `savedPersonaVoiceDefaults`
  - `liveSessionVoiceDefaultsBaseline`
- capture the live baseline from resolved saved defaults on connect/reconnect
- add a helper that compares current live tuning against raw saved VAD fields
- add `Save current settings as defaults` to the Live card wiring
- merge saved `voice_defaults` with live VAD state before sending PATCH
- update only the saved profile state from the response

In `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`:

- initialize VAD state from resolved defaults instead of hardcoded balanced
- reset to the passed-in baseline on persona/session reset and disconnect
- expose the current VAD state cleanly for the route’s save helper

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "saved persona defaults on connect|does not hot-reset|save current settings as defaults|merged voice defaults|after reconnect"
```

Expected: route integration tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: seed live voice from saved persona turn detection defaults"
```

### Task 5: Verify The Full Slice

**Files:**
- Verify touched backend and UI files from Tasks 1-4

**Step 1: Run backend profile verification**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Persona/test_persona_profiles_api.py -q
```

Expected: persona profile persistence coverage stays green.

**Step 2: Run focused UI hook and component verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx
```

Expected: resolver, live controller, Profiles, and Live Session tests all pass.

**Step 3: Run broader Persona Garden regression verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx src/components/PersonaGarden/__tests__/ExemplarImportPanel.test.tsx src/components/PersonaGarden/__tests__/VoiceExamplesPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx src/routes/__tests__/sidepanel-persona.blocker.test.tsx src/routes/__tests__/sidepanel-persona.command-handoff.test.tsx src/routes/__tests__/sidepanel-persona-locale-keys.test.ts
```

Expected: Persona Garden route and panel regressions remain green.

**Step 4: Run backend security and sanity checks**

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/schemas/persona.py -f json -o /tmp/bandit_persona_turn_detection_defaults.json
git diff --check
```

Expected: no new Bandit findings in touched backend code and no diff hygiene
issues.

**Step 5: Final commit**

```bash
git add Docs/Plans/2026-03-13-persona-turn-detection-defaults-design.md Docs/Plans/2026-03-13-persona-turn-detection-defaults-implementation-plan.md tldw_Server_API/app/api/v1/schemas/persona.py tldw_Server_API/tests/Persona/test_persona_profiles_api.py apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionControls.tsx apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: persist persona turn detection defaults"
```
