# Persona Setup Connection Hints And Starter Pack Review Design

## Goal

Polish the Persona Garden setup flow in two focused ways:

- add shallow but useful connection validation hints to the setup safety/connections step
- expand the post-setup handoff card into a compact starter-pack review surface

This pass should reduce obvious setup mistakes without turning the wizard into a full advanced editor, and it should make completion feel more informative without reopening the entire wizard.

## Why This Slice Exists

The current setup flow already supports:

- explicit persona choice
- saved voice defaults
- starter command selection
- safety and connection setup
- required dry-run or live-session completion
- post-setup handoff on the intended target tab

That baseline works, but two product gaps remain:

1. the safety/connections step only validates that `name` and `baseUrl` are non-empty, which makes first-run connection setup too blind
2. the post-setup handoff card confirms completion, but does not summarize what the setup flow actually configured

This design addresses those two gaps without changing the underlying persona model or adding a second setup workflow.

## Scope

### In scope

- client-side URL and auth hints in the setup safety/connections step
- removal of incomplete advanced auth setup from the wizard
- route-owned starter-pack review summary captured during setup
- expanded post-setup handoff card with starter command, approval mode, and connection summaries
- focused Vitest coverage for the wizard step, handoff card, and route state

### Out of scope

- backend validation changes for persona connections
- new connection schema fields
- full reuse of `ConnectionsPanel` inside setup
- persistent post-setup review state after dismissal or reload
- new voice runtime or setup analytics work

## Design Principles

- Keep setup forgiving. Only clearly malformed input should block progress.
- Keep setup shallow. Advanced connection editing remains in `ConnectionsPanel`.
- Keep review accurate. Handoff summaries should come from the setup run, not be re-derived from mutable persona state.
- Keep completion compact. The handoff card should summarize and route, not become a second wizard.

## Key Review Fixes Incorporated

### 1. Route-owned review summary

The route currently stores only:

- `targetTab`
- `completionType`

That is not enough to render a starter-pack review. This design adds a route-owned `setupReviewSummary` payload that is captured during the setup run and frozen into the handoff state at completion.

### 2. No false warning on endpoint paths

Wizard connection validation should not imply that a URL path is suspicious by default. Webhook-style integrations commonly use endpoint paths. Path, query, and fragment should be treated as informational notes, not warnings or blockers.

### 3. Remove incomplete advanced auth from setup

The wizard currently offers `custom_header` auth but does not collect the header name/template needed to make it useful. That is an advanced Connections concern, not a setup concern. This design removes `custom_header` from the setup step so the step stays honest.

### 4. Keep hints separate from backend step errors

Wizard validation hints should stay component-local and should not reuse the route’s setup step error channel. Backend save failures and local form hints are different UX states and should remain separate.

## Product Shape

This slice adds two adjacent improvements on top of the existing setup flow.

First, the safety/connections step becomes more guided. Users should get immediate feedback about malformed URLs, secret expectations, and whether they are creating a likely public or authenticated connection.

Second, the post-setup handoff becomes a small review surface. Instead of only saying setup is complete, it should show what setup actually produced:

- starter commands
- approval mode
- connection outcome

From there, users can jump directly into Commands, Profiles, Connections, or Test Lab.

## Connection Validation Hints

### Validation model

The setup step should add a small local validation model:

- `Base URL` must parse as `http:` or `https:`
- malformed or unsupported URLs block continue
- URL path/query/fragment produce an informational note only
- `authType === "bearer"` with an empty secret produces a non-blocking warning
- `authType === "none"` produces a neutral note that this is best for public endpoints

Because the setup step will no longer expose `custom_header`, it does not need to hint about missing header templates there.

### Continue behavior

Continue should be blocked only when:

- confirmation mode is unset
- connection mode is unset
- connection creation is selected and either:
  - name is empty
  - base URL is empty
  - base URL is malformed or non-http(s)

Continue should remain enabled when:

- the URL is valid but includes a path/query/fragment
- `bearer` auth is selected without a secret

### UI behavior

Add component-local derived validation state in `SetupSafetyConnectionsStep.tsx`:

- inline URL message below the Base URL field
- inline auth message below the auth selector or secret field
- a compact setup hint footer when the form is otherwise valid

Example copy:

- `URL looks valid.`
- `This endpoint includes a path, which is common for webhook-style integrations.`
- `This connection will be created without a bearer token. You can add one later in Connections.`
- `No authentication selected. Use this only for public endpoints.`

### Advanced auth boundary

The setup step should only offer:

- `none`
- `bearer`

