# Persona Assistant Setup Experience Polish Design

## Goal

Improve the end-to-end assistant setup experience in Persona Garden without expanding the underlying assistant model. This pass should make setup easier to finish, more reliable under failure and retry conditions, and clearer after completion, while staying persona-first and reusing the existing wizard, tabs, and saved persona resources.

## Why A Second Setup Pass Is Needed

The first setup-wizard pass established the core flow:

- persona-scoped setup metadata
- route gating for incomplete personas
- explicit persona choice
- saved voice defaults
- starter commands
- explicit safety/connections choice
- required dry-run or live-session completion

That baseline is functional, but it still has several product gaps:

- resuming setup does not preserve the user’s original target tab cleanly
- reset and rerun semantics are not yet separated from existing persona artifacts
- step failures are still mostly funneled into generic route-level error state
- the test step does not yet model failure types cleanly enough for good retry guidance
- completion and post-completion handoff are fragmented, especially around live-session completion

This design addresses those gaps while keeping the current wizard architecture intact.

## Scope

### In scope

- wizard progress rail with per-step status and summaries
- persona-scoped `Resume setup`, `Reset setup`, and `Rerun setup`
- stable captured setup intent target tab
- step-scoped error and retry UX
- structured setup test outcomes for dry-run and live-session flows
- unified post-setup handoff card on the intended destination tab
- Playwright coverage for the main setup flow and one retry path

### Out of scope

- new voice runtime capabilities
- new command/runtime domain models
- additional assistant profile objects
- automatic “step completion” inferred only from existing persona data
- full deletion of commands, connections, or defaults on reset/rerun

## Design Principles

- Persona-first. Setup remains metadata on the persona profile.
- One source of truth per domain. Commands remain commands, defaults remain defaults, connections remain connections.
- Progress is about this setup run, not about whether configuration artifacts happen to exist.
- Failure states must leave the user with a concrete forward action.
- Completion should feel intentional, not like an abrupt overlay dismissal.

## Key Review Fixes Incorporated

### 1. Stable target-tab handoff

`postSetupTargetTab` must no longer be derived live from the currently active tab. The route should capture a dedicated `setupIntentTargetTab` the first time setup gating activates for a persona or when the user explicitly reruns setup.

That captured target should:

- survive wizard resume
- survive step transitions
- drive post-completion handoff
- clear only after setup finishes and the handoff card is dismissed or consumed

### 2. Progress belongs to the setup run, not existing artifacts

Resetting or rerunning setup should not treat existing commands/defaults/connections as already completed. The design therefore extends persona setup metadata to track completed steps for the current setup run.

Existing artifacts may still be surfaced as contextual hints such as:

- `Saved voice defaults already exist`
- `2 enabled commands already exist`
- `1 connection already exists`

But they must not mark steps complete automatically.

### 3. Step-scoped error state

The setup experience needs a route-owned step error model instead of one generic wizard error. Each step must be able to render its own failure copy, retry affordance, and optional advanced escape hatch without stepping on unrelated steps.

### 4. Structured setup test outcomes

The test step needs a real outcome model, not just free-form error strings plus a green state. Dry-run and live-session testing should each produce route-owned structured outcomes that the UI can translate into actionable next steps.

### 5. Unified completion and handoff

The existing live-session completion helper inside the composer should be folded into the broader setup flow. The wizard owns setup completion while setup is still in progress; the destination-tab handoff card owns the post-completion experience. There should not be two overlapping “finish setup” surfaces.

### 6. Version-aware setup mutations

All setup metadata writes should use the persona profile version returned from the backend and send `expected_version` on update. This reduces setup-state races now that the wizard is adding more resume/reset/rerun transitions.

## Data Model

### Persona setup metadata

Extend `PersonaSetupState` with one additional field:

```json
{
  "setup": {
    "status": "in_progress",
    "version": 1,
    "current_step": "commands",
    "completed_steps": ["persona", "voice"],
    "completed_at": null,
    "last_test_type": null
  }
}
```

Recommended fields:

- `status`: `not_started | in_progress | completed`
- `version`: wizard schema version
- `current_step`: `persona | voice | commands | safety | test`
- `completed_steps`: ordered or set-like list of completed steps for the current run
- `completed_at`: timestamp or `null`
- `last_test_type`: `dry_run | live_session | null`

