# Deep Research Chat State-Specific Return Banner Design

**Goal:** Make the one-time `Returned from Research` chat banner smarter after explicit return navigation by adapting its copy and primary CTA to the returned run's current state, especially after checkpoint review.

**Status:** Approved for implementation.

## Scope

This slice evolves the existing explicit-return banner only.

In scope:
- keep the current `researchReturnRunId` navigation flow
- keep the banner one-time and non-transcript
- derive banner mode from explicit return plus current linked-run state
- add a stronger post-review CTA when a previously review-blocked return is now review-cleared
- keep the existing completed and still-blocked behaviors intact

Out of scope:
- backend schema or event-history changes
- auto-attach or auto-launch on return
- generic linked-run row changes
- multi-run return history

## Problem

The current return banner distinguishes only by current action policy:
- completed returns show `Use in Chat` / `Follow up`
- checkpoint-blocked returns show `Review in Research`

That is correct but incomplete. When a user explicitly comes back from `/research` after resolving a checkpoint, chat has no clearer next-step language than the generic completed banner. The returned run is special because the user just reviewed or adjusted it, and the banner should acknowledge that without inventing new backend state.

## User Experience

When the user clicks `Back to Chat` from `/research`:

1. Chat restores the exact saved thread as it already does.
2. Chat resolves the returned run from `researchReturnRunId`.
3. The one-time banner derives a mode from:
   - explicit return context
   - current linked-run state
4. The banner adapts:
   - `completed`
     - `Use in Chat`
     - `Follow up`
     - `Open in Research`
   - `review_required`
     - `Review in Research`
   - `review_cleared`
     - primary CTA: `Continue with reviewed research`
     - secondary: `Open in Research`
   - `generic`
     - conservative fallback, usually `Open in Research`
5. The banner remains dismissible and one-time.

The key user-facing change is the `review_cleared` case. It acknowledges that the returned run reflects user review and emphasizes the next chat-side action without changing the underlying attach behavior.

## State Contract

There is no distinct chat-facing backend state today for "review just completed." The research run model still exposes only current `status` and `phase`, with review blocks represented by:

- `status = waiting_human`
- `phase = awaiting_*_review`

So this slice must stay client-derived.

Suggested derived modes:

- `review_required`
  - current linked run is still checkpoint-blocked
- `completed`
  - current linked run is completed
- `review_cleared`
  - explicit return banner is active
  - current run is no longer checkpoint-blocked
  - current run is not completed
- `generic`
  - any other current returned state

This intentionally avoids inventing a persisted "just reviewed" state. The stronger CTA is a UX interpretation of:
- explicit return from `/research`
- current run no longer needing review

## Banner Contract

The existing shared linked-run action policy remains the source of truth for:
- whether review is required
- whether `Use in Chat` is allowed
- whether `Follow up` is allowed
- which research link label is correct

This slice adds one lightweight banner adapter on top of that policy. The adapter should return:

- `mode`
- `headline`
- `supportingText`
- `primaryActionLabel`
- whether to expose `Use in Chat`, `Follow up`, or only the research link

Important boundary:
- the shared policy helper should not learn about transient return-banner UX
- the banner adapter should not reimplement run-state safety rules

## UI Contract

The existing banner component stays in place, but its CTA wording becomes mode-specific.

### Completed

- label: `Returned from Research`
- keep current action set:
  - `Use in Chat`
  - `Follow up`
  - `Open in Research`

### Review Required

- label: `Returned from Research`
- keep current reason label from shared policy
- actions:
  - `Review in Research`
  - `Dismiss`

### Review Cleared

- label: `Returned from Research`
- supporting copy:
  - `Your review is reflected in this run.`
- primary CTA:
  - `Continue with reviewed research`
- secondary:
  - `Open in Research`
  - `Dismiss`

For v1, `Continue with reviewed research` should map to the same underlying attach path as `Use in Chat`. The change is phrasing and priority, not a new behavior path.

### Generic

- conservative fallback:
  - `Open in Research`
  - `Dismiss`

## Integration Points

### Playground coordinator

`Playground.tsx` continues to own:
- explicit return marker capture
- one-time banner lifetime
- dismissal state

No new navigation or persistence logic is required.

### Playground chat surface

`PlaygroundChat.tsx` continues to:
- resolve the returned run from linked runs
- reuse shared linked-run action policy
- render the visible banner

This slice adds:
- a banner-mode adapter
- state-specific CTA copy

### Shared helpers

The cleanest seam is likely a small helper near:
- `apps/packages/ui/src/components/Option/Playground/research-run-status.ts`
- or `apps/packages/ui/src/components/Option/Playground/research-chat-context.ts`

The helper should be return-banner specific, not a generic expansion of the shared policy contract.

## Failure Handling

Failure behavior stays quiet:
- if the run cannot be resolved, show no banner
- if linked runs fail to load, show no special return error
- if the adapter cannot classify beyond the current policy, fall back to `generic`

This slice should never block chat loading.

## Testing Strategy

Frontend tests should cover:
- explicit return of a completed run keeps the current completed actions
- explicit return of a still-blocked checkpoint run keeps `Review in Research`
- explicit return of a no-longer-blocked non-completed run shows `Continue with reviewed research`
- `Continue with reviewed research` routes through the same attach path as `Use in Chat`
- non-returned linked runs do not receive the special `review_cleared` phrasing
- the one-time dismissal behavior remains unchanged

No backend changes or backend tests are required.

## Key Decision

The banner remains explicitly return-driven and client-derived. That gives chat better post-review guidance without introducing a new research lifecycle state or coupling the backend to transient chat UX language.
