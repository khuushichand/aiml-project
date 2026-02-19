# Implementation Plan: Knowledge QA - Source Cards and Retrieved Documents

## Scope

Components: `apps/packages/ui/src/components/Option/KnowledgeQA/SourceList.tsx`, `apps/packages/ui/src/components/Option/KnowledgeQA/SourceCard.tsx`, source keyboard shortcuts
Finding IDs: `3.1` through `3.13`

## Finding Coverage

- Preserve effective responsive layout: `3.1`
- Expand sorting/filtering and metadata meaning: `3.2`, `3.3`, `3.5`, `3.11`
- Improve card interaction quality: `3.4`, `3.6`, `3.7`, `3.8`, `3.9`, `3.10`
- Handle scale and semantics: `3.12`, `3.13`

## Stage 1: Semantic Structure and Baseline Preservation
**Goal**: Keep the strong grid while adding screen-reader structure.
**Success Criteria**:
- Current 1-column/2-column responsive layout remains unchanged (`3.1`).
- Source collection exposes list semantics (`role=list/listitem` or equivalent article semantics) (`3.13`).
**Tests**:
- Component tests for grid class regression.
- Accessibility tests asserting list/article roles and card discoverability.
**Status**: Complete (2026-02-18)

## Stage 2: Sorting, Filtering, and Metadata Clarity
**Goal**: Let researchers reframe result sets quickly with richer metadata.
**Success Criteria**:
- Sort options include relevance, title, date, and cited-first with suitable UI control (`3.2`).
- Relevance badge adds calibrated visual semantics (label/color) beyond raw percentage (`3.3`).
- Source type filters with counts are available and composable (`3.11`).
- Card metadata includes chunk position, friendly source-type labels, and full-title affordance (`3.5`).
**Tests**:
- Unit tests for sort comparators and filter reducers.
- Component tests for filter chip counts and active state.
- Snapshot/visual tests for relevance badge variants.
**Status**: Complete (2026-02-18)

## Stage 3: Source Card Action and Readability Upgrades
**Goal**: Improve on-card comprehension and task-specific actions.
**Success Criteria**:
- Uncited cards are visually de-emphasized without harming readability (`3.4`).
- Excerpts support expand/collapse for full chunk review (`3.6`).
- "Ask About This" supports action variants (detail/summary/key quotes) (`3.7`).
- Copy action supports raw text and formatted citation variants (`3.8`).
- URL-open affordance remains consistent when URL absent (explicit disabled/help state or documented omission) (`3.9`).
- Shortcut discoverability improves with a dedicated legend overlay (`3.10`).
**Tests**:
- Component tests for expand/collapse and overflow behavior.
- Integration tests for ask-action menu wiring into query input.
- Clipboard tests for citation-format output.
- Keyboard tests for shortcut help modal and conflict-safe handling.
**Status**: Complete (2026-02-18)

## Stage 4: Large-Result Scalability and Rendering Performance
**Goal**: Keep source browsing responsive for high result counts.
**Success Criteria**:
- Results use progressive pagination or virtualization beyond threshold (`3.12`).
- UI shows current visible count vs total count.
- Scrolling and keyboard navigation remain smooth after scaling changes.
**Tests**:
- Integration tests for show-more pagination behavior.
- Performance test/benchmark for 20–50 result render path.
- E2E keyboard navigation test across paginated/virtualized lists.
**Status**: Complete (2026-02-18)

## Dependencies

- Sorting/filter metadata must align with Search Details and future comparison capabilities in Missing Functionality plan.

## Implementation Notes (2026-02-18)

- Added shared source-list utilities for source-type labeling/counting, filters, sort comparators, relevance calibration labels, metadata date parsing, and chunk-position formatting.
- Upgraded source-list interactions with dropdown sort modes (relevance/title/date/cited-first), type filter chips with counts, visible/total count summary, and incremental "Show more" pagination.
- Improved source-card readability and actions: uncited de-emphasis, excerpt expand/collapse, ask-template variants, copy citation option, and explicit disabled open affordance when URL is absent.
- Added shortcut legend overlay (`?`) and preserved keyboard navigation behavior for visible cards.
- Preserved list semantics and accessibility guardrails validated by existing and new tests.

## Verification (2026-02-18)

- `bunx vitest run src/components/Option/KnowledgeQA/__tests__/sourceListUtils.test.ts src/components/Option/KnowledgeQA/__tests__/SourceList.accessibility.test.tsx src/components/Option/KnowledgeQA/__tests__/SourceList.feedback.test.tsx src/components/Option/KnowledgeQA/__tests__/SourceList.viewer.test.tsx src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx`
- `bunx vitest run src/components/Option/KnowledgeQA/__tests__`
