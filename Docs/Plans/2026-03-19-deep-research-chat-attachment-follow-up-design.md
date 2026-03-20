# Deep Research Chat Attachment-Surface Follow-Up Design

**Goal:** Let users prepare a follow-up deep-research prompt directly from active, pinned, and recent attached research surfaces near the composer, while keeping launch explicit.

**Status:** Approved design baseline for implementation planning.

## Summary

Chat already supports:

- attaching completed research with `Use in Chat`
- persisting one active attachment, one pinned attachment, and bounded history
- preparing follow-up research from completed run rows and completion handoff messages

The remaining usability gap is that composer-adjacent attachment management surfaces still require the user to move back to a linked run row or completion message if they want to prepare a follow-up research prompt from the attachment they are already using.

This slice adds `Follow up` to attachment-management surfaces and routes those actions through the same shared follow-up-preparation path that run surfaces already use.

## Desired Behavior

Expose `Follow up` on:

- the active attachment chip
- the pinned attachment mini-card
- each recent-history entry

When clicked:

1. show a lightweight local confirmation tied to that surface
2. if confirmed, route the selected run through the existing shared follow-up-preparation callback
3. let the existing preparation path restore/attach the run if needed
4. seed the deterministic composer prompt
5. do not launch anything automatically

The composer `Follow-up Research` action remains the only place that actually starts a new research run.

## Confirmation Contract

This slice should use a small local confirmation, not a full modal.

Confirmation copy:

- title: `Prepare follow-up?`
- body: `This will use "<query>" and prefill a follow-up research prompt in the composer.`
- actions:
  - `Prepare follow-up`
  - `Cancel`

Behavior:

- cancel does nothing
- confirm routes through the shared preparation callback
- confirmation should be visually local to the clicked surface, not a global workflow modal

## Surface Scope

### Active Attachment Chip

In `AttachedResearchContextChip.tsx`:

- add `Follow up` beside the existing active attachment actions
- keep current `Preview`, `Remove`, `Pin`, and related actions unchanged
- `Follow up` should prepare a new research draft, not mutate active attachment state directly

### Pinned Attachment Mini-Card

In the pinned-only fallback area of `PlaygroundForm.tsx`:

- add `Follow up` beside `Use now`, `Unpin`, and `Open in Research`
- keep pinned-only fallback semantics unchanged
- confirmation should be local to the pinned card

### Recent History Entries

In active and fallback history surfaces:

- add `Follow up` beside `Use` and `Pin`
- `Follow up` must not implicitly trigger `Use`
- history ordering must stay unchanged

## State Ownership

No backend changes are needed.

This remains frontend-only and should reuse current state owners:

- attachment surfaces only identify the selected source run and ask for confirmation
- `Playground.tsx` remains the owner of shared follow-up preparation
- `PlaygroundForm.tsx` remains the owner of draft insertion and explicit follow-up launch

Recommended flow:

1. attachment surface emits `onRequestFollowUp(target)`
2. local UI opens confirmation tied to that target
3. on confirm, attachment surface emits `onConfirmFollowUp(target)`
4. `Playground` reuses the existing shared follow-up-preparation callback
5. composer insertion remains unchanged

## Interaction Rules

- `Follow up` from history must not also activate the history item unless the shared prep path later reattaches it
- `Follow up` from pinned must not implicitly switch pinned to active until the shared prep path runs
- active, pinned, and history controls must not duplicate the same run visually after confirmation if active state changes later

## Testing Scope

Frontend coverage should prove:

- `Follow up` appears on active, pinned, and recent-history attachment surfaces
- clicking it opens the local confirmation with the correct query text
- confirming routes through the same shared preparation callback already used by run surfaces
- cancelling does nothing
- existing `Use`, `Pin`, `Unpin`, `Remove`, and `Open in Research` actions remain intact

## Out Of Scope

- no new backend contracts or persistence changes
- no launch modal from attachment surfaces
- no automatic run launch
- no model-generated follow-up suggestions
- no changes to linked-run row or completion-message follow-up semantics

## Risks

- action crowding on recent-history rows if controls become too dense
- event bubbling causing `Follow up` to trigger `Use`
- duplicate preparation logic if attachment surfaces bypass the shared callback in `Playground`

## Implementation Notes

Primary files likely involved:

- `apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx`
- `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- `apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- existing attachment integration tests under `apps/packages/ui/src/components/Option/Playground/__tests__/`

The preferred implementation is:

- keep confirmation UI local to the clicked attachment surface
- keep follow-up preparation logic centralized in `Playground`
- avoid adding new stores, backend fields, or modal systems
