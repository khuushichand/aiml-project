# Deep Research Chat Run-Surface Follow-Up Design

**Goal:** Let users start a chat-side follow-up research flow directly from completed research surfaces by prefilling the composer and restoring the selected run as active research context.

**Status:** Approved design baseline for implementation planning.

## Summary

Chat already supports:

- launching deep research from chat
- seeing linked run status in the thread
- attaching completed run context with `Use in Chat`
- launching explicit composer-driven `Follow-up Research`

The remaining usability gap is that completed research surfaces do not provide a direct way to prepare a follow-up research question. Users must manually attach the prior run or remember to type a prompt in the composer first.

This slice adds a lightweight `Follow up` action to completed research surfaces that prepares, but does not launch, the next research run.

## Desired Behavior

Expose `Follow up` in two places:

- completed rows in `ResearchRunStatusStack.tsx`
- completion handoff messages in `Message.tsx`

When clicked:

1. If the selected run is not already the active attached research context, attach it as the active context.
2. Prefill the composer with a deterministic follow-up prompt based on the run query.
3. Focus the composer so the user can edit the prompt.
4. Do not launch anything automatically.

The actual run creation remains owned by the existing composer `Follow-up Research` flow in `PlaygroundForm.tsx`.

## Deterministic Prompt Contract

V1 prompt format:

- `Follow up on this research: <query>`

Rules:

- derive only from the run query
- do not inspect the bundle to generate prompts
- do not call a model

Draft handling:

- if the composer draft is empty, replace it directly
- if the composer draft is non-empty, use the existing overwrite/append confirmation pattern already used by prompt insertion flows in `PlaygroundForm.tsx`

## Surface Scope

### Linked Run Status Rows

In `ResearchRunStatusStack.tsx`:

- show `Follow up` only when `run.status === "completed"`
- keep `Use in Chat` and `Open in Research`
- `Follow up` should be distinct from `Use in Chat`

The intent split is:

- `Use in Chat`: attach completed research for normal chat use
- `Follow up`: prepare the composer for a new research run based on that prior run

### Completion Handoff Messages

In `Message.tsx`:

- show `Follow up` only for genuine research completion handoff messages
- keep `Use in Chat` for the same messages
- do not show `Follow up` for unrelated assistant messages

## State Ownership

No new backend contract is needed.

This slice should remain frontend-only and reuse the current state owners:

- `Playground.tsx` owns attached research context state
- `PlaygroundForm.tsx` owns composer draft text and the explicit follow-up launch flow
- linked run rows and completion messages should emit a narrow callback upward

Recommended flow:

1. run surface emits `onFollowUp(run)`
2. parent resolves that run into the active attached context if needed
3. parent or form applies the deterministic prompt into the composer draft
4. existing composer `Follow-up Research` path remains unchanged

## Draft Insertion Behavior

To avoid divergent UX, run-surface follow-up should reuse the existing insert behavior pattern already present in `PlaygroundForm.tsx`:

- empty draft: replace silently
- non-empty draft: show overwrite/append choice

This avoids silently clobbering user input.

## Focus Behavior

After the prompt is inserted:

- focus the composer textarea
- place the caret at the end of the inserted content

This is important because the feature is meant to prepare the next launch, not just mutate hidden state.

## Out Of Scope

- no auto-launch from run surfaces
- no model-generated or multi-suggestion follow-up prompts
- no new backend fields or persistence model
- no `Follow up` for in-progress, failed, or cancelled runs
- no bundle-aware prompt generation

## Risks

- confusing `Follow up` with `Use in Chat` if both actions are not clearly labeled
- unexpectedly overwriting non-empty drafts if insertion logic bypasses existing confirmation patterns
- splitting behavior between linked-run rows and completion messages if each surface implements custom prompt-building logic

## Implementation Notes

Primary files likely involved:

- `apps/packages/ui/src/components/Option/Playground/ResearchRunStatusStack.tsx`
- `apps/packages/ui/src/components/Common/Playground/Message.tsx`
- `apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`
- `apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`

The preferred implementation is to introduce a shared helper for:

- building the deterministic follow-up prompt from a run query
- routing run-surface follow-up intent into the composer/attachment state

That keeps row actions and message actions from drifting.
