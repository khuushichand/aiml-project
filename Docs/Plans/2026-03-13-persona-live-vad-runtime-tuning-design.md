# Persona Live VAD Runtime Tuning Design

## Goal

Add direct, session-only turn-detection controls to `Persona Garden -> Live Session`
so users can shape live voice auto-commit behavior without editing saved persona
defaults.

This slice should make tuning feel immediate and honest:

- presets for fast setup
- an advanced drawer for deeper control
- immediate runtime application while connected
- no persistence into persona profiles yet

## Scope

This slice is limited to:

- `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`
- `apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx`
- `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- focused UI and hook tests already covering Live Session

This slice does not add:

- persona profile schema changes
- saved VAD defaults
- backend API or websocket schema changes
- global speech-setting overrides outside Persona Garden

## Existing Constraints

### The Backend Contract Already Exists

The persona websocket already accepts session-scoped VAD and STT runtime values
via `voice_config`:

- `enable_vad`
- `vad_threshold`
- `min_silence_ms`
- `turn_stop_secs`
- `min_utterance_secs`

Those values are already clamped server-side in
`tldw_Server_API/app/api/v1/endpoints/persona.py`, so the UI should stay within
the same supported ranges rather than inventing new semantics.

### The Current Hook Reset Path Is Too Broad

`usePersonaLiveVoiceController` currently resets listening, transcript, playback,
and warning state whenever persona/session defaults change. That is correct for
persona switch and reconnect, but it would be wrong for live VAD tuning.

If tuning values are added to the existing reset dependency path, changing a
preset would stop the mic and clear the current turn instead of reconfiguring the
runtime.

### `vad_threshold` Is A Threshold, Not A Friendly “Sensitivity” Value

The current Silero turn detector treats speech as present when probability is
greater than or equal to `vad_threshold`. Lower thresholds are easier to trigger;
higher thresholds are more conservative.

So the advanced UI should not present that raw field as a generic “Sensitivity”
control unless it also inverts and explains the value. The safer V1 is to label
it directly as `Speech threshold`.

### Intentional Manual Mode Must Be Different From Unavailable Manual Mode

Today the hook already supports degraded manual-send behavior when server-side VAD
is unavailable. That state is surfaced through `manualModeRequired`.

This slice also needs a user-controlled “Auto-commit off” state. That should not
reuse the same warning or copy as server degradation. The product needs to be
clear about the difference between:

- `Auto-commit unavailable`
- `Auto-commit intentionally turned off for this session`

## Chosen Approach

Keep all tuning session-local inside `usePersonaLiveVoiceController`, extend the
existing `voice_config` sender, and expose the controls through a new `Turn
detection` section in `AssistantVoiceCard`.

The hook should own:

- current VAD preset
- current advanced VAD values
- whether auto-commit is enabled for this session

The route should continue to be a pass-through layer that renders the Live card
and forwards the controller state/actions.

The backend remains unchanged for this slice because the required websocket
contract already exists.

## Session Model

### New Session-Only Runtime State

Add a dedicated `liveVadConfig` state bucket inside
`usePersonaLiveVoiceController`, separate from:

- saved persona defaults
- existing session-only `auto-resume`
- existing session-only `barge-in`

Suggested runtime shape:

- `autoCommitEnabled: boolean`
- `preset: "conservative" | "balanced" | "fast" | "custom"`
- `vadThreshold: number`
- `minSilenceMs: number`
- `turnStopSecs: number`
- `minUtteranceSecs: number`

This state should:

- initialize from a fixed baseline when the persona session starts
- reset on disconnect
- reset on persona switch / session switch
- never write back into persona profiles

### Preset Definitions

`Balanced` should match the current backend defaults:

- `autoCommitEnabled: true`
- `vadThreshold: 0.5`
- `minSilenceMs: 250`
- `turnStopSecs: 0.2`
- `minUtteranceSecs: 0.4`

Recommended preset values:

- `Conservative`
  - `vadThreshold: 0.65`
  - `minSilenceMs: 450`
  - `turnStopSecs: 0.35`
  - `minUtteranceSecs: 0.6`
- `Balanced`
  - `vadThreshold: 0.5`
  - `minSilenceMs: 250`
  - `turnStopSecs: 0.2`
  - `minUtteranceSecs: 0.4`
- `Fast`
  - `vadThreshold: 0.35`
  - `minSilenceMs: 150`
  - `turnStopSecs: 0.1`
  - `minUtteranceSecs: 0.25`

If any advanced value diverges from the selected preset, the hook should derive
the visible preset label as `Custom`.

`Custom` is derived state only. It should not be shown in the default preset
buttons until the user has diverged from a stock preset.

## Runtime Application

### Immediate While Connected

When the websocket is connected and open, any change to:

- auto-commit toggle
- preset
- advanced field

should send a fresh `voice_config` frame immediately.

That frame should include the existing fields plus the tuned STT section:

- `enable_vad`
- `vad_threshold`
- `min_silence_ms`
- `turn_stop_secs`
- `min_utterance_secs`

This should apply to subsequent audio interpretation, not by rewriting completed
or partially processed turns.

### Honest Mid-Utterance Behavior

Immediate application is useful, but it is not perfectly transactional while a
user is already speaking. If the user changes tuning mid-utterance, the current
turn may feel different because the server turn detector is being reconfigured
live.

The UI should say that plainly in the advanced drawer:

`Changes apply immediately and may affect the current live turn.`

### Disconnected Behavior

The controls should remain visible when disconnected so the feature stays
discoverable, but they should be disabled until the session is connected.

Copy should be explicit:

`Connect to tune live turn detection for this session.`

This avoids a misleading local-only state that never reaches the server.

## UI Design

## Turn Detection Block

Add a new `Turn detection` section inside `AssistantVoiceCard`, below the
session-only `Auto-resume` and `Barge-in` toggles.

The block should contain:

- `Auto-commit` session-only toggle
- preset selector
- helper copy
- `Advanced` disclosure button

### Auto-Commit Toggle

The first control should be:

- `Auto-commit (session only)`

Behavior:

- on: presets and advanced fields are active
- off: the session intentionally uses manual send

When auto-commit is off:

- advanced tuning inputs should be disabled
- helper copy should change to:
  `Auto-commit is off for this live session. Use Send now to commit heard speech.`

This state should not be presented as an error or degraded warning.

### Preset Selector

Render compact buttons or a segmented control:

- `Conservative`
- `Balanced`
- `Fast`

If the runtime values no longer match a stock preset, show:

- `Custom`

The current preset should always be visible, even when it is `Custom`.

### Advanced Drawer

The advanced drawer should expose:

- `Speech threshold`
- `Silence before commit`
- `Minimum utterance`
- `Turn tail`

Recommended units:

- threshold: numeric value with two decimals
- silence: milliseconds
- minimum utterance: seconds
- turn tail: seconds

Recommended helper copy:

- `Controls when speech auto-commits in this live session only.`
- `Changes apply immediately and may affect the current live turn.`

### Disabled States

If disconnected:

- disable the entire block
- keep explanatory copy visible

If server-side VAD is unavailable and `manualModeRequired` is true:

- keep the block visible
- disable tuning inputs
- show that tuning applies once server auto-commit becomes available again

If auto-commit is intentionally off:

- keep the block visible
- keep the auto-commit toggle enabled
- disable only the preset selector and advanced fields

## Hook Design

### New Responsibilities

`usePersonaLiveVoiceController` should gain:

- live VAD runtime state
- preset helpers
- advanced-field setters
- derived preset detection

It should return to the route:

- current runtime tuning values
- current preset label
- whether tuning is interactive
- `setAutoCommitEnabled`
- `setVadPreset`
- advanced-field setters
- advanced drawer open/close state, if the card does not own it locally

### Important Separation

The new tuning state must not be included in the existing “full live session
reset” effect that currently depends on persona/session baseline values.

Instead:

- keep the reset effect scoped to persona/session identity changes
- add a dedicated `voice_config` sending effect that depends on runtime tuning

That preserves immediate reconfiguration without killing the current Live Session.

## Route Design

`sidepanel-persona.tsx` should remain thin in this slice.

It needs only to:

- pass the new hook state/actions into `AssistantVoiceCard`
- keep existing Live Session composition intact
- avoid introducing route-owned tuning state

This keeps all runtime tuning semantics in the controller where the websocket
already lives.

## Error And Status Behavior

### Intentional Manual Mode

If the user turns auto-commit off:

- do not show a warning banner
- do not call it degraded mode
- keep `Send now` enabled
- keep `listening_stuck` recovery available, because it still helps when the user
  forgets to commit manually

### Unavailable Manual Mode

If server VAD is unavailable:

- retain the existing warning path
- keep tuning disabled
- make it clear that the controls are temporarily not in effect

### Reconnect And Reset

On disconnect, reconnect, persona switch, or session switch:

- clear session tuning state
- restore the baseline preset
- return the visible preset to `Balanced`

## Testing

### Hook Tests

Add or extend tests in:

- `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx`

Cover:

- baseline runtime VAD config initializes to `Balanced`
- preset changes emit a fresh `voice_config`
- advanced changes emit a fresh `voice_config`
- advanced divergence yields `Custom`
- auto-commit off sends `enable_vad: false`
- disconnect/persona switch resets runtime tuning to the baseline
- runtime tuning changes do not trigger the broad reset path that clears the
  live turn

### Component Tests

Add or extend tests in:

- `apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx`

Cover:

- `Turn detection` block renders
- auto-commit toggle renders
- presets render
- advanced drawer opens
- disconnected/manual-unavailable states disable the controls
- `Custom` appears after advanced edits

### Route Tests

Add or extend tests in:

- `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

Cover:

- connected preset change sends updated `voice_config`
- connected advanced change sends updated `voice_config`
- auto-commit off sends `enable_vad: false`
- reconnect resets the session tuning baseline

## Risks And Mitigations

### Risk: Mid-Utterance Reconfiguration Feels Odd

Mitigation:

- keep changes immediate because that is the requested behavior
- document the behavior in the advanced drawer

### Risk: Threshold Wording Confuses Users

Mitigation:

- avoid vague `Sensitivity` wording
- use `Speech threshold`
- rely on presets for most users

### Risk: Live Card Becomes Too Dense

Mitigation:

- keep the advanced controls collapsed by default
- keep copy short
- keep the route free of duplicate tuning UI

## Recommendation

Implement this as a hook-owned, session-only runtime tuning layer with:

- an explicit `Auto-commit` toggle
- three stock presets
- a derived `Custom` state
- an advanced drawer
- immediate `voice_config` resend while connected

That is the smallest honest step that gives users meaningful control over live
voice behavior without prematurely expanding the persona profile schema.
