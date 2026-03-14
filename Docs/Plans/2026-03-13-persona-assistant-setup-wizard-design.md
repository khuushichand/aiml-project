# Persona Assistant Setup Wizard Design

## Goal

Add a first-run setup wizard inside Persona Garden that helps a user build a usable voice assistant without introducing a second assistant model. The wizard must be persona-scoped, require an explicit persona choice, require one explicit successful test before completion, and reuse the existing Persona Garden surfaces instead of duplicating them.

## Why This Needs A Different Shape

The current Persona Garden route already owns live session state, approvals, analytics, commands handoff, and saved/live voice defaults. Adding another large state machine directly into the route would create unnecessary risk. The backend also has no persistent setup-completion model today, so a route-local wizard would not survive reloads or device changes.

The revised design therefore makes setup progress part of the persona profile, while keeping the actual assistant configuration in the existing persona resources:

- voice defaults stay in `voice_defaults`
- starter commands stay in persona voice commands
- optional integrations stay in persona connections
- test success is recorded as setup metadata, not inferred from UI state

## Design Principles

- Persona-first architecture. No separate `assistant_profile` object.
- Explicit user intent. The user must choose an existing persona or create a new one.
- No duplicated editors. The wizard orchestrates existing capabilities and smaller shared controls.
- Completion is truthful. A wizard is only complete after a specific recorded test succeeds.
- Full setup is mandatory for incomplete personas. Deep links do not silently bypass onboarding.

## Data Model

### Persona-scoped setup metadata

Extend the persona profile shape with a nested setup object, for example:

```json
{
  "setup": {
    "status": "not_started",
    "version": 1,
    "current_step": "persona",
    "completed_at": null,
    "last_test_type": null
  }
}
```

Recommended fields:

- `status`: `not_started | in_progress | completed`
- `version`: integer so the wizard can evolve later without migrating unrelated profile data
- `current_step`: `persona | voice | commands | safety | test`
- `completed_at`: timestamp or `null`
- `last_test_type`: `dry_run | live_session | null`

This object stores wizard progress only. It does not duplicate commands, connections, or voice defaults.

### Existing resource ownership remains unchanged

- Voice defaults stay in `PersonaVoiceDefaults`
- Commands remain persona-scoped voice commands
- Connections remain persona-scoped connection records
- Approval posture continues to use existing confirmation/default policy controls

## Route Architecture

### Wizard placement

The setup experience lives inside Persona Garden as a route-owned overlay, not a new top-level route and not a new tab.

Recommended structure:

- `sidepanel-persona.tsx` remains the route owner
- add a dedicated hook such as `usePersonaSetupWizard`
- add a route overlay component such as `AssistantSetupWizard`

The route should own:

- selected persona id
- whether setup gating is active for that persona
- target post-setup tab to restore after completion
- callbacks for creating personas, saving progress, and marking completion

The wizard component should own:

- current local form state for the active step
- rendering of staged content
- step validation messages

### Why not a separate route

A separate route would duplicate persona selection, profile fetch, and session bootstrap. The existing route already contains the right backend calls and tab surfaces. The overlay approach lets setup guide users without forking the product architecture.

## Deep-Link And Bootstrap Behavior

Current route bootstrap can set `tab` and `personaId` from the URL. That behavior should remain, but incomplete setup must gate access.

Revised behavior:

1. Bootstrap still reads the incoming `personaId` and requested tab.
2. The route loads the persona profile and setup metadata.
3. If the selected persona has `setup.status !== "completed"`, show the setup overlay before exposing the requested tab.
4. Preserve the intended tab as `postSetupTargetTab`.
5. After the wizard completes, remove the overlay and land the user on the preserved target tab or `live` by default.

This keeps power-user links meaningful without allowing incomplete personas to silently skip onboarding.

## Wizard Flow

### Step 1: Choose A Persona Explicitly

The wizard always starts with an explicit persona decision, even if the backend already auto-created a default persona.

The step should offer:

- `Use this persona` for existing catalog entries
- `Create new persona` with a minimal create form

Requirements:

- never auto-advance just because one persona exists
- if a default persona exists, present it as a real choice
- the step completes only when the user explicitly selects or creates a persona

On success:

- persist `setup.status = "in_progress"`
- persist `setup.current_step = "voice"`

