# Deep Research Chat Action Policy Design

**Goal:** Centralize chat-side deep-research action eligibility into one shared policy helper so current and future chat surfaces stop re-deriving the same run-state rules independently.

**Status:** Approved design baseline for implementation planning.

## Summary

Chat now exposes deep-research actions across multiple surfaces:

- linked-run status rows above the transcript
- genuine research-origin handoff messages inside the transcript

Those surfaces currently agree on the main user-facing behaviors, including checkpoint-aware review handoff, but they still derive action eligibility in separate places. That creates a policy-drift risk whenever a new run state or action rule is added.

This slice introduces one shared chat-side action-policy helper that derives:

- whether `Use in Chat` is allowed
- whether `Follow up` is allowed
- whether review handoff should replace completion-oriented actions
- which compact reason label to show
- which primary research-link label and href to use

The helper is a policy layer only. It does not render UI and does not decide whether a transcript message is eligible to participate in research actions at all.

## Desired Behavior

All chat surfaces that render research actions should consume one shared policy contract for linked-run state.

For a checkpoint-needed run:

- `needsReview = true`
- `reasonLabel = "Plan review needed"` / `Sources review needed` / `Outline review needed` / fallback `Review needed`
- primary link label becomes `Review in Research`
- `Use in Chat` is disallowed
- `Follow up` is disallowed

For a completed run:

- `needsReview = false`
- primary link label becomes `Open in Research`
- `Use in Chat` is allowed
- `Follow up` is allowed

For unknown or nonterminal non-review states:

- default conservatively
- keep the research link available
- do not enable `Use in Chat` or `Follow up` unless the state is explicitly safe

## Scope

Primary helper layer:

- `apps/packages/ui/src/components/Option/Playground/research-run-status.ts`
  - or a small adjacent helper module if keeping `research-run-status.ts` focused becomes cleaner

Current consumer surfaces:

- `apps/packages/ui/src/components/Option/Playground/ResearchRunStatusStack.tsx`
- `apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`

Primary test seams:

- `apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts`
- `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx`
- `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx`

## Architecture

Add a shared helper that accepts current linked-run state and returns a narrow action-policy object.

Recommended inputs:

- `run: ChatLinkedResearchRun`

Recommended exported contract:

- `type ChatLinkedResearchActionPolicy = { ... }`

Recommended outputs:

- `needsReview: boolean`
- `reasonLabel: string | null`
- `primaryActionKind: "review" | "open"`
- `primaryActionLabel: "Review in Research" | "Open in Research"`
- `researchHref: string`
- `canUseInChat: boolean`
- `canFollowUp: boolean`

Message-specific eligibility stays outside the helper.

For example:

- `PlaygroundChat.tsx` should still first decide whether a message is a genuine deep-research handoff message
- only then should it ask the shared helper for run-state policy

That keeps transcript-specific concerns out of the shared policy layer.

The contract should be exported as a named type, not inferred ad hoc from helper return values. Future chat surfaces should depend on one stable policy shape.

## State Rules

The helper should build on the existing checkpoint review logic already established in chat.

Recommended review mapping:

- `awaiting_plan_review` -> `Plan review needed`
- `awaiting_source_review` -> `Sources review needed`
- `awaiting_sources_review` -> `Sources review needed`
- `awaiting_outline_review` -> `Outline review needed`
- unknown `waiting_human` review phase -> `Review needed`

Recommended action rules:

- checkpoint-needed review run:
  - `primaryActionKind = "review"`
  - `primaryActionLabel = "Review in Research"`
  - `canUseInChat = false`
  - `canFollowUp = false`
- completed run:
  - `primaryActionKind = "open"`
  - `primaryActionLabel = "Open in Research"`
  - `canUseInChat = true`
  - `canFollowUp = true`
- all other states:
  - `primaryActionKind = "open"`
  - `primaryActionLabel = "Open in Research"`
  - `canUseInChat = false`
  - `canFollowUp = false`

This design does not change the separate status-badge contract. Existing helpers like `getChatLinkedResearchStatusLabel(...)` can remain focused on status presentation.

The shared helper should not decide status-badge text. It should only decide research-action policy.

## Surface Integration

### Linked-Run Status Stack

`ResearchRunStatusStack.tsx` should:

- ask the shared helper for row policy
- render the returned `reasonLabel`
- show `Use in Chat` only when `canUseInChat`
- show `Follow up` only when `canFollowUp`
- show the primary research link using the returned label and href

### Research Handoff Messages

`PlaygroundChat.tsx` should:

- keep current genuine-handoff detection unchanged
- resolve the current linked run for the handoff message
- if found, ask the shared helper for policy exactly once for that message
- pass the resulting review reason, review href, and completion-action eligibility through the existing `Message.tsx` seam

If no current run match exists:

- keep existing message behavior unchanged
- do not guess policy from stale message metadata alone

The message layer should use one local adapter that resolves the current run once and fans the resulting policy back out into the existing message props. It should not reintroduce drift by repeating linked-run lookup across multiple builder functions.

## Testing Scope

Shared-helper coverage should prove:

- completed run policy allows `Use in Chat` and `Follow up`
- checkpoint-needed review run policy returns the correct reason and disallows those actions
- unknown review phase falls back to `Review needed`
- running/failed/cancelled states stay conservative
- failed and cancelled states still keep the primary research link available as `Open in Research`

Surface regression coverage should prove:

- status rows preserve current behavior after moving to the helper
- genuine research handoff messages preserve current behavior after moving to the helper
- non-handoff messages still do not get research actions from the helper layer

## Out Of Scope

- no new user-facing behavior beyond policy unification
- no new backend APIs or schema changes
- no changes to message-body text
- no new chat research surfaces in this slice

## Risks

- subtle regressions if one surface depended on undocumented special-case logic
- helper over-design that is harder to extend than the duplicated code it replaces
- future surfaces bypassing the helper if the policy contract is awkward or too UI-specific

## Implementation Notes

The existing `research-run-status.ts` file already owns checkpoint review helpers and the research href builder. It is the most natural place to host the shared policy contract unless the file becomes too mixed.

The helper should return booleans and labels only. It should not return callbacks or JSX. Surfaces should continue to own UI layout and event wiring.
