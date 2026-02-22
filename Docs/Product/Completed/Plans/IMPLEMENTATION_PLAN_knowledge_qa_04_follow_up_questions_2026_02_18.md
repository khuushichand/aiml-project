# Implementation Plan: Knowledge QA - Follow-Up Questions

## Scope

Components: `apps/packages/ui/src/components/Option/KnowledgeQA/FollowUpInput.tsx`, `apps/packages/ui/src/components/Option/KnowledgeQA/index.tsx`, thread/message presentation components
Finding IDs: `4.1` through `4.8`

## Finding Coverage

- Preserve clear threading guidance: `4.3`
- Improve input placement, clarity, and accessibility: `4.1`, `4.2`, `4.7`, `4.8`
- Deliver thread visibility and conversational controls: `4.4`, `4.5`, `4.6`

## Stage 1: Follow-Up Entry UX and Accessibility Baseline
**Goal**: Make follow-up actions discoverable and reachable across screen sizes.
**Success Criteria**:
- Follow-up input is reachable without full source-list traversal (sticky or duplicated placement strategy) (`4.1`).
- New Topic affordance includes explicit text or equivalent discoverability treatment (`4.2`).
- Follow-up field remains visible in disabled/queued state during active search (`4.7`).
- Follow-up input has explicit accessible labeling (`4.8`).
**Tests**:
- Responsive integration tests for sticky/duplicated follow-up placement.
- Component tests for queued-state behavior while search is active.
- Accessibility test asserting follow-up input naming.
**Status**: Complete

## Stage 2: Multi-Turn Inline Conversation Rendering
**Goal**: Expose the full Q&A thread in main content for research continuity.
**Success Criteria**:
- Prior question/answer turns render inline above current exchange (`4.4`).
- Each turn includes query text, answer preview/full toggle, and source/citation summary.
- Thread rendering does not regress current latest-answer/source components.
**Tests**:
- Component tests for thread list rendering and collapse/expand states.
- Integration tests for new question -> follow-up -> inline history continuity.
- E2E test validating that previous turns remain visible after multiple asks.
**Status**: Complete

## Stage 3: Conversational Branching and Re-Ask Enhancements
**Goal**: Enable iterative research from prior turns without losing context.
**Success Criteria**:
- Previous question can be selected and loaded for editing/re-run (`4.6`).
- Branching model is designed and staged (feature-flag or deferred milestone) for parallel follow-up paths (`4.5`).
- Thread model documents linear vs branch semantics and persistence rules.
**Tests**:
- Unit tests for question rehydrate/edit flow.
- Integration tests for re-run preserving expected context boundaries.
- Model/reducer tests for branch metadata if enabled.
**Status**: Complete

## Stage 4: Guidance Regression Protection
**Goal**: Preserve existing clear explanation of follow-up context behavior.
**Success Criteria**:
- Existing helper text intent remains visible and accurate (`4.3`).
- Any updated copy remains concise and i18n-ready.
**Tests**:
- Component snapshot tests for helper copy presence.
- i18n key presence test if copy moves to locale files.
**Status**: Complete

## Dependencies

- Multi-turn rendering should align with History restoration and Streaming plans to avoid duplicate conversation models.
