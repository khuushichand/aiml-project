# Persona Live Voice Approval Motion Design

## Goal

Make the guided runtime approval row in `Persona Garden -> Live Session` feel
more deliberate by adding:

- a strong landing pulse when `Jump to approval` is used
- a smaller follow-up pulse when guidance auto-advances to the next approval
- a steady highlighted state after either pulse settles
- a full fallback to static highlight under `prefers-reduced-motion`

## Scope

This slice is limited to:

- `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- the existing route-owned runtime approval row rendering
- route tests in
  `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

This slice does not add:

- backend changes
- new websocket events
- changes to the Live card layout
- changes to the answered-banner behavior

## Problem Statement

The current approval-highlight slice already:

- aligns the Live summary with the guided approval
- scrolls/focuses the active approval row
- keeps a steady highlighted state while guidance is active
- auto-advances to the next pending approval

That is correct, but the landing itself is still visually abrupt. After
`Jump to approval`, or when guidance advances to the next pending row, the user
gets a static state change but not much motion feedback.

The next slice should make that guidance easier to notice without becoming noisy.

## Chosen Approach

Keep the state model route-owned in `sidepanel-persona.tsx` and add a small
visual phase model for the active approval row:

- `landing_primary`
- `landing_secondary`
- `steady`

The route continues to own:

- `activeApprovalKey`
- queue advancement
- row-targeted jump/focus
- session cleanup

The new phase is presentation-only and should not affect queue semantics.

## Review Adjustments

### Explicit Phase State Is Better Than CSS Guesswork

The active approval row can persist across queue updates, so relying on DOM
re-mounting or class reapplication is too brittle for re-triggering animation.

Instead, the route should explicitly store a highlight phase and a small replay
token or sequence number so:

- `Jump to approval` can always replay the primary pulse
- auto-advance can intentionally trigger the smaller secondary pulse
- reduced-motion can skip the animation while keeping the same state contract

### The Pulse Should Not Replace The Steady Highlight

The current steady highlighted row is already doing useful work. The pulse should
sit on top of it, then decay into the same steady state.

That means:

- no layout changes
- no row movement
- no size changes
- only ring/glow/background-emphasis changes

### Auto-Advance Should Feel Different From Manual Jump

The user asked for:

- a full landing pulse on the initial jump
- a smaller pulse when the highlight auto-advances after an approval is answered

So the visual system should preserve two distinct pulse strengths:

- `landing_primary` after `Jump to approval`
- `landing_secondary` after queue progression

### Reduced Motion Must Collapse To Static Guidance

Under `prefers-reduced-motion: reduce`:

- the row should still become the active highlighted row
- no pulse animation should run
- tests should still assert the phase assignment, not animation playback

That keeps behavior accessible without inventing a second logic path.

## Route Design

### New Visual State

Add route-owned visual-only state in `sidepanel-persona.tsx`, for example:

- `approvalHighlightPhase: "none" | "landing_primary" | "landing_secondary" | "steady"`
- `approvalHighlightSequence: number`
- `approvalHighlightTimerRef`

The active row should derive a `data-highlight-phase` value only when:

- the row key matches `activeApprovalKey`

Suggested row rendering:

- inactive row: `data-highlighted="false"`
- active row during jump pulse: `data-highlighted="true" data-highlight-phase="landing_primary"`
- active row during auto-advance pulse:
  `data-highlighted="true" data-highlight-phase="landing_secondary"`
- active row after settling:
  `data-highlighted="true" data-highlight-phase="steady"`

### Trigger Rules

When `Jump to approval` is pressed:

- set or keep `activeApprovalKey`
- set `approvalHighlightPhase` to `landing_primary`
- increment `approvalHighlightSequence`
- schedule phase settle to `steady`

When the active approval resolves and another pending approval becomes active:

- set the new `activeApprovalKey`
- set `approvalHighlightPhase` to `landing_secondary`
- increment `approvalHighlightSequence`
- schedule phase settle to `steady`

When the active approval resolves and no next approval remains:

- clear the highlight phase with the existing guidance cleanup
- answered-banner behavior remains unchanged

When disconnect/reconnect/session reset occurs:

- clear phase state
- clear timers

### Replay Semantics

Repeated `Jump to approval` on the same active row should still replay the
primary pulse.

The easiest way to guarantee that is to tie the active row to both:

- `data-highlight-phase`
- `data-highlight-seq`

The sequence token gives tests and rendering a stable signal that the pulse was
retriggered intentionally.

## Styling Design

### Visual Behavior

Base active row:

- existing warning border/background
- existing `Needs your approval` badge

`landing_primary`:

- stronger temporary ring or shadow
- more visible glow
- short duration

`landing_secondary`:

- smaller ring or softer glow
- shorter or subtler than the primary pulse

`steady`:

- no pulse animation
- keep the existing highlighted state

### Styling Constraints

The pulse should:

- not affect layout
- not move neighboring rows
- not animate size or position
- use color/shadow/outline emphasis only

### Reduced Motion

Add a reduced-motion rule so these phase classes:

- keep the row in the active highlighted style
- disable animation and transition effects

## Testing

### Route Tests

Add route coverage for:

- `Jump to approval` sets `data-highlight-phase="landing_primary"` on the active row
- repeated `Jump to approval` on the same row increments the replay token
- after the pulse settles, the active row becomes `data-highlight-phase="steady"`
- auto-advance sets `data-highlight-phase="landing_secondary"` on the new row
- reconnect/disconnect clears the phase attributes

### Deterministic Timing

Use fake timers for the settle-to-steady assertions.

Tests should assert:

- phase value
- sequence token changes when the pulse replays

They should not attempt to assert computed CSS animation behavior.

## Success Criteria

- `Jump to approval` produces a visible landing pulse on the guided row.
- Auto-advancing to the next pending approval produces a smaller pulse.
- Both pulses settle into the existing steady highlighted state.
- Repeated jump actions replay the primary pulse intentionally.
- Reduced-motion users get the same guided row without animation.