### Semantics

- `completed_steps` tracks what the user has explicitly completed in this setup run.
- `current_step` is the step the wizard should open on if resumed.
- `completed_steps` resets to `[]` when setup is reset or rerun.
- Reset/rerun does not delete commands, connections, or defaults.

## Route Architecture

The route remains the owner of setup orchestration, but PR 2 should avoid inflating `sidepanel-persona.tsx` with additional inline branching. The route should own the state, while focused components render it.

### Route-owned setup state

Add or normalize the following route state:

- `savedPersonaSetup`
- `savedPersonaProfileVersion`
- `setupIntentTargetTab`
- `setupHandoff`
- `setupStepErrors`
- `setupTestOutcome`

#### `setupIntentTargetTab`

Stores the user’s intended destination tab for the active setup run. This is captured when setup gating begins or when rerun starts.

#### `setupHandoff`

Stores a transient post-completion payload, for example:

```ts
{
  personaId: string
  targetTab: PersonaGardenTabKey
  completionPath: "dry_run" | "live_session"
  completedAt: string
}
```

This drives the post-setup handoff card and clears after dismissal or meaningful interaction.

#### `setupStepErrors`

A route-owned map keyed by step name, for example:

```ts
{
  persona?: SetupStepError
  voice?: SetupStepError
  commands?: SetupStepError
  safety?: SetupStepError
  test?: SetupTestOutcomeError
}
```

This avoids collapsing unrelated failures into one generic banner.

#### `setupTestOutcome`

A route-owned structured result model that distinguishes test outcomes cleanly.

## Wizard UI

### Progress rail

Extend `AssistantSetupWizard` with a compact progress rail. Each step should show:

- label
- status: `current`, `completed`, `pending`
- summary for completed steps in this run
- optional hint if existing config artifacts are detected but not yet reviewed in this run

Example summaries:

- `Persona chosen`
- `Voice defaults saved`
- `Starter command added` or `Continued without starter commands`
- `Safety choice saved`
- `Completed with dry run`

Example artifact hints:

- `Existing defaults detected`
- `2 enabled commands already exist`
- `1 saved connection available`

### Setup status card in Profiles

Add a `PersonaSetupStatusCard` above or alongside the existing defaults panel.

States:

- `Not started`
  - show `Start setup`
- `In progress`
  - show current step
  - show completed-step summaries
  - actions: `Resume setup`, `Reset setup`
- `Completed`
  - show completion date
  - show completion path: `Dry run` or `Live session`
  - action: `Rerun setup`

### Post-setup handoff card

Add a route-owned `PersonaSetupHandoffCard` rendered on the intended target tab after setup completion.

This card should:

- explain setup is complete
- say how completion happened: `Finished with dry run` or `Finished with live session`
- offer two or three contextual next actions

Examples:

- `Commands`: `Review starter commands`, `Open Test Lab`
- `Live`: `Start live session`, `Review turn detection defaults`
- `Profiles`: `Adjust assistant defaults`, `Open Commands`
- `Test Lab`: `Try a new phrase`, `Create another command`

The handoff card is transient and should clear after dismissal or after the user takes one of its actions.

## Setup Flow Semantics

### Start setup

For personas with `setup.status = "not_started"`:

- capture `setupIntentTargetTab`
- show wizard at `persona`
- initialize `completed_steps = []`

### Resume setup

For personas with `setup.status = "in_progress"`:

- preserve existing `setupIntentTargetTab` if already captured in route state for this visit
- otherwise capture the current tab once
- reopen the wizard at `current_step`
- render progress summaries from `completed_steps`

### Reset setup

Reset means:

- keep persona resources intact
- set:
  - `status = "in_progress"`
  - `current_step = "persona"`
  - `completed_steps = []`
  - `completed_at = null`
  - `last_test_type = null`
- keep the user on the current selected persona
- prompt with explicit copy that persona data is not deleted

### Rerun setup

Rerun means:

- same metadata reset behavior as `Reset setup`
- intended for already-completed personas
- starts in a review-first mode because existing configuration artifacts will still be present
- still requires explicit step completion in the new run

## Step-by-Step UX

### Persona step