`custom_header` remains available in the full `ConnectionsPanel`, where users can provide headers and test the connection properly.

## Starter Pack Review

### Review summary content

The post-setup handoff card should expand with a `Starter pack review` section. It should show three review rows:

- `Starter commands`
- `Approval mode`
- `Connection`

Each row should contain:

- a short summary line
- a focused jump action

Examples:

- `Starter commands: Added 3 starter commands` -> `Review commands`
- `Approval mode: Ask for destructive actions` -> `Review safety defaults`
- `Connection: Connection added: Slack Alerts` -> `Open connections`

If a setup run skipped one area, the summary should say so explicitly:

- `Starter commands: Skipped starter commands`
- `Connection: No external connection yet`

### Handoff card structure

The card should still open on the intended destination tab after setup completion. The new layout should be:

1. completion heading
2. completion path line
3. starter-pack review section
4. bottom action row

Bottom actions should remain compact:

- one context-sensitive primary action based on target tab
- `Open Test Lab`
- `Dismiss`

## Route State And Data Flow

### `setupReviewSummary`

Add a route-owned transient structure, captured during the setup run:

```ts
type SetupReviewSummary = {
  starterCommands:
    | { mode: "added"; count: number }
    | { mode: "skipped" }
  confirmationMode: PersonaConfirmationMode | null
  connection:
    | { mode: "created"; name: string }
    | { mode: "skipped" }
}
```

### Capture points

Populate it from setup flow decisions that already occur in the route:

- command step:
  - record whether starter commands were added or skipped
  - if added, capture the number added in that run
- safety step:
  - record `confirmationMode`
  - record whether a connection was created and its display name
- completion:
  - freeze the current `setupReviewSummary` into `setupHandoff`

### Handoff state

Extend the handoff state to include:

```ts
type SetupHandoffState = {
  targetTab: PersonaGardenTabKey
  completionType: "dry_run" | "live_session"
  reviewSummary: SetupReviewSummary
}
```

This handoff state remains transient:

- created on setup completion
- rendered only on the intended target tab
- cleared on dismiss or handoff navigation action

### Why review state should be transient

The review surface is about what happened in the just-completed setup run. It does not need backend persistence because:

- it is informational, not configuration
- persona state can change after setup
- the handoff card already has transient dismissal semantics

## Component Changes

### `SetupSafetyConnectionsStep.tsx`

Add:

- derived local URL validation
- derived auth hint text
- filtered auth options (`none`, `bearer`)
- non-blocking notes for valid endpoint-style URLs

Do not:

- add full header editing
- call the backend for preflight validation

### `PersonaSetupHandoffCard.tsx`

Expand props to accept:

- `reviewSummary`
- `onOpenConnections`

Render:

- review section
- row-level summary/action pairs
- existing completion and dismissal actions

### `sidepanel-persona.tsx`

Extend route-owned setup state with:

- in-progress `setupReviewSummary`
- handoff `reviewSummary`

Update:

- starter command step handlers
- safety step handler
- setup completion handler
- handoff open actions to include Connections

## Error Handling

### Local validation hints

These are not setup step errors. They should:

- update immediately as the user edits fields
- never replace a backend save error message
- clear naturally when input changes

### Backend errors

Backend creation/save failures stay in the existing setup step error flow. The new hinting layer should not interfere with:

- saving state
- retry behavior
- step-scoped route errors

## Testing

### `SetupSafetyConnectionsStep.test.tsx`

Add coverage for:

- malformed URL blocks continue
- `ftp:` or other unsupported scheme blocks continue
- valid endpoint-style URL shows note and still allows continue
- bearer-without-secret shows warning and still allows continue
- `custom_header` is no longer offered in setup

### `PersonaSetupHandoffCard.test.tsx`

Add coverage for:

- starter-pack review section renders
- starter command summary row
- approval mode summary row
- connection summary row
- `Open connections` action is available when review is rendered

### `sidepanel-persona.test.tsx`

Add route coverage for:

- starter command choice updates review summary
- safety step choice updates review summary
- completion freezes `reviewSummary` into `setupHandoff`
- handoff card routes to Connections, Commands, Profiles, and Test Lab correctly

## Recommended Smallest Coherent Scope

The smallest shippable version of this slice is:

1. shallow connection validation hints in the setup step
2. removal of `custom_header` from setup
3. route-owned setup review summary
4. expanded starter-pack review in the handoff card
5. focused component and route tests

That is enough to materially improve both the setup step and the completion experience without introducing new backend work or another setup flow.
