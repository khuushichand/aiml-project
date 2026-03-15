# Persona Setup Handoff Target Reached Analytics Design

**Date:** 2026-03-14

## Goal

Add one analytics-only follow-up to the setup handoff system so Persona Garden
can measure whether a handoff click actually lands the user on the intended
panel section.

This slice should:

- emit `handoff_target_reached` when a setup handoff focus request is actually
  consumed by a destination panel
- dedupe that event by setup run and concrete target identity
- extend setup analytics summaries with both run-level and per-target reach
  metrics

## Why This Slice Exists

The current setup funnel already records:

- `handoff_action_clicked`
- `handoff_dismissed`
- `first_post_setup_action`

The recent handoff-target work now makes the UI land on exact sections inside:

- `Commands`
- `Profiles`
- `Connections`
- `Test Lab`

But there is still one analytics blind spot:

- we know a handoff action was clicked
- we know whether a later success happened
- we do not know whether the destination section was actually reached

That makes it hard to tell whether failures are caused by:

- weak CTA selection
- bad section-target delivery
- or poor follow-through after landing

## Scope

### In scope

- one new setup analytics event type: `handoff_target_reached`
- route-owned emission when a focus token is consumed
- target-aware setup event dedupe keys
- backend summary aggregation for run-level and per-target reach
- focused frontend/backend tests

### Out of scope

- UI changes
- new banners or visible “landed here” cues
- runtime voice analytics changes
- a new analytics dashboard
- any `Live Session` target-reached event

## Review-Driven Constraints

### 1. Dedupe must be target-aware

The existing setup analytics helper only builds stable keys from:

- `eventType`
- `step`
- `detourSource`

That is not sufficient for `handoff_target_reached`. Different destinations
like:

- `commands.command_form`
- `profiles.confirmation_mode`
- `connections.saved_connections`

would collapse incorrectly unless the key includes the concrete target.

### 2. Emission should remain route-owned

Panels already report token consumption through
`onSetupHandoffFocusConsumed(token)`.

That is the right boundary:

- panels own refs, focus, and readiness
- the route owns setup handoff state and analytics emission

This slice should not copy analytics posting logic into each panel.

### 3. The route must emit from a request snapshot

`handleSetupHandoffFocusConsumed(token)` currently clears the active request.
If analytics is built from state after that clear, the route can lose:

- target tab
- section
- connection item detail

So emission must use a snapshot of the matched request before state is cleared.

### 4. V1 should track target-level usefulness

A single run-level boolean is not enough. The point of this slice is to learn
which anchored destinations help.

That means the backend summary should expose:

- run-level `handoff_target_reached`
- per-target counts such as:
  - `commands.command_form`
  - `commands.command_list`
  - `profiles.confirmation_mode`
  - `profiles.assistant_defaults`
  - `connections.connection_form`
  - `connections.saved_connections`
  - `test-lab.dry_run_form`

### 5. The reach rate should be conditional

`handoff_target_reach_rate` should be:

- runs with at least one `handoff_target_reached`
- divided by runs with `handoff_action_clicked`

It should not use all setup runs as the denominator, because many runs never use
the handoff at all.

## Chosen Approach

Add a new append-only setup event type, emit it from the route when a panel
consumes a handoff token, and aggregate both run-level and per-target reach
metrics in the existing persona setup analytics summary.

Concretely:

1. Extend setup analytics event enums with `handoff_target_reached`.
2. Extend the event-key helper so this event dedupes by concrete target.
3. In the route, emit once when a matching focus request is consumed.
4. Persist the event through the existing setup-events endpoint/table.
5. Aggregate both:
   - `handoff_target_reached` boolean per run
   - `handoff_target_reached_counts` per target
   - `handoff_target_reach_rate` across runs with a handoff click

This keeps the slice small, measurable, and consistent with the current setup
analytics pipeline.

## Event Model

### New event type

Add:

```ts
"handoff_target_reached"
```

to the shared setup analytics event type lists in frontend and backend.

### Event payload

Reuse existing fields:

- `run_id`
- `event_type`
- `action_target`
- `metadata`

For this event, define:

- `action_target`: stable destination key such as:
  - `commands.command_form`
  - `commands.command_list`
  - `profiles.confirmation_mode`
  - `profiles.assistant_defaults`
  - `connections.connection_form`
  - `connections.saved_connections`
  - `test-lab.dry_run_form`
- `metadata`: optional target item detail when present
  - `connection_id`
  - `connection_name`
  - `recommended_action`
  - `completion_type`

This avoids adding new top-level schema fields for a narrow analytics event.

### Event key

The key for `handoff_target_reached` should be target-aware:

```ts
handoff_target_reached:${actionTarget}
handoff_target_reached:${actionTarget}:${connectionId}
handoff_target_reached:${actionTarget}:${connectionName}
```

Use item identity only for cases where one generic target can refer to multiple
frozen entities, specifically `connections.saved_connections`.

That gives once-only semantics per concrete destination for one setup run.

## Route Behavior

### Emission point

Keep emission in `sidepanel-persona.tsx`.

When `handleSetupHandoffFocusConsumed(token)` is called:

1. find the active `setupHandoffFocusRequest`
2. ignore the callback if the token does not match
3. build an analytics snapshot from the request before clearing it
4. emit `handoff_target_reached`
5. clear the request

### Action target formatting

Build `action_target` from the request:

```ts
`${request.tab}.${request.section}`
```

Examples:

- `commands.command_form`
- `connections.saved_connections`

### Metadata

If the request carries item detail, include it in metadata:

```ts
{
  connection_id: request.connectionId ?? undefined,
  connection_name: request.connectionName ?? undefined,
  recommended_action: setupHandoff?.recommendedAction ?? undefined,
  completion_type: setupHandoff?.completionType ?? undefined
}
```

This is advisory analytics detail only. It must not affect handoff behavior.

### What remains excluded

Do not emit `handoff_target_reached` for `live` tab actions. The current
handoff-target slice does not define a section-level focus contract there.

## Backend Aggregation

### Recent runs

Extend each recent run summary with:

- `handoff_target_reached: bool`

This means a run is marked reached if it has at least one
`handoff_target_reached` event.

### Summary metrics

Extend the summary with:

- `handoff_target_reach_rate: float`
- `handoff_target_reached_counts: dict[str, int]`

Definitions:

- `handoff_target_reached_counts[target]`:
  count of runs with at least one reach event for that target
- `handoff_target_reach_rate`:
  `reached_runs / handoff_clicked_runs`

If `handoff_clicked_runs == 0`, the rate is `0.0`.

This preserves the current run-based funnel semantics while still exposing
target-level usefulness.

## Testing Strategy

### Frontend

- service tests for stable event keys:
  - `handoff_target_reached:commands.command_form`
  - `handoff_target_reached:connections.saved_connections:conn-123`
- route test:
  - consuming a matching token posts `handoff_target_reached`
- route dedupe test:
  - repeated consume/re-render for the same token does not post a duplicate

### Backend

- schema/API test:
  - `handoff_target_reached` is accepted by the setup-events endpoint
- analytics summary test:
  - a run with `handoff_action_clicked` and `handoff_target_reached` sets:
    - `handoff_target_reached = true`
    - `handoff_target_reach_rate` correctly
    - target count for the expected `action_target`

## Success Criteria

This slice is complete when:

- setup handoff target consumption emits one append-only analytics event
- duplicate consume callbacks do not create duplicate rows
- setup analytics summaries expose both reach rate and per-target counts
- existing handoff behavior remains unchanged

