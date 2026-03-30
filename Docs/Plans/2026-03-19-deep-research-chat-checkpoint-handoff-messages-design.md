# Deep Research Chat Checkpoint Handoff Messages Design

**Goal:** Make genuine deep-research handoff messages in chat react to current checkpoint-needed run state, so they hand users back to `/research` consistently with the linked-run status stack.

**Status:** Approved design baseline for implementation planning.

## Summary

The linked-run status stack now treats checkpoint-needed runs as review handoffs:

- compact reason label
- `Review in Research`
- no `Use in Chat`
- no `Follow up`

Genuine deep-research handoff messages in the transcript still expose the older completion-oriented actions. That creates inconsistent guidance in two chat surfaces for the same run.

This slice reuses the same checkpoint-aware mapping on research-origin assistant handoff messages only. The message body stays unchanged. Only the action area becomes checkpoint-aware.

## Desired Behavior

For genuine deep-research handoff messages:

- if the linked run is not checkpoint-needed:
  - keep current message actions unchanged
  - `Use in Chat`
  - `Follow up`
  - existing research link behavior

- if the linked run is checkpoint-needed:
  - suppress `Use in Chat`
  - suppress `Follow up`
  - show a compact reason label:
    - `Plan review needed`
    - `Sources review needed`
    - `Outline review needed`
    - fallback: `Review needed`
  - show `Review in Research`

This should match the linked-run status stack, not introduce a second policy.

## Scope

Primary implementation seam:

- `apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`

Primary tests:

- `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx`

Supporting helper reuse:

- `apps/packages/ui/src/components/Option/Playground/research-run-status.ts`

This slice does not require:

- backend changes
- transcript text changes
- completion-message persistence changes
- attachment-surface changes

## State Contract

The message surface should derive its behavior from two existing data sources:

1. message metadata proving the message is a genuine deep-research handoff
2. current linked-run state for that `run_id`

The same run-state mapping should be reused:

- `awaiting_plan_review` -> `Plan review needed`
- `awaiting_source_review` / `awaiting_sources_review` -> `Sources review needed`
- `awaiting_outline_review` -> `Outline review needed`
- unknown `waiting_human` review phase -> `Review needed`

If the chat message is a genuine research handoff but there is no current linked-run state for that run:

- keep current message actions unchanged
- do not guess checkpoint state from stale metadata alone

## UI Contract

For checkpoint-needed handoff messages:

- keep the message body unchanged
- keep the treatment local to the message action area
- show the reason label near the action
- show `Review in Research`
- remove `Use in Chat`
- remove `Follow up`

For non-checkpoint handoff messages:

- preserve the current action rendering

The message action area should stay lightweight. The linked-run status stack remains the primary thread-level state view.

## Genuine Handoff Detection

This slice should only affect messages that the existing message-action logic already treats as deep-research completion/handoff messages.

It should not apply to:

- arbitrary assistant messages
- messages that merely mention a run id in text
- unrelated metadata shapes

Recommended approach:

- reuse the same `deep_research_completion` metadata recognition path already used to decide whether `Use in Chat` and `Follow up` appear today

## Testing Scope

Frontend coverage should prove:

- checkpoint-needed handoff messages show the correct reason label and `Review in Research`
- checkpoint-needed handoff messages suppress `Use in Chat` and `Follow up`
- non-checkpoint handoff messages retain existing actions
- unrelated assistant messages remain unaffected
- missing current linked-run state falls back to the existing message actions

## Out Of Scope

- no message-body copy changes
- no checkpoint approval/editing in chat
- no backend API/schema changes
- no new transcript banner or row type

## Risks

- duplicating checkpoint-state logic if the message layer does not reuse the helper layer
- over-matching messages that are not genuine research handoff messages
- making the message action area too heavy if the reason label is rendered as body content instead of action metadata

## Implementation Notes

`PlaygroundChat.tsx` already builds message-level `Use in Chat` and `Follow up` handlers from `deep_research_completion` metadata. This slice should extend that same decision point rather than patching the lower message component.

The preferred implementation is:

- reuse `isCheckpointReviewRun(...)` and `getChatLinkedResearchReviewReason(...)`
- resolve the current linked run by `run_id`
- emit message actions and reason label from one shared message-handoff helper path
