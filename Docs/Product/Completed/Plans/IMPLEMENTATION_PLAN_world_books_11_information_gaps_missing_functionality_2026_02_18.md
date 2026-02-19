# Implementation Plan: World Books - Information Gaps and Missing Functionality

## Scope

Components: Authoring-time testing UX, entry organization model, budget visualization surfaces, AI-assisted authoring, and relationship insights.
Finding IDs: `11.1` through `11.6`

## Finding Coverage

- Highest-impact authoring loop gap: `11.1`
- Organization scalability for large lorebooks: `11.2`
- Explicit defer/backup strategy for entry history: `11.3`
- Differentiating assistance features: `11.4`
- Token budget visibility in authoring flow: `11.5`
- Entry relationship/dependency understanding: `11.6`

## Stage 1: Deliver Test-Match Workflow as Core Authoring Tool
**Goal**: Provide immediate keyword-trigger validation without entering live chat.
**Success Criteria**:
- Add test input panel in world-book management with match result breakdown.
- Show matched entries, token usage, and budget status in one run.
- Support rapid iterate/test loops with saved sample inputs per session.
**Tests**:
- Integration tests for process-context API round trip and result rendering.
- Component tests for empty/error/success states.
- UX tests for repeated-run workflow latency and state persistence.
**Status**: Complete

## Stage 2: Add Entry Grouping/Category Model
**Goal**: Improve organization for high-entry-count lorebooks.
**Success Criteria**:
- Extend entry schema with optional `group` or `category` field.
- Add group filter and group badge rendering in entry list.
- Provide migration/backfill behavior for existing entries without group values.
**Tests**:
- Backend schema/migration tests for nullable group field handling.
- API integration tests for create/update/filter by group.
- UI tests for group display and filtering behavior.
**Status**: Complete

## Stage 3: Add Budget Visualization Across Key Surfaces
**Goal**: Make budget pressure visible during authoring, not only after-the-fact.
**Success Criteria**:
- Show utilization bar in statistics modal and entries drawer header.
- Use consistent thresholds and color semantics across all views.
- Highlight over-budget conditions with explicit remediation hint.
**Tests**:
- Unit tests for utilization calculations and threshold mapping.
- Component tests for drawer-header and modal budget bars.
- Regression tests for over-budget warning rendering.
**Status**: Complete

## Stage 4: Add AI-Assisted Entry Generation
**Goal**: Reduce manual drafting burden and increase onboarding success.
**Success Criteria**:
- Add `Generate with AI` flow that turns topic prompts into keyword-content entry suggestions.
- Support review/edit-before-save workflow for generated entries.
- Log provider/model metadata for traceability of generated outputs.
**Tests**:
- Integration tests for generation request/response handling and suggestion insertion.
- Component tests for suggestion approval/rejection/edit workflows.
- Safety tests for empty/unsafe generation output handling.
**Status**: Complete

## Stage 5: Relationship Insight and Versioning Strategy
**Goal**: Improve explainability while controlling complexity growth.
**Success Criteria**:
- Add lightweight referenced-by insights based on keyword/content overlap heuristics.
- Publish decision record for entry versioning: defer full version history, rely on export snapshots for now.
- Document recovery workflow via periodic exports until deeper versioning is prioritized.
**Tests**:
- Unit tests for relationship heuristic signal generation.
- Component tests for referenced-by display and no-signal fallback.
- Documentation check ensuring versioning policy is visible in user docs.
**Status**: Complete

## Dependencies

- Stage 2 requires coordinated backend and frontend schema rollout.
- Stage 4 depends on available LLM provider configuration in target environments.
