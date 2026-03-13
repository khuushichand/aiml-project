# Collections Page Startup Investigation Design

**Date:** 2026-03-13

## Goal

Define a narrow, evidence-driven investigation for the Collections page regression reported in both the WebUI and the extension, where the page loads empty and user actions appear non-functional.

## Problem Summary

The Collections page is shared across the WebUI and the extension via the UI package. The reported symptom pattern is:

- Collections is already empty on first load.
- User actions appear dead or produce API/data failures.
- The problem reproduces in both the WebUI and the extension.

That makes this primarily a shared startup-path regression until proven otherwise. The investigation should avoid broad feature sweeps and focus first on the mount-time load path that determines whether the page has usable data at all.

## Observed Architecture

The shared route and startup flow currently looks like this:

`/collections route` -> shared tab component -> mount-time `fetch*()` callback -> `useTldwApiClient()` singleton -> `TldwApiClient` -> `bgRequest` / `request-core` -> backend endpoint -> normalized response -> UI/store state

Key shared frontend files:

- `apps/packages/ui/src/routes/option-collections.tsx`
- `apps/packages/ui/src/components/Option/Collections/index.tsx`
- `apps/packages/ui/src/components/Option/Collections/ReadingList/ReadingItemsList.tsx`
- `apps/packages/ui/src/components/Option/Collections/Templates/TemplatesList.tsx`
- `apps/packages/ui/src/components/Option/Collections/Highlights/HighlightsList.tsx`
- `apps/packages/ui/src/components/Option/Collections/Digests/DigestSchedulesPanel.tsx`
- `apps/packages/ui/src/hooks/useTldwApiClient.tsx`
- `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- `apps/packages/ui/src/services/background-proxy.ts`
- `apps/packages/ui/src/services/tldw/request-core.ts`

Key backend files likely relevant to first-load data:

- `tldw_Server_API/app/api/v1/endpoints/reading.py`
- `tldw_Server_API/app/api/v1/endpoints/reading_highlights.py`
- `tldw_Server_API/app/api/v1/endpoints/outputs_templates.py`

## Investigation Scope

The first pass must focus on startup failures, not the whole Collections feature set.

In scope:

- Default Reading tab first-load behavior
- One secondary tab first-load behavior to confirm whether failure is shared
- Request config/auth resolution at request time
- Transport selection between extension messaging and direct fetch
- Response status and response shape for first-load endpoints
- Final UI/store outcome after the request resolves or fails

Out of scope for the first pass:

- Exhaustive review of all Collections actions
- Cosmetic UI issues
- Unrelated feature work
- Broad backend refactors

## Revised Investigation Sequence

### 1. Reproduce using real startup state

Reproduce the issue in both the WebUI and the extension using the same seeded backend state, but without relying exclusively on e2e bootstrap shortcuts that may pre-populate config or bypass normal startup.

Reason:

Existing tests seed auth/config directly in ways that may mask a real user bootstrap problem.

### 2. Capture first-load request evidence

Capture the earliest load-time evidence for:

- Reading tab request flow, especially `/api/v1/reading/items`
- One secondary tab request flow, likely templates via `/api/v1/outputs/templates`

Evidence to capture:

- Request start
- Resolved config summary
- Auth mode
- Transport path selected
- Final request URL/path and method
- Status code
- Minimal response shape
- Final UI/store state

### 3. Validate config and auth as first-class checkpoints

Do not treat config/auth as a side note. The investigation must explicitly verify:

- `tldwConfig` presence and shape
- resolved `serverUrl`
- auth mode
- API key or bearer token availability when required
- whether online/connected state is misleadingly healthy while authenticated requests fail

Reason:

Collections can appear empty if the page thinks the server is available while authenticated data requests fail.

### 4. Classify the failure into one of four buckets

The investigation should conclude with an exact classification:

- Transport failure
  Example: extension messaging or request routing problem
- Auth/bootstrap failure
  Example: config present but invalid or auth mode drift
- Backend contract failure
  Example: response shape, endpoint behavior, or auth expectation mismatch
- UI/store wiring failure
  Example: valid data returned but not rendered or not persisted into state

This classification prevents mixing root cause with secondary symptoms.

### 5. Verify one mutation path after load is fixed

Because the user also reported dead buttons, at least one mutation path must be validated after first-load data is working again.

Examples:

- add reading item
- delete reading item
- create template

Reason:

Load-time GETs and action-time mutations do not always share identical transport behavior. A fix that restores first-load data may still leave actions broken.

### 6. Add regression coverage based on the actual root cause

After the root cause is confirmed, add the smallest durable regression coverage that protects the real failure mode:

- shared client/request unit test if request/config logic regressed
- shared component test if UI/store wiring regressed
- higher-level smoke or e2e guard if startup/bootstrap integration regressed

## Design Review Corrections

The original draft design needed these improvements:

### Config and auth need equal priority

The earlier version treated config/auth as a quick sanity pass. That is not strong enough for this codebase. Config/bootstrap state must be verified as a primary hypothesis because it can cause empty data and dead actions across both environments.

### GET and mutation behavior must be separated

The original design did not sharply separate first-load GET requests from user-triggered mutations. The shared proxy/request path handles these differently, so the investigation must test both classes explicitly.

### Instrumentation must be bounded

The earlier version risked devolving into broad logging. This design narrows instrumentation to fixed checkpoints so the evidence stays actionable and temporary.

### Backend contract includes auth expectations

The investigation cannot limit backend validation to payload shape alone. Auth requirements and status-code behavior are part of the contract the shared frontend depends on.

### Existing e2e coverage is not sufficient evidence

Current collections-related e2e tests may seed config or auth in a way that bypasses the real broken path. Passing tests do not prove that a real user startup flow is healthy.

## Success Criteria

The investigation is successful when all of the following are true:

- The empty-on-load failure is reproduced in both WebUI and extension, or a clear divergence is demonstrated.
- The first failing or misbehaving request/state transition is captured.
- The root cause is classified into transport, auth/bootstrap, backend contract, or UI/store wiring.
- At least one user action is verified after the startup failure is understood or fixed.
- A regression test strategy is identified for the actual failure mode rather than an assumed one.

## Risks

- Test harnesses may hide the real user startup path.
- Shared code may produce different behavior depending on runtime-specific transport availability.
- The page may have more than one issue: a startup-path regression plus a separate mutation-path regression.

## Recommendation

Proceed with a narrow startup-path investigation first, with config/auth verification elevated to a primary checkpoint and one post-fix mutation validation required before considering the Collections page healthy.
