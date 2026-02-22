# Implementation Plan: Knowledge QA - AI Answer Display

## Scope

Components: `apps/packages/ui/src/components/Option/KnowledgeQA/AnswerPanel.tsx`, answer rendering helpers, citation focus interactions, Knowledge QA provider answer state
Finding IDs: `2.1` through `2.11`

## Finding Coverage

- Preserve current hierarchy strengths: `2.1`
- Improve citation interaction and focus lifecycle: `2.2`, `2.3`
- Upgrade answer rendering and loading/error clarity: `2.4`, `2.5`, `2.6`, `2.7`, `2.11`
- Add answer actions and feedback loops: `2.8`, `2.9`, `2.10`

## Stage 1: Citation Interaction and Mobile Usability
**Goal**: Make citation controls touch-friendly and reduce stale focus state.
**Success Criteria**:
- Citation markers meet mobile-friendly tap target sizing while preserving inline readability (`2.2`).
- Source highlight focus auto-clears/fades after timeout with manual override retained (`2.3`).
- Existing citation visual hierarchy remains intact (`2.1`).
**Tests**:
- Component tests for citation button sizing class behavior by viewport/breakpoint.
- Integration test for click citation -> scroll/focus -> auto-clear lifecycle.
- Visual regression snapshots for cited/uncited marker states.
**Status**: Complete

## Stage 2: Markdown-Capable Answer Rendering with Interactive Citations
**Goal**: Preserve rich model output formatting while keeping interactive citation jumps.
**Success Criteria**:
- Answers render markdown structures (lists, code blocks, tables) rather than flat text (`2.4`).
- Citation token replacement still yields accessible interactive controls inside rendered content (`2.4`).
- Rendering path safely handles malformed markdown/citation edge cases.
**Tests**:
- Unit tests for markdown + citation token transformation pipeline.
- Component tests for list/code/table rendering fidelity.
- Accessibility tests for citation button labels and tab order in rendered content.
**Status**: Complete

## Stage 3: Progressive Status and Actionable Failure States
**Goal**: Replace static waiting/error UX with informative, recoverable states.
**Success Criteria**:
- Loading state communicates stage and/or elapsed time during long queries (`2.5`).
- Error presentation maps known failure classes to targeted guidance (`2.6`).
- No-answer/generated-disabled path includes a direct settings action (`2.7`).
- Answer header indicates when web fallback contributed sources (`2.11`).
**Tests**:
- Integration tests with mocked state stages and elapsed timer rendering.
- Unit tests for error-classification mapper and user-facing copy selection.
- Component test for "Enable in Settings" action wiring.
- State test asserting web-fallback indicator conditions.
**Status**: Complete

## Stage 4: Answer Utility Controls and Feedback Capture
**Goal**: Support researcher workflows beyond passive reading.
**Success Criteria**:
- Copy-answer action is present and includes citation markers in output (`2.8`).
- Answer feedback controls (up/down) persist against backend feedback identifier (`2.9`).
- Inline "Show more/Summarize" actions support per-query answer length control (`2.10`).
**Tests**:
- Clipboard action tests for copied payload formatting.
- Integration tests for feedback submit/retry/disabled states.
- Provider tests for per-query token override flow.
**Status**: Complete

## Dependencies

- Markdown rendering should be compatible with Export formatting and Accessibility plan requirements.
