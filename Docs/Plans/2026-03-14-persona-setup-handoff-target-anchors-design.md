# Persona Setup Handoff Target Anchors Design

**Date:** 2026-03-14

## Goal

Finish the remaining post-setup handoff gap in Persona Garden by making handoff
actions land on the exact section the user needs, not just the right tab.

This slice should:

- add stable, explicit handoff targets for the existing setup completion card
- let same-tab handoff actions scroll, focus, and briefly highlight the relevant
  section
- preserve the current handoff lifecycle, analytics, and first-success collapse
  behavior

## Why This Slice Exists

The setup wizard, retry flows, detours, handoff persistence, and setup analytics
are now in place. The remaining friction is narrower.

Today:

- the handoff card can recommend `Commands`, `Connections`, `Profiles`, or
  `Test Lab`
- route actions can retarget the handoff to another tab
- the card stays visible until a real post-setup success collapses it

But:

- same-tab actions do not land on the exact section the user should use next
- cross-tab actions still stop at tab navigation, not a concrete destination
- destination panels do not expose a stable contract for “focus this setup
  handoff target”

That makes the current handoff informative, but still slightly indirect.

## Scope

### In scope

- route-owned handoff target requests
- stable focus/scroll targets in `Commands`, `Connections`, `Profiles`, and
  `Test Lab`
- handoff action mapping from review rows and recommended CTA to concrete
  sections
- brief destination highlight to confirm arrival
- focused frontend tests

### Out of scope

- new backend endpoints or analytics schemas
- another setup state model change
- new setup wizard steps
- generic cross-app focus/anchor infrastructure
- live-session runtime behavior changes

## Review-Driven Constraints

### 1. The route should not query the DOM blindly

The route already owns setup handoff state, but it should not start using
`querySelector` against child panel internals. That would be brittle and hard to
test.

This design uses an explicit panel contract instead:

- the route emits a typed focus request
- the active destination panel receives that request as props
- the panel owns the refs, scroll, focus, and temporary highlight

### 2. Targets must be explicit and small

This slice should not invent a generic “scroll to anything” mechanism.

Instead, each relevant panel gets a short, local set of supported targets:

- `Commands`: `command_form`, `command_list`
- `Connections`: `connection_form`, `saved_connections`
- `Profiles`: `assistant_defaults`, `confirmation_mode`
- `Test Lab`: `dry_run_form`

Anything outside that list stays out of scope.

### 3. Same-tab and cross-tab behavior should share one model

The current route already distinguishes:

- same-tab action: keep the handoff visible
- cross-tab action: retarget the handoff to the destination tab

This design keeps that rule and adds one more layer:

- every handoff action may also carry a `section` target
- same-tab actions focus immediately
- cross-tab actions focus after the destination panel mounts

### 4. Handoff clicks are still navigation, not success

This slice must not change the current meaning of
`first_post_setup_action`.

Success remains domain-level:

- command saved
- connection saved
- connection test succeeded
- voice defaults saved
- dry-run match
- live response received

Scrolling to a target or focusing an input does not collapse the handoff.

### 5. No backend changes are needed in V1

The setup analytics work already records:

- handoff clicks
- dismiss
- first post-setup success

That is enough for this slice. It is acceptable to ship the targeting behavior
without adding a new `handoff_target_reached` event yet.

### 6. Async-loaded panels must not consume targets too early

`Commands`, `Connections`, and `Assistant Defaults` all fetch data after mount.
That means a section request can arrive before:

- command rows exist
- saved connection rows exist
- the confirmation-mode select is ready

This design requires panels to keep a request pending until they can either:

- fulfill the requested target, or
- choose a deterministic fallback after load completes

The route must not clear requests on a blind “panel mounted” signal.

## Chosen Approach

Use a route-owned `setupHandoffFocusRequest` model plus panel-local target refs.

Concretely:

1. Add a typed `section` target model for post-setup handoff actions.
2. Teach the route to open a handoff target, not just a tab.
3. Pass the current focus request into the active panel.
4. In each panel, scroll to the requested section, focus the first useful
   control, and show a brief highlight.
5. Keep the existing handoff card visible until a real success event collapses
   it.

This keeps the feature frontend-only, predictable, and easy to test.

## Target Model

### Focus request type

Add a small route-owned request object:

```ts
type SetupHandoffSectionTarget =
  | { tab: "commands"; section: "command_form" | "command_list" }
  | {
      tab: "connections"
      section: "connection_form" | "saved_connections"
      connectionId?: string | null
      connectionName?: string | null
    }
  | { tab: "profiles"; section: "assistant_defaults" | "confirmation_mode" }
  | { tab: "test-lab"; section: "dry_run_form" }

type SetupHandoffFocusRequest = {
  tab: SetupHandoffSectionTarget["tab"]
  section: SetupHandoffSectionTarget["section"]
  token: number
  connectionId?: string | null
  connectionName?: string | null
}
```

`token` is important. It lets the route intentionally replay the same handoff
target twice, for example if the user clicks `Review commands` again while
already on `Commands`.

### Why `live` is excluded

The `Live Session` tab already opens at the relevant control surface. This slice
keeps `live` tab actions as plain tab switches. Only the panels that need
section-level landing behavior get the new contract.

## Handoff Action Mapping

The current handoff card exposes these user actions:

- recommended primary CTA
- `Review commands`
- `Review safety defaults`
- `Open connections`
- `Open Test Lab`

