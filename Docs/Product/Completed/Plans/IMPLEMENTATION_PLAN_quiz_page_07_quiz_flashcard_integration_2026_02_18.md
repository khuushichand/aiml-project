# Implementation Plan: Quiz Page - Quiz-to-Flashcard Integration

## Scope

Components: quiz results actions, flashcard creation APIs/workflows, `/quiz` and `/flashcards` cross-navigation
Finding IDs: `7.1` through `7.3`

## Finding Coverage

- Missed-question remediation workflow: `7.1`
- Cross-surface discoverability: `7.2`
- Unified study material generation: `7.3`

## Stage 1: Missed Questions -> Flashcards Conversion
**Goal**: Turn quiz mistakes into immediate review material.
**Success Criteria**:
- Results detail view includes `Create Flashcards from Missed Questions` action.
- Conversion maps question text/correct answer/explanation into flashcard front/back schema.
- User can choose destination deck/new deck name before creation.
**Tests**:
- API integration tests for conversion payload and created-card counts.
- Component tests for selection defaults (missed-only) and confirmation flow.
- Regression tests for duplicate prevention/idempotent conversion behavior.
**Status**: Complete

## Stage 2: Cross-Navigation Between Quiz and Flashcards
**Goal**: Connect study surfaces with contextual next-step actions.
**Success Criteria**:
- Quiz results include contextual link to related flashcard study route.
- Flashcards page includes CTA to quiz-related assessment route.
- Navigation carries contextual identifiers (quiz/deck/source) when available.
**Tests**:
- Integration tests for cross-route navigation and context hydration.
- Component tests for CTA visibility rules based on available context.
- Routing tests for handling missing/invalid referenced IDs gracefully.
**Status**: Complete

## Stage 3: Combined "Generate Study Materials" Flow
**Goal**: Support one-pass generation of quizzes and flashcard decks from a source.
**Success Criteria**:
- Generation UI offers combined study-materials option.
- Backend orchestration can create quiz + flashcards from same source selection.
- Completion summary reports created artifacts and links to both destinations.
**Tests**:
- Integration tests for dual-creation success and partial failure handling.
- Contract tests for combined generation response schema.
- UX tests for post-generation summary actions.
**Status**: Complete

## Dependencies

- Requires results drill-down readiness from `IMPLEMENTATION_PLAN_quiz_page_05_results_analytics_tab_2026_02_18.md`.
- Cross-navigation conventions should align with `IMPLEMENTATION_PLAN_quiz_page_06_cross_tab_interaction_information_flow_2026_02_18.md`.