- User must explicitly choose current persona, switch persona, or create a new one.
- For rerun on the current persona, the current persona may be visually emphasized, but the user still must explicitly continue with it.
- On success:
  - append `persona` to `completed_steps`
  - set `current_step = "voice"`

### Voice step

- Reuse `AssistantDefaultsPanel` and shared turn-detection controls.
- If saved defaults already exist, show that as a hint, not as completion.
- Failures remain local to the voice step.
- On save:
  - append `voice`
  - set `current_step = "commands"`

### Commands step

- Continue to use starter templates and MCP starter creation.
- Step-local retry UX should distinguish:
  - template create failure
  - MCP starter create failure
  - explicit continue-without-commands
- On explicit success:
  - append `commands`
  - set `current_step = "safety"`

### Safety step

- Keep confirmation posture explicit.
- Keep “no external connection for now” as a valid explicit path.
- Step-local errors should distinguish:
  - validation issue
  - connection creation failure
  - confirmation/default save failure
- On explicit success:
  - append `safety`
  - set `current_step = "test"`

### Test step

The test step must distinguish dry-run and live-session outcomes structurally.

Recommended route model:

```ts
type SetupTestOutcome =
  | { kind: "idle" }
  | { kind: "dry_run_success"; heardText: string; commandName?: string | null }
  | { kind: "dry_run_no_match"; heardText: string }
  | { kind: "dry_run_failure"; heardText: string; failurePhase?: string | null; message: string }
  | { kind: "live_unavailable"; message: string }
  | { kind: "live_sent"; text: string }
  | { kind: "live_success"; text: string; responseText: string }
  | { kind: "live_failure"; text?: string; message: string }
```

This allows the UI to show clear next actions such as:

- `No direct command matched. Create a starter command or try live session.`
- `Dry run failed validation. Review the command in Commands.`
- `Live session is not connected yet. Connect and try again.`
- `Live test sent, waiting for assistant response.`

On completion:

- append `test` to `completed_steps`
- set `status = "completed"`
- set `completed_at`
- set `last_test_type`
- set `setupHandoff`
- close the overlay
- navigate to `setupIntentTargetTab`

## Reliability And Failure Handling

### Step-local retries

Each step must keep its own error and retry affordances. Generic top-level setup errors should be reserved for route-level failures that genuinely affect the whole wizard.

Step-local examples:

- persona step: retry `Use this persona` or `Create new persona`
- voice step: retry save directly inside defaults panel
- commands step: retry selected starter action or continue without one
- safety step: retry connection creation or choose no connection
- test step: retry dry-run, connect live, resend live message, or switch to another completion path

### Live-session completion unification

Remove the special pre-completion `setupLiveCompletionCard` from the normal composer area. Live-session completion guidance should live inside the setup test step while setup is active. After completion, the target-tab handoff card takes over.

### Blockers and unsaved state

Setup-triggered persona switching and live-session connect actions must continue to honor existing unsaved-state blockers. The wizard should not silently bypass those protections.

## Backend Changes

Keep backend changes narrow:

- extend `PersonaSetupState` with `completed_steps`
- continue using persona profile patching for setup metadata
- rely on `expected_version` for setup mutations

No new assistant-specific table or route family is needed for PR 2.

## Testing Strategy

### Backend

- schema/API tests for `completed_steps`
- reset/rerun metadata update tests
- optimistic concurrency behavior for setup patch updates where appropriate

### Frontend unit/integration

- wizard progress rail status and summary rendering
- setup status card states: not started, in progress, completed
- reset/rerun actions
- step-scoped error rendering
- structured test-outcome rendering
- captured `setupIntentTargetTab` behavior
- post-setup handoff card rendering and dismissal

### Playwright

Add at least two browser-level flows:

1. happy path resume/finish flow
2. one failure-and-retry path, preferably in commands, safety, or test

## Smallest Coherent PR 2

The smallest coherent version of this design includes:

- `completed_steps` in setup metadata
- progress rail and setup status card
- route-owned `setupIntentTargetTab`
- reset/rerun setup actions
- step-scoped error/test outcome state
- unified post-setup handoff card
- Playwright happy path plus one retry scenario

That is broad enough to materially improve completion, reliability, and post-setup clarity, while still staying tightly bounded around the existing setup system.
