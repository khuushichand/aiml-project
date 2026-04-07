# Quick Ingest Resume And E2E Design

Date: 2026-03-24
Status: Approved for planning
Owner: Codex brainstorming session

## Summary

Make quick ingest in the WebUI behave like a resumable work surface instead of a disposable wizard. The normal `Quick Ingest` entry point should always reopen the current session when one exists. All configurable options should be reachable directly inside the wizard configure step without forcing the user through one of three presets. The completed or in-progress session should remain reopenable until the user explicitly clears it or starts a new ingest.

The design also adds true end-to-end coverage for both `.mkv` upload and URL ingest so the web flow is tested through real processing rather than only mocked submission.

## Problem

The current quick-ingest experience has three user-facing failures:

- the WebUI presents a three-preset decision too early and implies those are the only supported configurations
- the full set of options is not exposed in the actual wizard modal used by the web app
- dismissing the modal does not give users a reliable way to reopen the same ingest session and inspect current status or completed results

There is also an architectural split that makes the behavior easy to regress:

- the WebUI trigger opens [`QuickIngestWizardModal.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/QuickIngestWizardModal.tsx)
- richer option-handling and queue behavior also exists in [`QuickIngestModal.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/QuickIngestModal.tsx)

The wizard is the user-facing surface, but it still includes an “Advanced options are available in the full ingest modal” placeholder. That means the live WebUI path still hides capabilities even if the older modal contains them.

## Goals

- Make the wizard modal the canonical quick-ingest surface in the WebUI.
- Let users process content without selecting a preset.
- Keep presets as optional shortcuts only.
- Expose common, type-specific, and advanced options directly in the wizard configure step.
- Preserve the active quick-ingest session across modal dismissal, route changes, and full page refresh within the same browser tab.
- Reopen the same session from the standard `Quick Ingest` trigger.
- Keep completed sessions visible until the user explicitly starts a new one or clears the old one.
- Add real browser end-to-end coverage for:
  - `.mkv` upload through processing to completion
  - URL ingest through processing to completion
  - queue-limit fallback behavior
  - resume behavior after dismissal

## Non-Goals

- Persist quick-ingest sessions across browser restarts.
- Restore raw local file bytes after a full page refresh.
- Introduce a second persistent ingest monitor surface outside the modal.
- Redesign the backend ingestion APIs from scratch.
- Preserve the current dual-modal architecture for WebUI quick ingest.

## Current State

### User-facing modal

The active WebUI trigger lives in [`QuickIngestButton.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Layouts/QuickIngestButton.tsx) and opens [`QuickIngestWizardModal.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/QuickIngestWizardModal.tsx).

Today the wizard:

- uses a multi-step flow
- treats presets as the first-class configuration choice
- exposes only a small set of type-specific toggles inline
- renders an advanced-options placeholder instead of the real advanced configuration UI
- closes through `onClose()` and relies on minimized processing state only while that in-memory provider remains mounted

### Hidden richer surface

[`QuickIngestModal.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/QuickIngestModal.tsx) contains a richer queue, options, and results implementation, including:

- scroll-constrained modal body handling
- full options panel integration
- more detailed queue and results state
- stronger interaction with the quick-ingest batch service

This is useful implementation material, but it is not the canonical surface the WebUI button opens.

### Existing persistence and runtime pieces

- [`quick-ingest.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/store/quick-ingest.tsx) currently stores lightweight badge state and last-run summary only.
- [`quick-ingest-session-runtime.ts`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/entries/shared/quick-ingest-session-runtime.ts) supports start/cancel and runtime message emission for active sessions, but the runtime session itself is ephemeral.
- [`useIngestQueue.tsx`](/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Common/hooks/useIngestQueue.tsx) already distinguishes persisted queue stubs from in-memory `File` objects, which is the right base for tab-refresh restore semantics.

## Proposed Design

### 1. Make the wizard modal canonical

`QuickIngestWizardModal` becomes the single product-grade quick-ingest modal for WebUI.

Recommended structure:

```text
Quick Ingest trigger
    |
    v
QuickIngestWizardModal
    |
    +-- Add Content step
    +-- Configure step
    +-- Review step
    +-- Processing step
    +-- Results step
    |
    v
Quick ingest session store
```

Design rules:

- The WebUI should not depend on two different ingest modals with different capability surfaces.
- The wizard remains the visible shell because it is already wired to the header and event hosts.
- The older full modal may donate reusable pieces, but users should not need to discover a separate “full modal” to access supported options.

### 2. Introduce a tab-scoped quick-ingest session store

Add a dedicated quick-ingest session store that persists to `sessionStorage`.

The store should contain:

- session lifecycle state:
  - `draft`
  - `processing`
  - `completed`
  - `partial_failure`
  - `cancelled`
- current wizard step
- queued URL rows
- queued file stubs
- active ingest session id
- processing snapshot and progress metadata
- result snapshot
- hidden or visible state
- badge summary for the trigger

