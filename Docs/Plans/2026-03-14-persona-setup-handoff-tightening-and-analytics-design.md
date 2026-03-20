# Persona Setup Handoff Tightening And Analytics Design

**Date:** 2026-03-14

## Goal

Finish the remaining post-setup handoff tightening in Persona Garden and add
setup-specific analytics that can answer whether setup actually leads to first
successful use.

This slice should:

- make the post-setup handoff recommend one clear next step
- keep the handoff visible long enough to bridge into real use
- record setup and handoff behavior without mixing it into live voice runtime
  analytics

## Why This Slice Exists

The current setup flow is functionally complete, but the completion handoff is
still thinner than the rest of the setup experience.

Today:

- the handoff card shows useful review data, but it clears on any handoff action
- the card does not distinguish between navigation and real follow-through
- the route has no explicit notion of a first meaningful post-setup action
- setup success and recovery are not instrumented separately from live voice
  analytics

That means the UX is still abrupt after completion, and product decisions about
which setup paths work best are still guesswork.

## Scope

### In scope

- post-setup handoff recommendation logic
- delayed handoff dismissal and compact post-consumption state
- explicit `setup_run_id` correlation for setup flows
- append-only setup analytics event persistence and a small summary read path
- route-side setup analytics emission and handoff instrumentation
- focused frontend/backend tests

### Out of scope

- new live voice runtime behavior
- generic product telemetry
- a full analytics dashboard
- stable scroll/focus anchors across all Persona Garden tabs
- broad setup wizard redesign

## Review-Driven Constraints

### 1. Setup runs need a durable identifier

The current persona setup state stores:

- `status`
- `version`
- `current_step`
- `completed_steps`
- `completed_at`
- `last_test_type`

That is not enough to group events into one setup attempt across:

- resume after reload
- reset
- rerun
- completion and handoff actions

This design adds a durable `run_id` to setup state. That `run_id` is the
correlation key for setup analytics and for post-completion handoff state.

### 2. Handoff persistence needs explicit rules

The current route clears `setupHandoff` on any handoff action. That is too
eager, but replacing it with vague “keep the handoff around longer” behavior is
not enough.

This design makes the rule explicit:

- same-tab handoff actions keep the handoff visible on the current tab
- cross-tab handoff actions retarget the handoff to the destination tab
- the handoff clears only on:
  - explicit dismiss
  - persona/setup context change
  - first successful post-setup action, which collapses it into a compact
    completion banner instead of dropping it immediately

### 3. First post-setup action must mean success, not navigation

CTA clicks and tab switches are not meaningful follow-through by themselves.

This design treats only successful domain actions as
`first_post_setup_action`, for example:

- `command_saved`
- `connection_saved`
- `connection_test_succeeded`
- `voice_defaults_saved`
- `dry_run_match`
- `live_response_received`

Navigation events remain `handoff_action_clicked`, not success.

### 4. Same-tab anchoring is not ready in V1

Commands, Profiles, and Connections do not currently expose a stable
handoff-anchor contract. This design does not promise scroll/focus targeting in
V1.

Instead:

- same-tab actions keep the handoff visible
- cross-tab actions retarget the handoff to the new tab
- target anchoring can be a later polish slice once dedicated refs exist

### 5. Setup analytics should not ride on profile PATCH writes

Setup profile mutations are already versioned with `expected_version`. Analytics
events are append-only. Combining those two concerns would create conflict
churn, couple telemetry to mutable profile state, and make retries harder to
reason about.

This design uses:

- profile PATCH for setup state and setup `run_id`
- a separate append-only setup analytics event endpoint/table for instrumentation

### 6. Dedupe rules must be explicit

Some setup events are effect-driven and should be recorded at most once per run
or step. Others are user-click-driven and may occur more than once.

This design splits them into two groups:

- deterministic once-only events with stable `event_key`
- user-action events with unique `event_id`

## Chosen Approach

Use a route-owned, run-aware handoff model on the frontend and a separate,
append-only persona setup analytics store on the backend.

