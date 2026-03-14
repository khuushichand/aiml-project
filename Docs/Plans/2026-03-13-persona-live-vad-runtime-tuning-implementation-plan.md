# Persona Live VAD Runtime Tuning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add session-only turn-detection controls to Persona Garden Live Session, with an auto-commit toggle, presets, an advanced drawer, and immediate websocket runtime updates.

**Architecture:** Keep tuning state in `usePersonaLiveVoiceController`, reuse the existing persona websocket `voice_config` contract, and expose the controls through `AssistantVoiceCard` without changing persona profile persistence. The route remains a thin pass-through layer and verification stays focused on hook, card, and route behavior.

**Tech Stack:** React, TypeScript, Ant Design, Vitest, React Testing Library, existing persona websocket runtime.

---

### Task 1: Red-Test Hook Runtime Tuning State

**Files:**
- Modify: `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx`
- Modify: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`

**Step 1: Write the failing tests**

Add hook tests for:

```tsx
it("initializes session turn detection to the balanced preset")
it("marks the preset as custom after an advanced runtime edit")
it("resets session turn detection tuning on persona switch")
```

Assert:

- baseline values match `Balanced`
- advanced changes produce `preset: "custom"`
- persona/session reset restores balanced values

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx -t "balanced preset|custom after an advanced runtime edit|resets session turn detection tuning"
```

Expected: failures because the hook does not yet track session VAD runtime state.

**Step 3: Write minimal implementation**

In `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`:

- add a session-only runtime tuning object:
  - `autoCommitEnabled`
  - `vadPreset`
  - `vadThreshold`
  - `minSilenceMs`
  - `turnStopSecs`
  - `minUtteranceSecs`
- add preset constants for `Conservative`, `Balanced`, and `Fast`
- add a derived preset matcher that returns `custom` when values diverge
- reset this tuning only on persona/session identity changes, not on ordinary runtime edits

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx -t "balanced preset|custom after an advanced runtime edit|resets session turn detection tuning"
```

Expected: new hook tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
git commit -m "feat: add session vad tuning state to persona live voice"
```

### Task 2: Red-Test `voice_config` Runtime Updates

**Files:**
- Modify: `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx`
- Modify: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`

**Step 1: Write the failing tests**

Add hook tests for:

```tsx
it("sends updated voice_config when the preset changes while connected")
it("sends enable_vad false when auto-commit is turned off")
it("sends updated advanced values when turn detection tuning changes")
```

Assert the websocket payload includes:

- `stt.enable_vad`
- `stt.vad_threshold`
- `stt.min_silence_ms`
- `stt.turn_stop_secs`
- `stt.min_utterance_secs`

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx -t "sends updated voice_config|enable_vad false|updated advanced values"
```

Expected: failures because the hook currently always sends `enable_vad: true` and has no tunable values.

**Step 3: Write minimal implementation**

In `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`:

- extend the existing `voice_config` effect to include runtime VAD fields
- send `enable_vad` from session tuning state
- add setter callbacks:
  - `setAutoCommitEnabled`
  - `setVadPreset`
  - `setVadThreshold`
  - `setMinSilenceMs`
  - `setTurnStopSecs`
  - `setMinUtteranceSecs`
- keep runtime tuning out of the broad reset effect that currently clears the live turn

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx -t "sends updated voice_config|enable_vad false|updated advanced values"
```

Expected: websocket payload assertions pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx
git commit -m "feat: send persona live vad tuning over voice config"
```

### Task 3: Red-Test Live Card Turn Detection UI

**Files:**
- Modify: `apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx`
- Modify: `apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing tests**

Add component tests for:

```tsx
it("renders the turn detection section with auto-commit and presets")
it("shows the advanced drawer and current runtime values")
it("disables advanced tuning while disconnected or when manual mode is required")
it("shows custom as the active preset when advanced values diverge")
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx -t "turn detection|advanced drawer|custom as the active preset"
```

Expected: failures because the card does not yet render runtime tuning controls.

**Step 3: Write minimal implementation**

In `apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx`:

- add a `Turn detection` block below the session-only toggles
- add:
  - `Auto-commit (session only)` toggle
  - preset selector for `Conservative`, `Balanced`, `Fast`, and derived `Custom`
  - `Advanced` disclosure
  - advanced inputs for:
    - `Speech threshold`
    - `Silence before commit`
    - `Minimum utterance`
    - `Turn tail`
- add honest helper copy for:
  - session-only scope
  - disconnected state
  - manual-mode-unavailable state
  - immediate live-application caveat

In `apps/packages/ui/src/routes/sidepanel-persona.tsx`:

- pass the new hook state and setter callbacks into `AssistantVoiceCard`

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx -t "turn detection|advanced drawer|custom as the active preset"
```

Expected: new Live Session card tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx
git commit -m "feat: add persona live turn detection controls"
```

### Task 4: Red-Test Route Integration And Session Reset

**Files:**
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`

**Step 1: Write the failing tests**

Add route tests for:

```tsx
it("sends a fresh voice_config when the live turn detection preset changes")
it("sends a fresh voice_config when auto-commit is turned off")
it("resets turn detection tuning to the session baseline after reconnect")
```

Inspect the websocket payloads already sent by the route and assert the updated
STT runtime fields are present.

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "turn detection preset changes|auto-commit is turned off|session baseline after reconnect"
```

Expected: failures until the new card controls are wired through the route and the hook reset behavior is correct.

**Step 3: Write minimal implementation**

Adjust the route and hook so:

- connected tuning changes immediately resend `voice_config`
- disconnected controls remain disabled and do not fake runtime application
- reconnect or persona/session reset restores the balanced session baseline

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx -t "turn detection preset changes|auto-commit is turned off|session baseline after reconnect"
```

Expected: route integration tests pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx
git commit -m "feat: wire session live vad tuning into persona route"
```

### Task 5: Verify The Slice

**Files:**
- Verify touched hook, card, route, and docs from Tasks 1-4

**Step 1: Run focused hook and Live Session verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx
```

Expected: focused runtime tuning coverage passes.

**Step 2: Run broader Persona Garden regression coverage**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/PersonaGarden/__tests__/CommandsPanel.test.tsx src/components/PersonaGarden/__tests__/ConnectionsPanel.test.tsx src/components/PersonaGarden/__tests__/PersonaGardenPanels.i18n.test.tsx src/components/PersonaGarden/__tests__/ExemplarImportPanel.test.tsx src/components/PersonaGarden/__tests__/VoiceExamplesPanel.test.tsx src/components/PersonaGarden/__tests__/TestLabPanel.test.tsx src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx src/routes/__tests__/sidepanel-persona.blocker.test.tsx src/routes/__tests__/sidepanel-persona.command-handoff.test.tsx src/routes/__tests__/sidepanel-persona-locale-keys.test.ts
```

Expected: Persona Garden route and panel regressions remain green.

**Step 3: Run diff sanity check**

Run:

```bash
git diff --check
```

Expected: no whitespace or merge-marker problems.

**Step 4: Final commit**

```bash
git add Docs/Plans/2026-03-13-persona-live-vad-runtime-tuning-design.md Docs/Plans/2026-03-13-persona-live-vad-runtime-tuning-implementation-plan.md apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "feat: add session live vad tuning to persona garden"
```