The store should not persist raw `File` objects. Instead:

- queued local files are stored as stubs with reattach metadata
- in-memory files are re-bound when available
- after a refresh, queued file stubs without live `File` objects require explicit user reattach

That behavior is acceptable and should be treated as expected UX, not a defect.

Mounting rule:

- the quick-ingest host and its session provider must remain mounted while a resumable session exists
- modal visibility is UI state only
- a session is torn down only when the user explicitly clears it or starts a replacement session

This must be stated explicitly because the current wizard unmounts when `open` becomes false. The implementation plan should treat `open/closed` and `mounted/unmounted` as separate concerns.

### 3. Reframe presets as optional shortcuts

The configure step must stop behaving like a preset gate.

New interaction model:

- presets remain visible near the top
- preset selection is optional
- presets only mutate default option values
- every relevant option remains editable after preset application
- the user can continue without choosing any preset

Required helper copy:

```text
Presets are starting points. You can change any settings below.
```

This copy should be persistent and not hidden behind a tooltip.

### 4. Expose all options inline in the wizard configure step

The configure step should include four sections in one place:

```text
+--------------------------------------------------+
| Presets (optional shortcuts)                     |
| [Quick] [Balanced] [Deep] [Reset]               |
| Presets are starting points. You can change...   |
+--------------------------------------------------+

+--------------------------------------------------+
| Common options                                   |
| analysis / chunking / overwrite / storage        |
+--------------------------------------------------+

+--------------------------------------------------+
| Content-specific options                         |
| Audio      language / diarization                |
| Video      captions / audio defaults             |
| Document   OCR                                   |
+--------------------------------------------------+

+--------------------------------------------------+
| Advanced options                                 |
| Expandable, inline, fully editable               |
+--------------------------------------------------+
```

Design requirements:

- reuse the richer options panel and advanced field handling already present in the shared UI package where practical
- remove the current advanced-options placeholder from the wizard
- keep advanced controls inline in the same step instead of redirecting to another modal
- preserve all edited values when the session is hidden and resumed

### 5. Make the options step viewport-safe

The configure step must remain usable on constrained viewports.

Required behavior:

- the wizard modal body is scroll-constrained
- long option sets remain reachable on shorter laptop screens
- the user never loses access to the lower option groups or navigation actions because the modal body overflows without scrolling

The scroll target should be the actual quick-ingest modal body, not a page-level fallback element.

### 6. Resume the same session from the normal trigger

The normal `Quick Ingest` button should reopen the existing session when one exists. It should not silently create a fresh session while work is queued, processing, or completed.

Trigger behavior:

- no existing session:
  - click opens a new draft session
- queued session exists:
  - click reopens queued items and current options
- processing session exists:
  - click reopens live progress
- completed or partial-failure session exists:
  - click reopens results and status

The trigger should also reflect session state, for example:

- `2 queued`
- `3 processing`
- `4 completed`
- `1 failed`

The existing queued-count badge store can be expanded or fed from the new session store rather than remaining a disconnected summary.

The existing secondary header action also needs an explicit role:

- keep a secondary CTA only for the `draft with queued items` state
- rename it to something unambiguous, for example `Start queued ingest`
- this action should jump directly into the existing session and begin processing
- once a session is already processing or completed, remove the secondary CTA so the main `Quick Ingest` trigger remains the only reopen action

### 7. Hide versus destroy

Dismissing the modal should hide the session UI, not destroy the session state.

Lifecycle sketch:

```text
[Draft]
   |
   v
[Processing]
   |
   +--> dismiss modal --> [Hidden but resumable]
   |                          |
   |                          v
   |                   click Quick Ingest
   |                          |
   |                          v
   +------------------> [Reopen same session]
   |
   +--> [Completed / Partial failure / Cancelled]
                   |
                   v
         session remains reopenable
```

Rules:

- dismiss during processing hides the modal and keeps processing active
- dismiss during queued or completed states hides the modal and preserves state
- completed sessions stay reopenable until the user explicitly clears them or starts a new session
- starting a new ingest from a completed session should be explicit, for example via `New ingest`, not an implicit reset

### 8. Refresh persistence semantics

The session should survive route changes and full page refreshes within the same tab.

Restore expectations:

- URL-only sessions restore fully after refresh
- processing state restores from stored snapshot plus resumed runtime updates when possible
- completed sessions restore with their final results
- local-file queue items restore as stubs and may require reattach if the underlying `File` objects were lost during refresh

The implementation should prefer deterministic restore over pretending local files still exist when they do not.

Reattachment contract for in-flight processing:

- persist enough backend-tracking metadata to reattach after refresh, not just the UI step
- required persisted identifiers include:
  - quick-ingest session id
  - submission mode
  - started-at timestamp
  - tracked batch id and job ids for direct backend-tracked sessions