Concretely:

1. Extend `PersonaSetupState` with a persistent `run_id`.
2. Freeze `run_id`, review summary, completion type, and recommended next step
   into `setupHandoff` at completion time.
3. Let handoff actions either preserve the handoff on the same tab or retarget
   it to a new tab.
4. Collapse the full handoff into a compact success banner only after one
   successful post-setup action.
5. Emit setup analytics events through a dedicated route-level helper into a new
   append-only backend table.
6. Expose a small setup analytics summary endpoint for recent runs and aggregate
   handoff/recovery metrics.

This keeps UX state and analytics state coherent without turning setup
instrumentation into another profile mutation layer.

## Setup State Model

### `PersonaSetupState`

Extend setup state with:

```ts
type PersonaSetupState = {
  status: "not_started" | "in_progress" | "completed"
  version: number
  run_id: string | null
  current_step: PersonaSetupStep
  completed_steps: PersonaSetupStep[]
  completed_at: string | null
  last_test_type: "dry_run" | "live_session" | null
}
```

### `run_id` lifecycle

- when setup starts from `not_started`, generate a new `run_id`
- when setup is reset or rerun, generate a new `run_id`
- when setup resumes, keep the existing `run_id`
- when setup completes, keep that `run_id` in the completed setup state until
  the next reset/rerun

This gives the route and backend one durable identifier for:

- step progress
- detours
- completion
- handoff actions
- first real post-setup success

## Handoff Tightening

### Handoff state

Extend the current route-owned handoff state to include:

```ts
type SetupRecommendedActionTarget =
  | "commands"
  | "connections"
  | "profiles"
  | "live"
  | "test-lab"

type SetupPostSetupActionType =
  | "command_saved"
  | "connection_saved"
  | "connection_test_succeeded"
  | "voice_defaults_saved"
  | "dry_run_match"
  | "live_response_received"

type SetupHandoffState = {
  runId: string
  targetTab: PersonaGardenTabKey
  completionType: "dry_run" | "live_session"
  reviewSummary: SetupReviewSummary
  recommendedAction: {
    target: SetupRecommendedActionTarget
    label: string
    reason: string
  }
  consumedAction: SetupPostSetupActionType | null
  compact: boolean
}
```

### Recommended next step

Derive one preferred next step from the frozen review summary plus completion
type:

- no starter commands configured:
  - target: `commands`
  - label: `Add your first command`
- no connection available:
  - target: `connections`
  - label: `Add a connection`
- completed by `dry_run`:
  - target: `live`
  - label: `Try your first live turn`
- completed by `live_session`:
  - target: `commands`
  - label: `Review starter commands`
- fallback:
  - target: `profiles`
  - label: `Adjust assistant defaults`

The handoff card should present this as the primary CTA and keep the starter
pack review rows as secondary actions.

### Persistence and dismissal rules

- the full handoff card renders on `setupHandoff.targetTab`
- clicking a same-tab action:
  - keeps `setupHandoff` intact
  - records `handoff_action_clicked`
- clicking a cross-tab action:
  - switches `activeTab`
  - retargets `setupHandoff.targetTab`
  - records `handoff_action_clicked`
- clicking dismiss:
  - clears `setupHandoff`
  - records `handoff_dismissed`

### Compact completion state

After the first successful post-setup action:

- do not remove the handoff immediately
- set `compact = true`
- replace the full review card with a smaller `Setup complete` banner for the
  current setup run

The compact banner exists to confirm follow-through without keeping the full
review UI on screen indefinitely.

It clears on:

- explicit dismiss
- persona/setup context change
- reset/rerun

## Setup Analytics

### Separate analytics model

Add a new append-only setup analytics model separate from persona live voice
analytics.

Recommended table: `persona_setup_events`

Fields:

- `event_id`
- `user_id`
- `persona_id`
- `run_id`
- `event_type`
- `event_key`
- `step`
- `completion_type`
- `detour_source`
- `action_target`
- `created_at`
- `metadata_json`

