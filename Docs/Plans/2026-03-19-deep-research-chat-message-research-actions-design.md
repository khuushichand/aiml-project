# Deep Research Chat Message Research Actions Design

**Goal:** Replace the ad hoc deep-research message action prop bundle with one narrow `researchActions` view-model contract so transcript handoff messages render from a single message-level seam instead of four loosely-related props.

**Status:** Approved design baseline for implementation planning.

## Summary

Deep-research handoff messages inside chat currently render from four separate props threaded through `PlaygroundChat.tsx` into `Message.tsx`:

- `onUseInChat`
- `onFollowUp`
- `researchReviewReason`
- `researchReviewHref`

The underlying run-state policy is now centralized, but the message rendering seam still remains loosely structured. That makes future message-surface changes easy to drift because the same research action state is still represented as an informal prop bundle.

This slice introduces one narrow `researchActions` message prop for genuine deep-research handoff messages only. The goal is to unify message rendering and message-level wiring without changing any user-facing behavior.

## Desired Behavior

For genuine deep-research handoff messages:

- completed run state still shows:
  - `Use in Chat`
  - `Follow up`
- checkpoint-needed run state still shows:
  - compact reason label
  - `Review in Research`
- no-current-run fallback still keeps the existing completion-oriented actions

For unrelated assistant messages:

- no deep-research action row is rendered

For non-message chat surfaces:

- no change in this slice

## Scope

Primary files:

- `apps/packages/ui/src/components/Common/Playground/Message.tsx`
- `apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`

Primary test seam:

- `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx`

## Architecture

Introduce a single message-level view model:

- `researchActions?: { ... }`

Recommended fields:

- `reasonLabel?: string`
- `primaryLink?: { href: string; label: string }`
- `onUseInChat?: () => void`
- `onFollowUp?: () => void`

Important constraints:

- `Message.tsx` should treat `researchActions` as the single source of truth for deep-research handoff message actions
- `Message.tsx` should not continue to separately derive `showUseInChat` / `showFollowUp` from deep-research metadata once `researchActions` exists
- `PlaygroundChat.tsx` should build the object once per message through one local adapter and pass that object through all existing `PlaygroundMessage` call sites

This design is intentionally narrow:

- `researchActions` is for genuine deep-research handoff messages only in v1
- it is named cleanly enough to generalize later, but should not be treated as a generic message-actions system in this slice

## State Rules

`PlaygroundChat.tsx` remains responsible for:

- deciding whether a message is a genuine deep-research handoff message
- resolving the current linked run, if any
- applying the shared run-state policy helper when a current run exists
- preserving the no-current-run fallback behavior when current linked-run state is unavailable

`Message.tsx` should receive only render-ready data:

- optional reason label
- optional primary link
- optional handlers for `Use in Chat` and `Follow up`

It should not receive raw policy flags, run IDs, or checkpoint phase names.

## Surface Integration

### Message.tsx

`Message.tsx` should:

- add `researchActions?: { ... }` to the prop contract
- render the deep-research action row from that object only
- stop depending on a separate deep-research metadata gate for those actions once the object is present

This avoids two sources of truth inside the message component.

### PlaygroundChat.tsx

`PlaygroundChat.tsx` should:

- replace the four separate deep-research message props with one `researchActions` object
- build that object through a single local adapter, for example `buildMessageResearchActions(metadataExtra)`
- reuse that adapter across all three existing `PlaygroundMessage` call sites in the chat timeline

The adapter should:

- keep genuine-handoff detection unchanged
- preserve no-current-run fallback behavior
- return `undefined` for non-handoff messages

## Testing Scope

Regression coverage should prove:

- completed deep-research handoff messages still render `Use in Chat` and `Follow up`
- checkpoint-needed handoff messages still render the reason label and `Review in Research`
- no-current-run handoff messages still preserve the current fallback actions
- unrelated assistant messages still render no deep-research actions
- the mocked `PlaygroundMessage` seam now consumes `researchActions`, not the old four-prop bundle

## Out Of Scope

- no new user-facing behavior
- no status-row changes
- no attempt to generalize non-research `onUseInChat` behavior elsewhere in the app
- no generic message-actions framework

## Risks

- leaving metadata-based gates inside `Message.tsx` and ending up with two sources of truth
- repeating `researchActions` object construction inline across multiple `PlaygroundChat` call sites
- accidentally breaking unrelated uses of the existing generic `onUseInChat` prop outside the deep-research handoff path

## Implementation Notes

The current `PlaygroundMessage` prop surface is used broadly across the app, including prompt-related flows that also use `onUseInChat`. This slice should only collapse the deep-research handoff rendering seam, not reinterpret every generic `PlaygroundMessage` action as a research action.

That means:

- the new `researchActions` prop should be additive and narrow
- the old generic `onUseInChat` prop should only be removed from this message-handoff path when all deep-research message call sites are migrated
- other unrelated `PlaygroundMessage` consumers should remain untouched in this slice