- on reload, if the persisted session is still marked `processing` and tracking ids exist, the client should resume polling backend job status and rebuild live progress from that data
- if reattachment fails, the session must degrade into a recoverable `interrupted` or `unknown` processing state with clear UI messaging and a retry or dismiss path
- the UI must not pretend live progress is still attached when it cannot prove that

Fallback policy for queue-limit handling:

- fallback from `/api/v1/media/ingest/jobs` to `/api/v1/media/add` should happen only for recognized concurrent-job-limit `429` responses
- other `429` variants and unrelated submission failures should continue to surface as normal errors until separately designed

### 8a. Surface scope and shared-package compatibility

This work is motivated by the WebUI and must be planned as WebUI-first behavior even though the components live in the shared UI package.

Rules:

- WebUI resumable-session behavior is required in this phase
- extension behavior must not regress, because the extension also uses the same quick-ingest trigger and wizard components
- full refresh-based session rehydration is required for WebUI in this phase
- extension full-refresh rehydration is not a phase-1 requirement unless the implementation proves it can be delivered safely without complicating the WebUI path
- the implementation plan should call out any runtime guards needed so shared code can support WebUI-first persistence without breaking extension flows

### 9. End-to-end verification strategy

Add real browser end-to-end tests against the actual wizard modal used by the WebUI.

Required coverage:

1. `.mkv` upload through completion
   - add a real `.mkv`
   - configure options without relying on preset selection
   - process to a visible completed or ready state
   - dismiss and reopen
   - verify the results remain visible

2. URL ingest through completion
   - add a real URL using a stable local or self-hosted target
   - adjust options directly in the configure step
   - process to a visible completed or ready state
   - dismiss and reopen
   - verify the results remain visible

3. Queue-limit fallback
   - force `POST /api/v1/media/ingest/jobs` to return `429`
   - verify the UI does not claim the queue is full
   - verify the fallback path submits through `/api/v1/media/add`
   - verify fallback happens only for the recognized concurrent-job-limit shape

4. Options exposure on constrained viewport
   - run with a shorter viewport
   - verify all option groups are reachable
   - verify advanced options can be expanded in the wizard itself

5. Dismiss and resume during processing
   - start processing
   - dismiss the modal
   - reopen through the standard trigger
   - verify live progress and active session context are preserved

6. Refresh restore
   - refresh during URL-based queued, processing, and completed states
   - verify the session rehydrates from `sessionStorage`

7. File refresh edge case
   - refresh with queued local files before submission
   - verify stubs restore and the UI requires reattach

8. Secondary trigger semantics
   - verify the secondary header CTA appears only for queued draft sessions
   - verify it starts processing the existing queued session
   - verify it is absent once processing or results state exists

### 10. Stable ingest targets for E2E

Full completion tests should avoid flaky third-party dependencies.

Recommendations:

- prefer local or repo-controlled ingest targets for URL tests
- use deterministic fixtures for `.mkv` uploads
- separate “submission and fallback” validation from “full completion” validation when backend processing time is inherently variable

## Implementation Notes

- Keep the wizard shell and stepper, but move richer option rendering into the configure step.
- Prefer extracting reusable pieces from the older modal rather than porting the wizard into the old modal.
- Expand the quick-ingest store from badge-summary state into a proper session model.
- Persist only tab-scoped quick-ingest session state in `sessionStorage`.
- Keep background-runtime session messaging as the live source of progress truth while storing enough snapshot state to restore the UI after hide and refresh.
- Treat session-host lifetime as independent from modal visibility so close/reopen does not destroy in-flight state.
- Plan WebUI-first persistence explicitly, with extension-safe guards where shared package code paths differ.

## Risks

- If both the old modal and wizard continue evolving in parallel, regressions will recur because product behavior will diverge between two implementations.
- Full real-processing E2E can become slow if it targets unstable or externally hosted URLs.
- Refresh restore for local files can look broken unless the UI clearly communicates when reattach is required.
- Rehydrating processing state without persisted job identifiers would create false “live” status and is not acceptable.
- Shared-package changes can regress the extension if WebUI-first persistence is implemented without runtime scoping.

## Acceptance Criteria

- The WebUI quick-ingest button opens one canonical wizard modal.
- Users can process content without selecting any preset.
- All supported quick-ingest options are reachable within the wizard configure step.
- Dismissing the modal does not lose queued, processing, or completed session state.
- Reopening `Quick Ingest` restores the same session.
- Completed sessions stay visible until explicitly replaced or cleared.
- Refreshing an in-flight WebUI session reattaches using persisted backend tracking metadata or degrades honestly into an interrupted state.
- `.mkv` upload and URL ingest both have real E2E coverage through processing completion.
- Queue-limit fallback is covered and does not surface a misleading queue-full error to the user.
- The secondary header CTA has a single unambiguous meaning and does not compete with the main resume trigger outside the queued-draft state.
