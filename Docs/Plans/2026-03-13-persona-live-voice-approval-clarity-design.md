# Persona Live Voice Approval Clarity Design

## Goal

Make `Persona Garden -> Live Session` stay legible when a tool pauses for runtime approval by:

- surfacing a compact approval-waiting summary in the Live voice card
- letting the user jump directly to the existing runtime approval controls already rendered lower in the same Live panel

## Scope

This slice is limited to:

- the Persona Garden route in `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- the Live voice card in `apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx`
- the existing Live Session layout in `apps/packages/ui/src/components/PersonaGarden/LiveSessionPanel.tsx`

This slice does not add:

- duplicate approve/deny controls in the Live card
- new backend approval events
- changes to approval submission semantics
- hook-owned approval state

## Problem Statement

When a `tool_result` carries runtime approval metadata, the route already captures that request and renders `runtimeApprovalCard` in the Live panel. But the `AssistantVoiceCard` at the top of the Live tab becomes visually quiet after the tool stops running. The user has to infer that work is now blocked on approval by scanning lower in the panel stack.

That is functionally correct, but it is not straightforward.

## Chosen Approach

Keep approval state route-owned and derive a compact Live-card summary from the existing `pendingApprovals` queue.

The summary should:

- name the first visible approval already shown in `runtimeApprovalCard`
- include a count suffix for additional approvals
- render in the Live card as:
  - `Waiting for approval: search_notes`
  - or `Waiting for approval: search_notes (+1 more)`
- expose a `Jump to approval` action that scrolls to and focuses the existing approval card in the same Live tab

## Review Adjustments

### Existing Queue Order Is The Source Of Truth

`pendingApprovals` is built in arrival order and the route-level `runtimeApprovalCard` renders that same array order.

So the approval summary should explicitly mean:

- the first visible approval in the existing runtime approval card
- plus a count of additional approvals behind it

This keeps the Live summary aligned with the card the user jumps to.

### Render-Time Precedence, Not Shared State Mutation

Approval state lives in the route.

Tool progress state lives in `usePersonaLiveVoiceController`.

The Live card should not try to synchronize those by mutating hook state. Instead:

- if `pendingApprovalSummary` exists, render it instead of `activeToolStatus`
- otherwise render `activeToolStatus` when present

That keeps responsibilities clean and avoids a fragile route-to-hook sync path.

### Jump Must Feel Deliberate

`scrollIntoView()` alone can be too subtle if the approval card is already partially visible.

The jump action should:

1. scroll the runtime approval card into view
2. focus the first actionable approval control when possible

That gives the user a visible “landing point” after pressing the button.

### Approval Summary Lifecycle Must Be Tested

The summary should not just render once. It must update as the queue changes:

- first approval arrives
- more approvals accumulate
- first approval is approved/denied and removed
- summary updates to the next approval or disappears when the queue is empty

## Route Design

### Derived Summary

In `sidepanel-persona.tsx`, derive a compact summary from `pendingApprovals`.

Suggested shape:

- `count: number`
- `primaryToolName: string`
- `summaryText: string`

Rules:

- no approvals: `null`
- one approval: `Waiting for approval: {tool}`
- multiple approvals: `Waiting for approval: {tool} (+{count - 1} more)`

### Jump Target

Add a stable ref and test id to the runtime approval card root.

Suggested behavior for `handleJumpToRuntimeApproval()`:

- if no pending approvals or no card ref, no-op
- call `scrollIntoView({ block: "start", behavior: "smooth" })`
- then try to focus the first actionable button inside the card, preferring the first approve button
- fail silently if scroll/focus APIs are unavailable

### Existing Approval Flow Stays Unchanged

Keep:

- request creation from `tool_result.approval`
- queue updates
- approve/deny submission
- queue removal after resolution

This slice is visibility and navigation only.

## Live Card Design

### New Props

Add route-owned props to `AssistantVoiceCard`:

- `pendingApprovalSummary: string | null`
- `onJumpToApproval: () => void`

### Rendering Rules

Status precedence becomes:

1. warning banner
2. approval summary status
3. active tool status
4. recovery panels

The approval status block should:

- reuse the same `Current action` label
- show `pendingApprovalSummary`
- show `Jump to approval` as a small secondary button

Only render the button when a summary exists.

### No Duplicate Controls

The Live card remains a compact handoff surface.

It should not render:

- approve/deny buttons
- duration selectors
- argument summaries

Those stay in the existing `runtimeApprovalCard`.

## Testing

### Component

Add coverage proving:

- approval summary renders in the Live card
- approval summary hides `activeToolStatus`
- `(+N more)` formatting appears for multiple approvals
- `Jump to approval` triggers the handler

### Route

Add coverage proving:

- an approval-producing `tool_result` causes the Live card summary to appear
- `Jump to approval` scrolls to the existing runtime approval card
- focus lands on the first approval action when possible
- after approving or denying the first request, the summary updates to the next request or disappears

## Success Criteria

- The Live card explicitly says when the assistant is waiting for approval.
- The summary matches the first visible approval in the existing runtime approval card.
- `Jump to approval` moves the user to the real approval controls without leaving the Live tab.
- No duplicate approval editor is introduced.
