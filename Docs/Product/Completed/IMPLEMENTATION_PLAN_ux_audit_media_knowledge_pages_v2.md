# Implementation Plan: UX Audit v2 Media and Knowledge Pages

## Scope

Pages: Media, Media Multi, Media Trash, Knowledge, Notes, Characters, Prompts, Chatbooks  
Issue IDs: `MEDIA-1`, `KNOW-1`, `KNOW-2`, `CHAR-1`, `CHAT-B1`

## Issue Grouping Coverage

- `MEDIA-1`: Error overlay masking media content
- `KNOW-1`: Positive finding to preserve (knowledge QA UX quality)
- `KNOW-2`: Mobile history sidebar width too large
- `CHAR-1`: Error text rendered in page body
- `CHAT-B1`: Chatbooks sections report "Unable to load items"

## Stage 1: Reliability Pass for Media/Knowledge Data Loads
**Goal**: Remove blocking runtime errors and ensure content states resolve correctly.
**Success Criteria**:
- Media routes render usable content without overlay interruptions.
- Characters and Chatbooks pages surface graceful error/retry states.
- No raw backend error text is displayed in normal UI regions.
**Tests**:
- Integration tests for media, characters, and chatbooks data-fetch states.
- Error-boundary tests for recoverable vs terminal load failures.
**Status**: Complete

## Stage 2: Mobile Layout Optimization
**Goal**: Improve narrow-screen usability for knowledge-focused flows.
**Success Criteria**:
- Knowledge history panel uses collapsible/drawer pattern on mobile.
- Primary query/composition area remains dominant in 375px viewport.
- Layout change does not degrade desktop split-view utility.
**Tests**:
- Mobile visual regression for knowledge route.
- Responsive layout assertions for panel width thresholds.
**Status**: Complete

## Stage 3: Chatbooks and Characters UX Recovery
**Goal**: Convert failing sections into actionable user flows.
**Success Criteria**:
- Chatbooks failed-load sections provide targeted guidance and retry options.
- Characters page handles empty/error/loading states with explicit messaging.
- API failure states include correlation ID/log hint (non-sensitive).
**Tests**:
- Mocked API tests for chatbooks partial and total failure modes.
- Characters page state-transition tests.
**Status**: Complete

## Stage 4: Preserve High-Quality Patterns
**Goal**: Protect known-strong UX in Knowledge QA while fixing adjacent issues.
**Success Criteria**:
- Knowledge QA hero/search/history interaction remains unchanged where intentional.
- Regression suite flags unintended visual/interaction drift on strong components.
**Tests**:
- Golden snapshot tests for knowledge QA core layout.
- Interaction tests for search, no-results response, and history recall.
**Status**: Complete

## Progress Notes (2026-02-17)
- Stage 1 media route reliability hardening implemented (`MEDIA-1`):
  - Added route-level error boundaries to media routes that previously lacked explicit guards:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-media-multi.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/option-media-trash.tsx`
  - Added regression coverage to ensure route boundaries remain attached:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/routes/__tests__/option-media-route-guards.test.tsx`
- Stage 1 chatbooks/characters error-state hardening implemented (`CHAT-B1`, `CHAR-1`):
  - Added shared server-error sanitization utility to prevent leaking backend endpoints/paths in normal UI error text:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/utils/server-error-message.ts`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/utils/__tests__/server-error-message.test.ts`
  - Chatbooks picker load errors now show sanitized text and expose an inline `Retry` action:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Chatbooks/ChatbooksPlaygroundPage.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx`
  - Characters load-error banner now renders sanitized server messages:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Characters/Manager.tsx`
- Stage 1 validation run:
  - `cd apps/packages/ui && bunx vitest run src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx`
  - Result: `3 passed` test files, `6 passed` tests.
- Stage 2 knowledge mobile history layout remediation implemented (`KNOW-2`):
  - Knowledge QA history sidebar now uses a mobile overlay drawer pattern instead of consuming inline horizontal space.
  - Collapsed mobile state exposes a floating open control, preserving primary query/composition area dominance.
  - Desktop behavior remains unchanged (`w-64` open sidebar, collapsed rail).
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KnowledgeQA/HistorySidebar.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx`
- Stage 2 validation run:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx`
  - Result: `4 passed` test files, `9 passed` tests.
- Expanded media/knowledge + prior wave regression rerun:
  - `cd apps/packages/ui && bunx vitest run src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.golden-path.test.tsx src/components/Option/DataTables/__tests__/DataTablesPage.golden-path.test.tsx src/components/Option/Evaluations/tabs/__tests__/EvaluationsTab.empty-state.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/utils/__tests__/template-guards.test.ts src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx`
  - Result: `24 passed` test files, `61 passed` tests.
- Stage 3 chatbooks/characters UX recovery completed (`CHAT-B1`, `CHAR-1`):
  - Added non-sensitive server log hint support with correlation ID extraction:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/utils/server-error-message.ts`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/utils/__tests__/server-error-message.test.ts`
  - Chatbooks section load-error panels now provide:
    - sanitized endpoint/path-safe error copy,
    - explicit retry action,
    - log hint with correlation ID when present.
  - Characters load-error panel now includes a log-inspection hint (with correlation ID when available).
- Stage 3 validation run:
  - `cd apps/packages/ui && bunx vitest run src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx`
  - Result: `4 passed` test files, `12 passed` tests.
- Expanded rerun after Stage 3 updates:
  - `cd apps/packages/ui && bunx vitest run src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.golden-path.test.tsx src/components/Option/DataTables/__tests__/DataTablesPage.golden-path.test.tsx src/components/Option/Evaluations/tabs/__tests__/EvaluationsTab.empty-state.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/utils/__tests__/template-guards.test.ts src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx`
  - Result: `24 passed` test files, `64 passed` tests.
- Stage 4 strong-pattern guardrails completed (`KNOW-1`):
  - Added Knowledge QA golden-layout guardrail coverage for hero/search-first and results transitions:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`
  - Added interaction guardrails for:
    - history recall selection behavior (`HistorySidebar.responsive.test.tsx`)
    - no-results/answer/citation-jump behavior (`AnswerPanel.states.test.tsx`)
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx`
- Stage 4 validation run:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx`
  - Result: `6 passed` test files, `18 passed` tests.
- Expanded rerun after Stage 4 updates:
  - `cd apps/packages/ui && bunx vitest run src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.golden-path.test.tsx src/components/Option/DataTables/__tests__/DataTablesPage.golden-path.test.tsx src/components/Option/Evaluations/tabs/__tests__/EvaluationsTab.empty-state.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/utils/__tests__/template-guards.test.ts src/utils/__tests__/server-error-message.test.ts src/components/Option/Chatbooks/__tests__/ContentTypePicker.error-state.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`
  - Result: `26 passed` test files, `70 passed` tests.
