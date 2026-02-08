## Stage 1: Harden QA Response Normalization
**Goal**: Ensure QA Search consistently renders retrieved chunks/metadata across all supported RAG response shapes.
**Success Criteria**:
- `useQASearch` accepts `documents`, `results`, and `docs` payload variants.
- Citations/timings/answer fields still normalize correctly with partial/missing fields.
- No regression in current `documents`-first behavior.
**Tests**:
- Add `useQASearch` unit tests for response variants (`documents`, `results`, `docs`, empty payload).
- Add timeout/error-path test for `runQASearch`.
**Status**: Complete

## Stage 2: Complete QA Search UX Gaps
**Goal**: Align QA tab behavior with plan expectations for answer rendering and chunk list behavior.
**Success Criteria**:
- Generated answer renders markdown safely (not plain-text only).
- Source chunk list supports deterministic sorting (default + alternate mode as specified).
- Existing copy/insert/pin actions remain functional.
**Tests**:
- Component tests for `GeneratedAnswerCard` markdown output.
- Component tests for `SourceChunksList` sort behavior.
- Interaction tests for copy/insert/pin after sorting.
**Status**: Complete

## Stage 3: Add QA Chunk Preview Integration
**Goal**: Make preview modal usable from QA source chunks, not only file-search results.
**Success Criteria**:
- QA chunk cards include a preview action.
- QA preview routes through shared `KnowledgePanel` preview modal.
- Preview modal actions (insert/ask) work for QA-derived items.
**Tests**:
- Component/integration test proving QA chunk -> preview modal open.
- Test insert/ask actions from modal for QA chunk content.
**Status**: Complete

## Stage 4: Finish i18n + Footer Logic Compliance
**Goal**: Remove fallback-only strings and align footer behavior with the staged-settings design.
**Success Criteria**:
- Add missing `sidepanel.knowledge.tabs.qaSearch`, `sidepanel.knowledge.tabs.fileSearch`, `sidepanel.qaSearch.*`, and `sidepanel.fileSearch.*` keys (minimum English locale; others as required by project policy).
- Footer behavior is explicitly scoped to settings-dirty state and tab context (including apply/search behavior by active tab).
- No untranslated key leakage in UI.
**Tests**:
- Locale key presence tests for new keys.
- UI tests for footer visibility/enabled/disabled matrix by tab and dirty state.
**Status**: Complete

## Stage 5: Test Suite Restructure and Regression Coverage
**Goal**: Implement the planned hook test split and close regression gaps in tab routing and compatibility behavior.
**Success Criteria**:
- Replace monolithic helper-only coverage with dedicated `useFileSearch.test.ts` and `useQASearch.test.ts`.
- Preserve helper tests where still valuable, but ensure behavior-level coverage exists for both new hooks.
- Add tests for `openTab=\"search\" -> \"qa-search\"` mapping and tab keyboard nav (`1/2/3/4`).
**Tests**:
- `useFileSearch.test.ts` (media filters, attach state tracking, search payload).
- `useQASearch.test.ts` (request building, normalization, answer/chunk actions).
- `KnowledgePanel`/`KnowledgeTabs` tests for backward compatibility + keyboard switching.
**Status**: Complete

## Execution Notes
**Order**:
1. Stage 1 (data-contract safety first)
2. Stage 2 and Stage 3 (QA UX parity)
3. Stage 4 (i18n + footer behavior)
4. Stage 5 (test architecture + regression hardening)

**Definition of Done**:
- All five stages marked Complete.
- New/updated tests pass locally for `apps/packages/ui`.
- No known plan-item gaps remain from the identified issue list.
