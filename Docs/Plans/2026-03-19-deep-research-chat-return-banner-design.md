# Deep Research Chat Return Banner Design

**Goal:** Show a one-time, non-transcript banner in chat immediately after the user returns from the research console via `Back to Chat`, so the returned run can be used or followed up without making the user hunt through the thread.

**Status:** Approved for implementation.

## Scope

This slice adds a one-time return banner to chat for the explicitly returned research run only.

In scope:
- carry `researchReturnRunId` on `Back to Chat` navigation
- restore the exact saved chat thread as already implemented
- render a compact one-time banner for the returned run
- reuse existing deep-research chat action policy and action handlers
- clear the return marker from the URL after the banner is resolved

Out of scope:
- transcript writes
- automatic context attachment
- automatic follow-up launch
- multi-run return history
- backend persistence or mutation

## User Experience

When the user clicks `Back to Chat` from `/research` on a linked run:

1. Chat opens the exact originating saved thread.
2. Chat recognizes the returned run by `researchReturnRunId`.
3. A compact banner appears above the transcript or composer area.
4. The banner offers the right actions for the current run state:
   - completed: `Use in Chat`, `Follow up`, `Open in Research`
   - checkpoint-needed: `Review in Research`
5. The user may dismiss it.
6. The banner does not replay on refresh because the return query param is removed once consumed.

The linked-run status stack remains unchanged. The banner is additive and specific to the explicit return flow.

## Navigation Contract

`Back to Chat` should navigate to the existing exact-thread restore path and add a single return marker:

- `settingsServerChatId=<chat_id>`
- `researchReturnRunId=<run_id>`

This intentionally reuses the existing exact-thread bootstrap seam already consumed by chat, rather than introducing a second chat-thread selection mechanism.

The URL should not include full run payloads or research bundle data.

## Data And State Contract

The banner state is derived from:

- `researchReturnRunId` from the URL
- the already-fetched linked runs for the active chat thread

Resolution rules:
- if the URL has no `researchReturnRunId`, show no banner
- if the thread has not loaded its linked runs yet, wait
- if the linked runs load and the returned run is found, show the banner
- if the linked runs load and the returned run is not found, silently show nothing
- after either showing or deciding not to show, clear `researchReturnRunId` from the URL

The banner should also keep a local dismissed state so the user can close it without affecting the linked-run stack.

## UI Contract

The return banner should be visually separate from both:
- the transcript
- the stacked linked-run status block

Suggested content:
- label: `Returned from Research`
- query snippet
- optional compact reason or status text
- actions driven by the shared research action policy
- `Dismiss`

Action behavior:
- `Use in Chat` reuses the existing attach flow
- `Follow up` reuses the existing prepare-follow-up flow
- `Review in Research` reuses the existing research link behavior
- `Open in Research` remains available when the primary action is not a review action

The banner must not re-derive its own gating rules. It should consume the same policy contract already used by status rows and handoff messages.

## Integration Points

### Research console

`Back to Chat` should extend its current exact-thread href generation to include `researchReturnRunId`.

### Route helpers

The chat-thread route helper should be extended to accept optional return-banner context:
- existing `serverChatId`
- new optional `researchReturnRunId`

### Chat page

Chat should:
- read `researchReturnRunId` from the URL
- wait for linked runs to resolve
- build banner state by matching that run
- clear the query param after consumption

### Shared policy

The banner should consume the existing chat-side deep-research action policy helper instead of encoding its own action eligibility.

## Failure Handling

Failure behavior should stay quiet:
- if the returned run cannot be found in linked runs, no toast and no banner
- if linked runs fail to load, no special error just for the banner
- if the URL is malformed, ignore it and clear it when convenient

This is a convenience surface, not a critical load path.

## Testing Strategy

Frontend coverage should prove:
- the `Back to Chat` href includes `researchReturnRunId`
- chat shows a banner only after explicit return navigation
- banner action eligibility matches the shared research policy
- checkpoint-needed returned runs show `Review in Research`
- dismiss hides the banner without affecting the linked-run stack
- the return marker is cleared from the URL after processing

No backend changes are required for this slice.

## Key Decision

The banner is intentionally one-time and URL-driven. That keeps the flow explicit, debuggable, and easy to test while reusing the chat thread restore mechanism already in production.
