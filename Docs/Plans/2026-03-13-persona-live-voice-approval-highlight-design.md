# Persona Live Voice Approval Highlight Design

## Goal

Make `Persona Garden -> Live Session` easier to navigate once the user presses
`Jump to approval` by:

- highlighting the currently guided runtime approval row
- keeping that highlight visible while the approval is still pending
- automatically advancing the highlight to the next pending approval after the
  current one is answered
- briefly showing that the last highlighted approval was answered before the
  guidance clears

## Scope

This slice is limited to:

- `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- the existing `AssistantVoiceCard` jump action
- route tests in
  `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

This slice does not add:

- backend changes
- new websocket events
- duplicate approval controls in the Live card
- hook-owned approval state

## Problem Statement

The current approval-clarity slice already tells the user that the assistant is
waiting for approval and provides `Jump to approval`. But after the jump lands,
the runtime approval card is still visually flat. With multiple queued approvals,
the user can lose track of which row the Live card was referring to.

The earlier design revision uncovered three implementation constraints:

1. approval rows are removed immediately on approve/deny
2. the Live card summary still follows `pendingApprovals[0]`
3. jump currently targets the card root, not a specific row

So a simple `highlightedApprovalId` is not enough. The route needs a slightly
richer state model.

## Chosen Approach

Keep approval guidance entirely route-owned in `sidepanel-persona.tsx` with two
pieces of ephemeral UI state:

- `activeApprovalKey: string | null`
- `resolvedApprovalSnapshot: { key: string; toolName: string } | null`

The queue itself remains `pendingApprovals`.

The route should derive:

- the Live-card summary from `activeApprovalKey` when it exists and still points
  to a pending row
- the jump target from that same active row
- the transient answered state from `resolvedApprovalSnapshot`

This keeps the summary text, highlighted row, and jump destination aligned.

## Review Adjustments

### The Highlight Must Follow A Real Pending Row

The guided approval should not float independently from the queue. If
`activeApprovalKey` exists and still matches a pending row, that row is the
single source of truth for:

- the Live-card summary text
- the row highlight styling
- the jump target and focus behavior

If it no longer exists, the route should choose the next first pending approval.

### Answered Fade Needs Separate Snapshot State

Because approval rows are removed immediately after submission, a post-answer
visual cannot be implemented with only row-local highlight classes.

So when the highlighted row is answered:

- capture a small `resolvedApprovalSnapshot`
- render a compact answered banner inside the runtime approval card when there
  are no more pending approvals
- clear that snapshot after a short timeout

This preserves the “auto-fade once answered” requirement without changing queue
removal semantics.

### Jump Must Target The Active Row, Not Just The Card

The previous jump focused the first approve button in the card root. That is no
longer sufficient once the guided approval can differ from `pendingApprovals[0]`
in future queue transitions.

The route should maintain per-row refs or a keyed row lookup so
`handleJumpToRuntimeApproval()` can:

1. locate the active row
2. scroll that row into view
3. focus its first approve button when possible
4. fall back to the card root only if the row ref is unavailable

### Reused Approval Keys Need Defensive Clearing

Approval identity is derived from session, scope, tool, plan, and step. That is
stable enough for queue tracking, but the same key may reappear later in the same
session. If a key reappears while a resolved snapshot for that key still exists,
the route must clear the old snapshot immediately so stale “answered” styling does
not attach to a new request.

## Route Design

### New Route State

Add ephemeral UI state to `sidepanel-persona.tsx`:

- `activeApprovalKey: string | null`
- `resolvedApprovalSnapshot: { key: string; toolName: string } | null`
- `resolvedApprovalFadeTimerRef`
- a keyed `Map<string, HTMLDivElement | null>` or callback-ref registry for
  approval rows

These states are session-scoped guidance only. They must clear on:

- disconnect
- reconnect/session reset
- force-close paths

### Active Approval Selection Rules

When `Jump to approval` is pressed:

- if `pendingApprovals` is empty, no-op
- otherwise set `activeApprovalKey` to the first pending approval key

When `pendingApprovals` changes:

- if `activeApprovalKey` still exists in the queue, keep it
- if it no longer exists and there are pending approvals, move it to the new
  first pending approval
- if the queue is empty, clear `activeApprovalKey`

This ensures new approvals do not steal focus from the currently guided row, but
resolved rows automatically advance the guidance.

### Live Summary Derivation

The Live-card summary should no longer be derived directly from
`pendingApprovals[0]`.

Instead:

- find the pending row matching `activeApprovalKey`
- if present, derive the summary from that row and count the remaining pending
  approvals behind it
- if no active row exists but there are pending approvals, fall back to the first
  pending row

Summary format remains:

- `Waiting for approval: knowledge.search`
- `Waiting for approval: knowledge.search (+1 more)`

### Submission And Resolved Snapshot Flow

When `submitApprovalDecision()` succeeds:

- if the answered approval matches `activeApprovalKey`, capture
  `resolvedApprovalSnapshot`
- then remove the approval from `pendingApprovals` as today
- if another pending approval remains, the active key advances automatically and
  the resolved snapshot should clear immediately
- if no pending approvals remain, show the answered banner for a short interval,
  then clear it

If the same approval key later reappears, clear any matching resolved snapshot
before rendering the new row.

## UI Design

### Runtime Approval Row Highlight

Each approval row in `runtimeApprovalCard` should expose:

- `data-approval-key`
- `data-highlighted="true"` for the active row

Highlighted row treatment:

- stronger warning border
- slightly stronger tinted background
- `Needs your approval` badge

The highlight appears only after the user has used `Jump to approval`.

### Answered Fade

If the last highlighted approval is answered and the queue becomes empty, render
a compact transient banner inside the runtime approval card:

- `Answered: knowledge.search`

The banner should use a success/settled style and disappear after the fade timer
clears the snapshot.

This avoids trying to keep a removed row on screen.

### Jump Behavior

`Jump to approval` remains in `AssistantVoiceCard`, but the route-owned handler now:

- ensures `activeApprovalKey` is set
- targets the matching row ref
- scrolls that row into view
- focuses the row’s approve button when possible

If the row ref is unavailable, it may fall back to the card root.

## Testing

### Route Coverage

Add route tests proving:

- `Jump to approval` highlights the first pending approval row
- approving the highlighted row advances the highlight to the next pending row
- denying the highlighted row also advances correctly
- new approvals do not steal highlight from the current active row
- the Live summary follows the active guided approval
- resolving the last highlighted row shows the answered banner, then clears it
- reconnect/disconnect clears active highlight guidance

### DOM Assertions

Use stable assertions such as:

- `data-highlighted="true"`
- `data-approval-key="..."`
- presence of `Needs your approval`
- presence and later removal of `Answered: {tool}`

### Timing

Use fake timers for the answered fade so the tests are deterministic.

## Success Criteria

- `Jump to approval` lands on a specific approval row, not just the card.
- The highlighted row stays visible until the user answers it.
- After the highlighted approval is answered, guidance moves to the next pending
  approval automatically.
- When the last highlighted approval is answered, the user sees a brief answered
  confirmation before the guidance clears.
- The Live-card summary, highlight target, and jump behavior stay aligned.