This slice maps them to concrete destinations.

### Recommended CTA

- `add_command` -> `commands.command_form`
- `review_commands` -> `commands.command_list`
- `add_connection` -> `connections.connection_form`
- `try_live` -> plain `live` tab navigation only

### Starter pack review rows

- starter commands row -> `commands.command_list`
- approval mode row -> `profiles.confirmation_mode`
- connection row:
  - `skipped` -> `connections.connection_form`
  - `created` or `available` -> `connections.saved_connections` with the frozen
    connection name, and id when available later
- `Open Test Lab` -> `test-lab.dry_run_form`

This keeps the action model specific to what setup just produced, rather than
one fixed destination per tab.

## Route Behavior

### New route state

Add:

```ts
const [setupHandoffFocusRequest, setSetupHandoffFocusRequest] =
  React.useState<SetupHandoffFocusRequest | null>(null)
```

### Opening a handoff target

Replace `openSetupHandoffTab(tab)` with a slightly richer helper:

```ts
openSetupHandoffTarget(
  target:
    | { tab: "live" }
    | SetupHandoffSectionTarget
)
```

Behavior:

- emit the existing `handoff_action_clicked` analytics event
- switch tabs as needed
- if the target includes a section:
  - increment a token
  - store `setupHandoffFocusRequest`
- preserve the current handoff on same-tab actions
- retarget the handoff to the destination tab on cross-tab actions

### Clearing focus requests

The focus request is transient UI state. It should clear when:

- the persona changes
- setup context changes
- the handoff is dismissed
- the destination panel reports that it has fulfilled or deterministically
  fallen back from the request

It should not clear simply because the handoff remains visible.

Add an explicit route callback, for example:

```ts
onSetupHandoffFocusConsumed(token: number): void
```

The route should ignore stale tokens and only clear the current request when the
reported token matches the active one.

## Panel Contracts

Each panel gets:

```ts
type SetupHandoffPanelTarget<TSection extends string> = {
  section: TSection
  token: number
} | null
```

Panels only react when:

- they are active
- the request token is newer than the last handled token

Panel behavior on a fresh request:

1. scroll the section container into view
2. focus the first useful control inside that section
3. apply a short visual highlight phase
4. notify the route that the request token was consumed

Panels should only consume a token after:

- the requested control is ready, or
- a documented fallback target has been used after load settled

They should not consume tokens just because the panel rendered.

### Commands

Targets:

- `command_form`
- `command_list`

Destination behavior:

- `command_form`: focus `persona-commands-name-input`
- `command_list`: focus the first actionable control in the first command row,
  preferably the `Edit` button; otherwise fall back to the command form

### Connections

Targets:

- `connection_form`
- `saved_connections`

Destination behavior:

- `connection_form`: focus `persona-connections-name-input`
- `saved_connections`: if a target connection id or name is present, focus that
  row’s first actionable control, preferably `Edit`; otherwise focus the first
  saved connection’s `Edit` button; if no saved rows exist, fall back to the
  connection form

### Profiles

Targets:

- `assistant_defaults`
- `confirmation_mode`

Destination behavior:

- `assistant_defaults`: focus the first meaningful control in
  `AssistantDefaultsPanel`, not a passive wrapper
- `confirmation_mode`: focus the confirmation-mode select inside
  `AssistantDefaultsPanel`

This keeps the existing `ProfilePanel` structure, but adds a focused path for
the current `Review safety defaults` action.

### Test Lab

Target:

- `dry_run_form`

Destination behavior:

- focus `persona-test-lab-heard-input`

## Visual Confirmation

Each target section should get a short arrival treatment:

- a stronger border or ring
- subtle background tint
- no layout movement

The highlight should:

- replay when the same target is requested again with a new token
- decay back to the normal state after a short timeout
- disable animation under `prefers-reduced-motion`

This is not a new “success” state. It only confirms that the handoff landed in
the intended place.

## Error Handling And Fallbacks

If a panel cannot satisfy the ideal target:

- it should fall back to the nearest useful section in the same panel
- it should not throw
- it should still consume the request so the route does not keep replaying it

Examples:

- `commands.command_list` with no commands -> focus command form
- `connections.saved_connections` with no saved rows -> focus connection form
- `profiles.confirmation_mode` while defaults are not loaded yet -> focus the
  first meaningful defaults control once the panel is ready; if the select still
  is not available, use the first defaults input as the fallback

## Testing Strategy

### Route tests

In `sidepanel-persona.test.tsx`, cover:

- same-tab handoff action keeps the card visible and emits a focus request
- cross-tab handoff action retargets the card and focuses the destination panel
- `try_live` remains tab-only and does not create a focus request

### Panel tests

Add focused tests that mock `scrollIntoView` and assert the destination control
is focused:

- `CommandsPanel.test.tsx`
- `ConnectionsPanel.test.tsx`
- `AssistantDefaultsPanel.test.tsx`
- `TestLabPanel.test.tsx`

Each should also cover:

- replay via a newer request token
- async-loaded targets that only consume after data is ready
- fallback behavior when the preferred target is unavailable

### Handoff card tests

Only add/adjust tests if the card action wiring changes. The card itself should
remain mostly presentational.

## Success Criteria

This slice is done when:

- each handoff action lands on a concrete destination, not just a tab
- same-tab actions replay cleanly
- the handoff lifecycle and compact-success behavior stay unchanged
- no backend work is required
- focused route and panel tests pass
