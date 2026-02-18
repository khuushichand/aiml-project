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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

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
