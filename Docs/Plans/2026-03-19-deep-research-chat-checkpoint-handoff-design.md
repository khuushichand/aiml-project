# Deep Research Chat Checkpoint Handoff Design

**Goal:** Make checkpoint-needed linked research runs in chat hand users back to `/research` more clearly, without turning chat into a second checkpoint UI.

**Status:** Approved design baseline for implementation planning.

## Summary

Chat already shows linked deep-research runs in a stacked status surface above the transcript. It can also launch research, attach completed research into chat, and prepare follow-up research from completed runs.

The remaining gap is checkpoint handling. When a linked run reaches a human-review checkpoint, chat currently only offers the same generic research link as any other run state. That forces the user to infer that review is needed and that the next action lives in `/research`.

This slice strengthens the handoff for checkpoint-needed runs by:

- showing a compact reason label derived from the review phase
- promoting the run action to `Review in Research`
- suppressing completion-oriented actions like `Use in Chat` and `Follow up` while review is pending

## Desired Behavior

When a linked run in chat has:

- `status = "waiting_human"`
- and a checkpoint review phase such as:
  - `awaiting_plan_review`
  - `awaiting_source_review` or `awaiting_sources_review`
  - `awaiting_outline_review`

the run row should render as a review-needed handoff state.

That state should show:

- the run query
- the existing status badge
- a compact reason label:
  - `Plan review needed`
  - `Sources review needed`
  - `Outline review needed`
  - fallback: `Review needed`
- a primary `Review in Research` action pointing to `/research?run=<id>`

While in that state:

- do not show `Use in Chat`
- do not show `Follow up`
- do not attempt checkpoint approval or editing in chat

## Scope

Start with the linked-run status stack only.

Primary surface:

- `apps/packages/ui/src/components/Option/Playground/ResearchRunStatusStack.tsx`

Supporting helper logic:

- `apps/packages/ui/src/components/Option/Playground/research-run-status.ts`

Primary test seam:

- `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx`

This slice does not require changes to:

- completion handoff message rendering
- attachment surfaces
- backend linked-run payloads

## State Contract

This slice should derive checkpoint handoff state entirely from the existing linked-run row payload:

- `run.status`
- `run.phase`
- `run.latest_checkpoint_id`
- `run.run_id`
- `run.query`

Recommended helper behavior:

- `awaiting_plan_review` -> `Plan review needed`
- `awaiting_source_review` or `awaiting_sources_review` -> `Sources review needed`
- `awaiting_outline_review` -> `Outline review needed`
- unknown review-phase while `waiting_human` -> `Review needed`

This design does not require the full checkpoint payload in chat. The chat UI only needs enough information to explain why the run must be reviewed in `/research`.

## UI Contract

For checkpoint-needed rows:

- keep the query snippet visible
- keep the row in the existing stack layout
- show the normal status badge, which may still read `Needs review`
- add the compact reason label beside the status area
- replace the generic `Open in Research` wording with `Review in Research`
- suppress `Use in Chat`
- suppress `Follow up`

For all non-checkpoint rows:

- keep the current behavior unchanged

The key UX difference is not a new layout. It is stronger intent on the existing run row.

## Interaction Rules

- clicking `Review in Research` always opens the specific run, not a speculative checkpoint deep-link
- checkpoint-needed runs remain read-only from chat
- non-checkpoint `waiting_human` states should still fall back cleanly if phase data is incomplete or unfamiliar

## Testing Scope

Frontend coverage should prove:

- `waiting_human + awaiting_plan_review` shows `Plan review needed` and `Review in Research`
- `waiting_human + awaiting_source_review` shows `Sources review needed`
- `waiting_human + awaiting_sources_review` is treated the same as sources review
- `waiting_human + awaiting_outline_review` shows `Outline review needed`
- unknown review-phase while `waiting_human` falls back to `Review needed`
- `Use in Chat` and `Follow up` are suppressed for checkpoint-needed rows
- non-checkpoint completed rows still show current actions unchanged
- `Review in Research` still targets the correct run URL

## Out Of Scope

- no checkpoint editing or approval in chat
- no new backend API or schema changes
- no dedicated checkpoint banner above the transcript
- no new completion-message treatment in this slice

## Risks

- phase-name drift if backend review phase strings expand or change subtly
- overloading the row if reason copy competes with status and actions
- accidentally suppressing useful actions for rows that are `waiting_human` but not truly checkpoint-driven

## Implementation Notes

The existing helper `getChatLinkedResearchStatusLabel(...)` already maps review phases to `Needs review`. This slice should extend that helper layer rather than hardcoding review strings in `ResearchRunStatusStack.tsx`.

The preferred implementation is:

- add a narrow helper like `getChatLinkedResearchReviewReason(...)`
- add a helper like `isCheckpointReviewRun(...)`
- keep `ResearchRunStatusStack.tsx` focused on row presentation and action gating