### Event types

Recommended initial set:

- `setup_started`
- `step_viewed`
- `step_completed`
- `step_error`
- `retry_clicked`
- `detour_started`
- `detour_returned`
- `setup_completed`
- `handoff_action_clicked`
- `handoff_dismissed`
- `first_post_setup_action`

### Dedupe and idempotency

Use both `event_id` and optional `event_key`.

- `event_id`
  - always unique
  - required for every event
- `event_key`
  - present for once-only events
  - unique within `(persona_id, run_id, event_key)`

Once-only events should use deterministic keys such as:

- `setup_started`
- `step_viewed:test`
- `step_completed:commands`
- `setup_completed`
- `handoff_dismissed`
- `first_post_setup_action`

Repeatable click-driven events such as `retry_clicked` and
`handoff_action_clicked` should omit `event_key` and use a fresh `event_id`.

### Backend summary API

Add a small summary endpoint:

- `GET /api/v1/persona/profiles/{persona_id}/setup-analytics`

Recommended response shape:

- aggregate summary:
  - `total_runs`
  - `completed_runs`
  - `completion_rate`
  - `dry_run_completion_count`
  - `live_session_completion_count`
  - `most_common_dropoff_step`
  - `handoff_click_rate`
  - `first_post_setup_action_rate`
  - detour recovery counts by source
- recent runs:
  - `run_id`
  - `started_at`
  - `completed_at`
  - `completion_type`
  - `terminal_step`
  - `handoff_clicked`
  - `handoff_dismissed`
  - `first_post_setup_action`

### Frontend emission rules

The route should emit setup analytics best-effort from the handlers and effects
that already own setup state:

- on start/reset/rerun -> `setup_started`
- on step changes -> `step_viewed`
- on successful step transitions -> `step_completed`
- on step-local failures -> `step_error`
- on retry buttons -> `retry_clicked`
- on setup detours -> `detour_started`
- on return from detours -> `detour_returned`
- on completion -> `setup_completed`
- on handoff CTA clicks -> `handoff_action_clicked`
- on dismiss -> `handoff_dismissed`
- on first successful post-setup action -> `first_post_setup_action`

These writes should be best-effort and never block setup UX.

## V1 Analytics Exposure

This PR should not add a full end-user analytics dashboard.

V1 analytics exposure is:

- append-only event persistence
- one setup analytics summary endpoint
- backend and route tests proving the emitted data is correct

Any future Profiles-side setup insights card can reuse that endpoint later.

## Testing

### Frontend

- `PersonaSetupHandoffCard.test.tsx`
  - recommended CTA derivation
  - compact banner rendering after `consumedAction`
- `sidepanel-persona.test.tsx`
  - same-tab handoff action keeps the handoff visible
  - cross-tab handoff action retargets the handoff
  - first successful post-setup action collapses the handoff
  - setup analytics events are emitted with the correct run/action metadata

### Backend

- `test_persona_profiles_api.py`
  - setup `run_id` round-trips through profile create/update/get
- new setup analytics API tests
  - append-only event write
  - once-only dedupe via `event_key`
  - recent run summary aggregation

### End-to-end

- one Playwright update:
  - complete setup
  - land on handoff
  - take the recommended next action
  - verify compact completion state instead of abrupt disappearance

## Risks

### Overcounting events

Mitigation:

- deterministic `event_key` for once-only events
- unique `event_id` for repeatable actions
- keep effect-driven analytics emission in one route helper

### Handoff staying around too long

Mitigation:

- compact the handoff after first successful action
- keep explicit dismiss available

### Scope creep from target anchoring

Mitigation:

- do not promise scroll/focus targeting in V1
- keep same-tab behavior limited to persistence, not deep navigation

## Recommended Slice Order

1. add `run_id` and backend setup analytics primitives
2. wire route-level setup analytics emission
3. tighten handoff recommendation/retargeting/collapse behavior
4. add Playwright coverage for the post-setup action flow