### Step 2: Voice Defaults

This step configures the assistant’s future live-session defaults, not the current live session.

It should reuse the existing voice-default controls and turn-detection controls where possible:

- trigger phrases
- STT language/model
- TTS provider/voice
- confirmation mode
- turn detection defaults

The step saves into `voice_defaults` on the selected persona profile.

Requirements:

- use shared controls instead of duplicating the Assistant Defaults form logic
- keep copy explicit: these are saved defaults for future sessions
- completion moves `setup.current_step` to `commands`

### Step 3: Starter Commands

This step helps the user add useful starter commands without exposing the full advanced command editor immediately.

The step should support:

- curated quick templates
- MCP-backed tool suggestions
- light phrase customization before save

It should not clone the whole `CommandsPanel`.

Recommended behavior:

- show a shortlist of suggested starter actions
- let the user add at least one enabled command, or explicitly continue with none
- save commands through the existing persona voice-command endpoints

Completion should persist `setup.current_step = "safety"`.

### Step 4: Safety And Connections

This step forces an explicit choice about approvals and optional external integrations.

The user should make an explicit decision on:

- confirmation mode / approval posture
- whether they want to add any external connection now

This step must be explicit even if the user chooses “no external connections for now.”

Recommended behavior:

- reuse existing confirmation mode semantics already stored in `voice_defaults`
- allow optional connection creation with the existing connection model
- persist `setup.current_step = "test"` once the user makes an explicit choice

### Step 5: Test And Finish

Completion requires one explicit successful test. The wizard should record which test passed.

Accepted completion paths:

- `dry_run`: a successful persona command test via the existing dry-run endpoint
- `live_session`: a successful live persona session turn from the Live tab flow

Rules:

- the UI must show which test type completed setup
- the route must persist `setup.last_test_type`
- the profile must be marked completed only after a recorded success event

On completion:

- persist
  - `setup.status = "completed"`
  - `setup.current_step = "test"`
  - `setup.completed_at = now`
  - `setup.last_test_type = <type>`
- close the overlay
- restore the intended tab

## Resume And Partial Progress

The wizard is resumable per persona.

Resume logic:

- `not_started`: open at `persona`
- `in_progress`: open at `current_step`
- `completed`: do not gate the route

Earlier step data should be read from the real saved resources:

- voice defaults from the profile
- starter commands from persona commands
- connections from persona connections

The setup object only tracks progress, not full form payloads.

## Interaction With Existing Tabs

The existing tabs remain the long-term advanced workspace.

Wizard responsibilities:

- get the user to a working baseline quickly
- keep them on the happy path
- record completion honestly

Existing tabs remain responsible for:

- advanced command editing
- connection management
- live repair/testing beyond the wizard
- deep analytics and debugging

This keeps the wizard small and prevents long-term UI drift.

## Error Handling

- Persona create/select failure: stay on step 1 and show inline error
- Voice default save failure: keep local step state and allow retry
- Command creation failure: show per-template error, do not advance
- Connection save failure: allow the user to keep “no connection for now” if that was their explicit choice
- Test failure: do not mark setup complete; keep the user on step 5 with actionable retry options

If the route has unrelated unsaved state-doc drafts, the wizard should not silently discard them. Setup-triggered persona/session changes must coordinate with the existing blocker rules.

## Testing Strategy

### Backend

- profile create/list/get/patch round-trip for the new setup object
- setup completion update persists `last_test_type` and `completed_at`
- existing profile behavior remains intact when setup data is omitted

### Frontend

- route gating shows the wizard for incomplete personas
- URL bootstrap stores the intended tab and restores it after completion
- explicit persona choice is required even when one default persona exists
- each step persists progress correctly
- command/test completion records the explicit test type
- completed personas no longer block access on reload

## Non-Goals For V1

- a second assistant profile model
- wizard-time persona analytics recommendations
- importing heard phrases directly into setup
- advanced command editing from inside the wizard
- multi-path branching setup graphs

## Recommended Next Step

Implement this as:

1. backend persona setup metadata
2. route gating and overlay shell
3. staged setup steps using existing APIs and shared controls
4. explicit test completion recording

That gives a truthful first-run assistant builder without splitting Persona Garden into a second product.
