# Implementation Plan: Notes Page - AI-Powered Features

## Scope

Components/pages: note title assist UX, optional strategy controls, future content-assist actions, monitoring visibility hooks.
Finding IDs: `8.1` through `8.4`

## Finding Coverage

- Expose existing backend title suggestion capability: `8.1`
- Strategy transparency and user control: `8.2`
- Content-level assist opportunities: `8.3`
- Topic monitoring visibility gap: `8.4`

## Stage 1: Title Generation UI Activation
**Goal**: Ship immediate value by wiring existing backend capability.
**Success Criteria**:
- Add `Generate Title` action near title input.
- Call `/notes/title/suggest` and present suggestion preview before applying.
- Handle loading/error states without disrupting manual editing.
**Tests**:
- Integration tests for request/response wiring and apply/reject flow.
- Component tests for button disabled/loading states.
- Fallback tests for empty content and backend unavailability.
**Status**: Complete

## Stage 2: Strategy Configuration Surface
**Goal**: Clarify and optionally expose heuristic vs LLM strategy behavior.
**Success Criteria**:
- Show strategy selector only when server indicates multiple strategies are available.
- Persist per-user preference if strategy switching is enabled.
- Hide/lock controls when policy disables LLM strategy.
**Tests**:
- Contract tests for strategy capability flags.
- Component tests for conditional selector rendering.
- Persistence tests for strategy preference retention.
**Status**: Complete

## Stage 3: Content Assistance Extensions
**Goal**: Introduce optional AI actions for drafting acceleration.
**Success Criteria**:
- Add editor actions for summarize, expand outline, and suggest keywords.
- Require explicit user acceptance before applying generated edits.
- Track action provenance in UI (generated vs manual edits).
**Tests**:
- Integration tests for each action pipeline and apply/discard behavior.
- Safety tests for no silent content mutation.
- Prompt contract tests for deterministic output envelope handling.
**Status**: Complete

## Stage 4: Topic Monitoring User Feedback
**Goal**: Surface moderation/monitoring outcomes in a user-meaningful way.
**Success Criteria**:
- Display non-blocking alerts when monitoring flags note content.
- Provide actionable next-step guidance in alert messaging.
- Avoid exposing internal-only policy details or sensitive scoring internals.
**Tests**:
- Integration tests for monitoring result surfacing on save.
- Accessibility tests for alert semantics (`aria-live`).
- Privacy tests confirming no sensitive internals leak in UI copy.
**Status**: Complete

## Dependencies

- Toolbar placement should coordinate with Plan 02 editor header/action layout.
- Keyword suggestion flow should reuse tagging behavior from Plan 03.

## Progress Notes (2026-02-18)

- Completed Stage 1 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Added `Generate title` action adjacent to the title input.
  - Wired request flow to `POST /api/v1/notes/title/suggest`.
  - Added suggestion preview-and-apply confirmation before mutating the title field.
  - Added loading/disabled/error handling that preserves manual editing context.
- Added Stage 1 verification in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage10.ai-title.test.tsx`:
  - Verifies suggestion request/response apply flow.
  - Verifies reject/keep-current behavior.
  - Verifies backend failure error handling.
- Completed Stage 2 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Added server-policy probe for `/api/v1/admin/notes/title-settings` with safe fallback.
  - Added strategy selector that only renders when more than one strategy is allowed.
  - Persisted selected strategy via `NOTES_TITLE_SUGGEST_STRATEGY_SETTING`.
  - Wired effective strategy into `/api/v1/notes/title/suggest` payloads.
- Added Stage 2 verification in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage10.ai-title.test.tsx`:
  - Verifies selector visibility when switching is enabled.
  - Verifies heuristic fallback behavior when LLM strategy is disabled by policy.
  - Verifies preference persistence when strategy changes.
- Completed Stage 3 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Added assist actions for summarize, expand outline, and suggest keywords.
  - Added explicit confirmation before applying any generated content or keyword mutations.
  - Added edit provenance metadata in the footer to distinguish manual vs generated edits.
- Added Stage 3 verification in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage10.ai-content-assist.test.tsx`:
  - Verifies summarize apply flow and manual-edit provenance reset.
  - Verifies summarize reject flow keeps content unchanged.
  - Verifies keyword suggestion confirm flow and generated provenance label.
- Completed Stage 4 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Added non-blocking monitoring alert lookup after note save.
  - Added in-editor monitoring banner with severity-aware copy and actionable guidance.
  - Kept messages privacy-safe by avoiding internal rule/pattern exposure.
- Added Stage 4 verification in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage10.ai-monitoring-feedback.test.tsx`:
  - Verifies monitoring banner surfacing on save when alerts are detected.
  - Verifies save success remains unaffected when monitoring endpoint access fails.
  - Verifies accessibility semantics via `role=\"alert\"` and `aria-live=\"polite\"`.
