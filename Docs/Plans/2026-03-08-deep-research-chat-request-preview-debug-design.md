# Deep Research Chat Request Preview And Debug Design

**Date:** 2026-03-08

## Goal

Make attached deep research context visible and editable in the composer request preview and chat debug tooling without creating a second source of truth or polluting chat transcript state.

## User-Facing Outcome

For v1:

- the existing raw request preview modal shows a structured `Attached Research Context` panel whenever chat has an active attached research context
- users can inspect exactly which bounded research fields will be sent on the next standard chat request
- users can edit the bounded attached context from that panel and apply those edits back to the active chat attachment
- the composer chip, request preview, and outbound request all reflect the same active attached context
- users can reset the edited attachment back to the last run-derived snapshot
- the raw request JSON remains available as an inspection surface below the structured panel

## Non-Goals

This slice does not include:

- backend API or schema changes
- direct raw-JSON editing of `research_context`
- persistence of edited attached context across reloads
- editing the underlying research run or bundle
- multiple simultaneous attached research contexts
- transcript messages for attachment changes
- request preview editing for image-generation or compare-mode request paths

## Constraints From The Current Codebase

The current code already provides:

- session-scoped attached research context in `Playground.tsx`
- bounded normalization helpers in `research-chat-context.ts`
- request-path injection of `research_context` for standard chat sends
- suppression of `research_context` for image-command and compare-mode paths
- an existing raw request preview modal in `PlaygroundForm.tsx`
- a raw request debug snapshot helper in `chat-request-debug.ts`

The current code does **not** provide:

- a structured preview of attached research context in the request modal
- a way to edit the active attached research context outside the composer chip remove action
- a reset path back to the original run-derived attached snapshot
- any explicit preview/debug affordance showing when `research_context` is being suppressed for nonstandard request flows

Those gaps define the shape of this slice.

## Architecture

### 1. Single Source Of Truth

Keep the active attached research context in the existing session-scoped playground state owned by `Playground.tsx`.

The request preview/debug modal must not own a separate durable copy of the attachment. It can hold temporary form edits while open, but `Apply` must update the same active attached-context state that the composer chip and request builder already use.

That means:

- no debug-only attachment model
- no raw JSON patch state
- no divergence between what the chip says is attached and what the next request will send

### 2. Structured Editing Over The Existing Bound Contract

Editing should stay inside the same bounded attached-context contract already used for request payloads.

Editable fields:

- `question`
- `outline` section titles
- `key_claims` text list
- `unresolved_questions` list
- `verification_summary.unsupported_claim_count`
- `source_trust_summary.high_trust_count`

Read-only identity fields:

- `run_id`
- `query`
- `research_url`
- `attached_at`

List editing uses full replacement in the UI. Empty list items are stripped on apply. This keeps the model simple and prevents the modal from growing a mini patch language.

### 3. Run-Derived Reset Baseline

The editor needs a stable reset target that is not the user’s most recent edits.

Store or derive a `run-derived attachment snapshot` alongside the active attached context in the live playground state. `Reset to Attached Run` restores from that baseline. `Apply` only updates the active attached context, not the baseline.

This gives users a safe editing loop:

- attach completed research
- trim/curate it for chat use
- reset back to the original bounded run snapshot if needed

### 4. Extend The Existing Raw Request Modal

Do not add a second debug surface.

The existing raw request modal in `PlaygroundForm.tsx` should become the single preview/debug surface for this feature:

- top section: structured attached research panel
- middle: request metadata already shown today
- bottom: existing raw request JSON textarea

If there is no active attachment, the panel stays hidden or shows a neutral empty state. The modal remains useful even without research context.

### 5. Composer Preview Entry Point

Add a lightweight `Preview` or `Edit` action to the attached-context chip so users can reach the modal directly from the composer area.

This keeps the composer chip as the quick status/remove surface and the modal as the deeper inspect/edit surface.

### 6. Behavior For Nonstandard Requests

The request preview must stay honest about suppression rules already implemented for image-command and compare-mode flows.

If the current preview path resolves to a request where `research_context` would be suppressed:

- the structured panel still shows the active attachment
- the preview indicates that the current request path will not include it
- the raw request JSON omits `research_context`

This avoids a confusing mismatch where users see an attached context but cannot tell why it is missing from a particular preview.

### 7. Thread-Switch Safety

Because attached context is session-scoped to the current thread, the modal editor must invalidate on thread changes.

If `serverChatId` or `historyId` changes while the modal is open:

- clear the editor state
- close the modal or reset it to the new thread state
- do not allow stale edits to apply to a different thread

This matches the existing “clear attached context on thread switch” rule.

## Component Changes

### `research-chat-context.ts`

Add small pure helpers for:

- sanitizing edited attached context into the bounded shape
- stripping empty list entries
- applying read/write field updates while preserving read-only identity fields
- comparing active attachment to the run-derived baseline if needed

Keep these helpers pure so both the chip and the modal can reuse them without UI coupling.

### `Playground.tsx`

Extend the attached research state to track:

- current active attached context
- run-derived baseline attached context for reset

When `Use in Chat` attaches a new run, both values are set to the same initial bounded snapshot. When the user edits via preview/debug, only the active value changes.

### `PlaygroundForm.tsx`

Extend the raw request modal with:

- a structured attached-research editor panel
- local edit state initialized from the active attachment
- `Apply`
- `Reset to Attached Run`
- `Copy JSON`
- optional inline note when the current preview suppresses `research_context`

The existing `Refresh` action continues to rebuild the raw request snapshot from the latest active state.

### `AttachedResearchContextChip.tsx`

Add a lightweight action to open the preview/debug modal. Keep `Remove` and `Open in Research` semantics unchanged.

## Testing Strategy

Frontend-only coverage should prove:

- the raw request modal renders the structured research panel when an attachment exists
- `Apply` updates the active attached context and the composer chip
- `Reset to Attached Run` restores the run-derived baseline
- refreshed raw JSON reflects the edited attachment
- no structured panel renders when no attachment exists
- image/compare preview paths still omit `research_context`
- thread switches invalidate editor state and do not leak edits

The request-preview tests should stay close to the existing playground integration seam rather than introducing a separate test harness for the modal alone.

## Risks And Mitigations

### Risk: Two Sources Of Truth

If the modal owns attachment state independently from the chip, the preview and the next request can drift.

Mitigation:

- keep active attached context in `Playground.tsx`
- make modal edits apply through that same state setter

### Risk: Users Think They Are Editing The Research Run

The preview/debug panel edits only the chat-attached subset, not the completed research result.

Mitigation:

- label the panel as `Attached Research Context`
- keep `run_id` and `query` read-only
- provide `Reset to Attached Run`

### Risk: Preview Surface Gets Too Busy

The modal already shows raw request metadata and JSON.

Mitigation:

- keep the structured panel compact
- limit editing to bounded fields only
- preserve raw JSON as secondary, not primary, content

## Success Criteria

This slice is complete when:

- users can inspect the active attached research context from the composer/debug surface
- users can edit the bounded chat-attached subset and apply it as the new active attachment
- the composer chip and raw request preview stay in sync
- nonstandard request previews remain explicit about suppressing `research_context`
- no backend changes are required
