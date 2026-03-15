# Persona Turn Detection Defaults Design

## Goal

Persist Persona Garden turn-detection settings into persona `voice_defaults`
without breaking the existing contract that Live Session tuning is session-only
until the user explicitly promotes it.

This slice should make three things true at once:

- persona profiles can store exact turn-detection defaults
- new Live sessions start from those saved defaults
- editing or saving defaults does not silently rewrite an already connected live
  session

## Scope

This slice is limited to:

- `tldw_Server_API/app/api/v1/schemas/persona.py`
- `tldw_Server_API/tests/Persona/test_persona_profiles_api.py`
- `apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx`
- `apps/packages/ui/src/hooks/__tests__/useResolvedPersonaVoiceDefaults.test.tsx`
- `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`
- `apps/packages/ui/src/components/PersonaGarden/AssistantDefaultsPanel.tsx`
- `apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx`
- `apps/packages/ui/src/components/PersonaGarden/__tests__/AssistantDefaultsPanel.test.tsx`
- `apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx`
- `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

This slice does not add:

- browser-global voice-setting changes
- automatic persistence of live tuning as the user edits controls
- hot-reloading of a running live session when saved defaults change in Profiles
- a new persona settings object separate from `voice_defaults`

## Existing Constraints

### Live Session Still Hardcodes A Balanced VAD Baseline

The current live controller initializes and reconnect-resets turn detection to
the hardcoded `balanced` preset in
`apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`.

If saved defaults are added without changing that baseline path, the persona
profile will claim ownership of turn detection while the live runtime keeps
ignoring it.

### Persona Profile PATCH Replaces The Whole `voice_defaults` Object

`PATCH /api/v1/persona/profiles/{persona_id}` currently writes the supplied
`voice_defaults` object as a full replacement, not a field-level merge.

That means a Live-tab save action cannot safely send only the VAD fields. If it
does, it will drop saved STT, TTS, trigger phrases, or confirmation settings.

### The Route Currently Stores Only One Voice Defaults Object

`sidepanel-persona.tsx` currently fetches one `personaVoiceDefaults` object and
passes its resolved values straight into the live controller.

That is fine for the current model, but it becomes dangerous once saved defaults
and live-session defaults need different lifecycles. If a successful save
immediately refreshes the same object the live controller depends on, the
current session can reset or silently change behavior.

### Resolved Fallbacks Are Not The Same Thing As Explicitly Saved Defaults

`useResolvedPersonaVoiceDefaults` already falls back to browser/global settings
for missing persona fields. That is correct for runtime resolution, but it is
not sufficient for deciding whether a persona has actually saved turn-detection
defaults yet.

If the save CTA compares the live session against resolved fallback values
instead of the raw saved profile fields, a persona with no explicit VAD defaults
can look “already matching” and hide the save path incorrectly.

### Saved VAD Values Need The Same Bounds As Live Runtime Values

The live websocket runtime already clamps:

- `vad_threshold` to `0.0..1.0`
- `min_silence_ms` to `50..10000`
- `turn_stop_secs` to `0.05..10.0`
- `min_utterance_secs` to `0.0..10.0`

Persisted defaults should use the same ranges so saved values and effective live
behavior do not drift.

## Chosen Approach

Extend `PersonaVoiceDefaults` with exact turn-detection fields, resolve them
through the existing persona defaults hook, and split the route into two
separate state layers:

- `savedPersonaVoiceDefaults`
- `liveSessionVoiceDefaultsBaseline`

The saved object tracks the latest profile state for the selected persona and is
used by Profiles.

The live baseline is a snapshot captured when the persona session starts or
reconnects. The live controller initializes from that snapshot and keeps its own
session-local edits after that.

This preserves the product contract:

- saved defaults affect future sessions
- Live Session remains session-only until explicitly saved
- explicit save promotes the current session tuning into the persona profile

## Data Model

### Extend `PersonaVoiceDefaults`

Add these nullable fields to `PersonaVoiceDefaults` in
`tldw_Server_API/app/api/v1/schemas/persona.py`:

- `auto_commit_enabled: bool | None`
- `vad_threshold: float | None`
- `min_silence_ms: int | None`
- `turn_stop_secs: float | None`
- `min_utterance_secs: float | None`

Do not add a stored preset label.

Preset state should remain derived from exact values in the UI. That avoids
future preset drift if the product tweaks stock values later.

### Validation Rules

Add schema validation or clamping that matches the live runtime bounds:

- `vad_threshold`: `0.0..1.0`
- `min_silence_ms`: `50..10000`
- `turn_stop_secs`: `0.05..10.0`
- `min_utterance_secs`: `0.0..10.0`

`auto_commit_enabled` remains nullable so saved profiles can intentionally leave
the field unset and inherit the baseline fallback.

### Resolver Output

Extend `ResolvedPersonaVoiceDefaults` in
`apps/packages/ui/src/hooks/useResolvedPersonaVoiceDefaults.tsx` to include:

- `autoCommitEnabled`
- `vadThreshold`
- `minSilenceMs`
- `turnStopSecs`
- `minUtteranceSecs`

These should resolve in this order:

1. explicit persona default
2. fixed balanced fallback for turn detection

Unlike STT/TTS/provider/phrases, turn detection does not have a meaningful
browser-backed source yet. Its fallback should stay internal and deterministic.

## Route State Model

### Separate Saved And Live-Baseline State

`sidepanel-persona.tsx` should hold two related but different values:

- `savedPersonaVoiceDefaults`
  - refreshed from `GET /persona/profiles/{persona_id}`
  - updated immediately after successful profile saves
  - used by Profiles and by the save-CTA comparison helper
- `liveSessionVoiceDefaultsBaseline`
  - captured from the resolved saved defaults when the live persona session
    connects or reconnects
  - passed into `usePersonaLiveVoiceController`
  - not updated just because Profiles saves new defaults while the session is
    already live

This prevents the connected live session from being rewritten when the user
saves new defaults in Profiles or from the Live tab.

### Refresh Behavior After Save

After a successful save of assistant defaults:

- update `savedPersonaVoiceDefaults` immediately so the Profiles tab reflects the
  persisted state
- do not overwrite `liveSessionVoiceDefaultsBaseline` while the session remains
  connected

The next reconnect or persona/session reset should capture the new saved values
and make them the live baseline.

## Live Controller Model

### Initialize From Baseline Snapshot, Not Hardcoded Balanced

`usePersonaLiveVoiceController` should initialize its session-local turn
detection state from `resolvedDefaults` instead of from the hardcoded balanced
preset.

That applies to:

- initial hook state
- persona/session reset effect
- disconnected/reset effect

The controller still owns session-local edits after initialization. Saving
defaults does not bypass that rule.

### Save-CTA Divergence Logic

The Live card should show `Save current settings as defaults` only when the
current live tuning differs from the persona’s explicitly saved VAD state.

That comparison should use a helper based on the raw saved profile fields, not
the fully resolved fallback output.

Recommended rule:

show the save CTA when either:

- any saved VAD field is currently absent, or
- any explicit saved VAD field differs from the current live tuning

That means a persona with no persisted turn-detection defaults can still save a
balanced session explicitly.

### Save Behavior

When the user clicks `Save current settings as defaults`:

1. take the latest `savedPersonaVoiceDefaults`
2. merge in the current live turn-detection values
3. send the full merged `voice_defaults` object in `PATCH /profiles/{persona_id}`
4. optionally include `expected_version` when available
5. update only `savedPersonaVoiceDefaults` from the response

The live controller should keep its current session-local state unchanged after
save.

## UI Design

### Shared Turn Detection Controls

The current turn-detection block in `AssistantVoiceCard` is already substantial.
Duplicating it into `AssistantDefaultsPanel` would create immediate drift.

Extract a shared presentational component, for example:

- `apps/packages/ui/src/components/PersonaGarden/PersonaTurnDetectionControls.tsx`

It should render:

- the heading
- helper copy
- `Auto-commit`
- preset buttons
- `Advanced` drawer
- exact numeric inputs

The shared component should stay dumb:

- receives values, preset, disabled state, and callbacks
- derives no route-level save behavior
- allows scope-specific copy

Live Session and Assistant Defaults can then provide different helper text and
disabled rules without duplicating the control tree.

### Assistant Defaults Panel

Add a `Turn detection defaults` section in `AssistantDefaultsPanel` using the
shared control block.

This section edits saved persona defaults, not the live session. Its copy should
say that clearly, for example:

`Saved for future live sessions. Existing live sessions keep their current turn-detection settings until reconnect.`

The panel should keep the existing `Save assistant defaults` button as the only
save action in Profiles.

### Live Session Card

Keep the current turn-detection controls in the Live card, but add a secondary
action:

- `Save current settings as defaults`

Suggested behavior:

- visible only while connected
- disabled while a save is in flight
- hidden when no VAD divergence exists

Suggested helper copy:

- session controls remain labeled `session only`
- save CTA copy stays focused on promotion:
  `Save current settings as defaults`

No automatic save should occur on checkbox/preset/input change.

## Sync Rules

### Profiles To Live

Saved defaults affect:

- future connects
- reconnects
- persona/session resets

They do not hot-override a currently connected live session.

### Live To Profiles

Live settings affect:

- current session behavior immediately

They affect the persona profile only after the user clicks the explicit save
action.

### Post-Save State

After a successful Live-tab save:

- the save CTA disappears because the live state now matches the explicit saved
  VAD defaults
- Profiles reflects the new saved defaults immediately
- the running live session continues unchanged because it is already using those
  exact values

## Testing Strategy

### Backend

Extend persona profile API coverage to assert the new `voice_defaults` fields
round-trip on create and patch, and that invalid out-of-range VAD values are
normalized or rejected consistently with the chosen schema behavior.

### Resolver

Extend `useResolvedPersonaVoiceDefaults` tests to verify:

- explicit persona VAD defaults win
- balanced fallback fills missing VAD values
- existing STT/TTS fallback behavior remains unchanged

### Assistant Defaults

Extend `AssistantDefaultsPanel` tests to verify:

- load and save of turn-detection defaults
- advanced drawer editing
- preset derivation to `Custom`
- payload contains the new exact VAD fields

### Live Session

Extend route and Live Session tests to verify:

- saved persona VAD defaults seed the live baseline on connect
- reconnect picks up updated saved defaults
- `Save current settings as defaults` appears only when explicit saved VAD state
  is absent or different
- the save action patches a merged `voice_defaults` object instead of dropping
  other saved fields
- saving defaults while connected does not reset the current live session

## Risks And Guardrails

### Whole-Object `voice_defaults` Replacement

This is the highest-risk path in the slice. Every save path that touches
turn-detection defaults must merge with the latest saved `voice_defaults` first.

### Live Session Reset Coupling

Do not key the broad live-session reset effect off of freshly fetched saved
defaults. It should depend on the baseline snapshot captured for the session.

### UI Drift

Do not copy the turn-detection markup into two places. Use a shared component or
shared helper layer from the start.

## Out Of Scope

- global/browser persistence of turn detection
- per-persona VAD analytics
- live hot-apply from Profiles into an already connected session
- preset customization or user-defined presets
