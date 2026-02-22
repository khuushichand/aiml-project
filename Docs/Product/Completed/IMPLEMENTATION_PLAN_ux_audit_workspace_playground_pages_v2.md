# Implementation Plan: UX Audit v2 Workspace and Playground Pages

## Scope

Pages: Flashcards, Quiz, Collections, Kanban, Data Tables, Watchlists, Evaluations, Chunking Playground, Moderation Playground, Workspace Playground, Document Workspace, Workflow Editor, Documentation  
Issue IDs: `FLASH-1`, `FLASH-2`, `QUIZ-1`, `KANBAN-1`, `DT-1`, `DT-2`, `WATCH-1`, `EVAL-1`, `CHUNK-1`, `CHUNK-2`, `MOD-1`, `MOD-2`, `WP-1`, `WP-2`, `DOC-1`, `DOC-2`, `DOC-3`, `DW-1`, `WE-1`, `WE-2`, `WE-3`, `WE-4`

## Issue Grouping Coverage

- Content accuracy and affordance issues: `FLASH-1`, `QUIZ-1`, `KANBAN-1`, `WATCH-1`, `DOC-3`
- Mobile usability issues: `FLASH-2`, `DT-2`, `CHUNK-2`, `WP-2`, `WE-2`
- Template leaks/accessibility issues: `DOC-1`, `DOC-2`, `DW-1`, `WE-4`, `WE-3`
- Visual consistency/progressive disclosure: `WE-1`, `MOD-1`, `MOD-2`
- Positive patterns to preserve: `DT-1`, `EVAL-1`, `CHUNK-1`, `WP-1`

## Stage 1: Content Integrity and State Logic
**Goal**: Make page content match labels, tab intent, and empty-state context.
**Success Criteria**:
- Flashcards first card content is actual user/workspace content, not tutorial residue.
- Quiz and Kanban tabs/labels align with rendered state and CTA messaging.
- Watchlists/documentation empty states are specific and actionable.
- Documentation page reflects real item status with accurate counts.
**Tests**:
- Integration tests for tab-content mapping and empty-state copy.
- Seeded data tests for flashcards/kanban/documentation initial render.
**Status**: Complete

## Stage 2: Mobile Workflow and Touch Target Remediation
**Goal**: Ensure critical workflows remain usable on 375px devices.
**Success Criteria**:
- High-priority actions remain above fold or discoverable via sticky/overflow controls.
- Icon actions meet 44x44px target minimum.
- Workflow editor and chunking/settings panes remain reachable without overlap.
- Workspace copy references mobile UI correctly ("Sources tab" style wording).
**Tests**:
- Mobile Playwright flows for flashcards, chunking, workflow editor, workspace.
- Bounding-box assertions for tap-target dimensions.
**Status**: Complete

## Stage 3: Template and Accessibility Hardening
**Goal**: Remove raw placeholders and ambiguous icon-only controls.
**Success Criteria**:
- `{{extensionPath}}`, `{{serverPath}}`, and `{{path}}` never appear in UI.
- Document Workspace and Workflow icon controls include labels/tooltips and `aria-label`.
- Label casing is standardized (`LLM` naming consistency).
**Tests**:
- Component tests for template fallback rendering.
- Accessibility tests for labeled controls and keyboard focus.
- String/content lint checks for critical terminology.
**Status**: Complete

## Stage 4: Visual Language and Guidance Refinement
**Goal**: Reduce cognitive load and unify visual semantics across advanced tools.
**Success Criteria**:
- Workflow editor color semantics align with broader design token strategy.
- Moderation onboarding callout is dismissible and stateful.
- High-density views use progressive disclosure for advanced controls.
**Tests**:
- Visual regression tests for workflow/moderation surfaces.
- Interaction tests for onboarding-callout dismissal persistence.
**Status**: Complete

## Stage 5: Preserve and Protect High-Quality Experiences
**Goal**: Keep strong pages strong while adjacent issues are fixed.
**Success Criteria**:
- Data Tables, Evaluations, Chunking, and Workspace strengths remain intact.
- Regression guardrails prevent quality backslide on known-good interactions.
**Tests**:
- Golden-path interaction tests for positive exemplars.
- Snapshot diffs reviewed against approved baseline.
**Status**: Complete

## Progress Notes (2026-02-17)
- Stage 2 started with mobile wording fix for Workspace Playground guidance copy (`WP-2`):
  - Replaced hardcoded "left pane" hints with adaptive copy:
    - mobile: `Sources tab`
    - desktop: `Sources pane`
  - Updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorkspacePlayground/source-location-copy.ts`
- Added regression test coverage:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts`
- Stage 2 workflow editor mobile layout remediation implemented (`WE-2`):
  - desktop keeps persistent sidebar panel; non-desktop now opens node/config/execution panels in a left drawer via toolbar action, preventing node-library/canvas overlap.
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/WorkflowEditor/WorkflowEditor.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx`
- Stage 3 started with documentation template fallback guard coverage (`DOC-1`, `DOC-2`):
  - added component regression test to ensure placeholder tokens do not render on the documentation page:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx`
- Stage 3 workflow-editor accessibility label hardening implemented (`WE-4`):
  - validation badge/action now includes issue counts in the icon-only control `aria-label` (for example: `Validation issues: 2 warnings`).
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/WorkflowEditor/WorkflowEditor.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx`
- Stage 3 workflow-editor casing consistency remediation implemented (`WE-3`):
  - fallback step-type labels now preserve acronym casing for LLM-derived step names (`llm` -> `LLM`, `llm_compare` -> `LLM Compare`) to avoid `Llm`/`LLM Prompt` inconsistency.
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/WorkflowEditor/step-registry.ts`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/WorkflowEditor/__tests__/step-registry.test.ts`
- Stage 3 document-workspace icon-label remediation implemented (`DW-1`):
  - left/right workspace sidebar tabs now use icon+text labels with retained tooltips and explicit `aria-label`, replacing ambiguous icon-only affordances.
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/DocumentWorkspace/DocumentWorkspacePage.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/DocumentWorkspace/TabIconLabel.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx`
- Stage 1 kanban empty-state copy remediation implemented (`KANBAN-1`):
  - empty state guidance now reflects whether boards already exist:
    - no boards: `No boards yet. Create your first board`
    - boards exist with none selected: `Select an existing board to get started`
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KanbanPlayground/index.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx`
- Stage 1 quiz tab-intent remediation implemented (`QUIZ-1`):
  - `Take Quiz` empty-state copy now reflects take-flow intent (no quizzes available to take) while still offering generate/create actions.
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Quiz/tabs/TakeQuizTab.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx`
- Stage 1 watchlists empty-state remediation implemented (`WATCH-1`):
  - sources tab now shows a unified first-use empty state when both groups and sources are empty, removing the prior dual-pane barren empty presentation.
  - table empty messaging now adapts for filtered vs. first-use scenarios.
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Watchlists/SourcesTab/SourcesTab.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Watchlists/SourcesTab/empty-state.ts`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts`
- Stage 1 documentation functional-fallback remediation implemented (`DOC-3`):
  - documentation tabs now provide inline fallback documents when runtime doc auto-discovery is unavailable, preventing the prior `0 items / non-functional` state.
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Documentation/DocumentationPage.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx`
- Stage 2 data-tables touch-target remediation implemented (`DT-2`):
  - icon-only row actions (`View`, `Export`, `Delete`) now expose explicit labels and mobile-safe `44x44` touch target minimum sizing.
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/DataTables/DataTablesList.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/DataTables/ExportMenu.tsx`
- Stage 2 chunking mobile workflow remediation implemented (`CHUNK-2`):
  - single-mode layout now renders settings before result output on non-desktop viewports so critical options remain reachable during mobile workflows.
  - desktop layout preserves existing split (results pane + right settings pane) behavior.
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/ChunkingPlayground/index.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx`
- Stage 1 flashcards content-integrity remediation implemented (`FLASH-1`):
  - review queue now scans a candidate window per due-status bucket and prefers non-instructional cards, reducing first-card tutorial residue caused by generative preamble content.
  - added tutorial-residue detection utility and unit coverage for residue detection + fallback behavior.
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Flashcards/utils/review-card-hygiene.ts`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts`
- Stage 2 flashcards mobile CTA discoverability remediation implemented (`FLASH-2`):
  - review tab now surfaces a persistent, above-fold `Create a new card` primary action next to deck selection, eliminating reliance on below-fold discovery.
  - added interaction test to assert CTA presence and click-through behavior.
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Flashcards/tabs/ReviewTab.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx`
- Stage 4 workflow visual-semantics remediation implemented (`WE-1`):
  - workflow category palette now aligns with the app’s blue/indigo visual language (removed prior purple/orange emphasis for AI/control categories across node cards, palette chips, and minimap colors).
  - added regression assertions for category color mapping.
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/WorkflowEditor/step-registry.ts`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/WorkflowEditor/NodePalette.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/WorkflowEditor/WorkflowCanvas.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/WorkflowEditor/nodes/WorkflowNode.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/WorkflowEditor/__tests__/step-registry.test.ts`
- Stage 4 moderation onboarding/progressive-disclosure validation coverage added (`MOD-1`, `MOD-2`):
  - added component-level regression tests confirming onboarding callout dismissal persistence and advanced-mode progressive disclosure behavior.
  - updated files:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx`
- Added Data Tables accessibility regression coverage:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx`
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx`
- Validation run:
  - `cd apps/packages/ui && bunx vitest run src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `5 passed` test files, `14 passed` tests.
- Validation rerun after `DT-2`:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `7 passed` test files, `16 passed` tests.
- Validation rerun after `WE-3`:
  - `cd apps/packages/ui && bunx vitest run src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx`
  - Result: `3 passed` test files, `21 passed` tests.
- Validation rerun after `KANBAN-1`:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `8 passed` test files, `27 passed` tests.
- Validation rerun after `QUIZ-1`:
  - `cd apps/packages/ui && bunx vitest run src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `9 passed` test files, `28 passed` tests.
- Validation rerun after `WATCH-1`:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `10 passed` test files, `31 passed` tests.
- Validation rerun after `DOC-3`:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `10 passed` test files, `31 passed` tests.
- Validation rerun after `CHUNK-2`:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `11 passed` test files, `33 passed` tests.
- Validation rerun after `DW-1`:
  - `cd apps/packages/ui && bunx vitest run src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `12 passed` test files, `34 passed` tests.
- Validation rerun after `FLASH-1` + `FLASH-2`:
  - `cd apps/packages/ui && bunx vitest run src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `14 passed` test files, `39 passed` tests.
- Validation rerun after `WE-1` + `MOD-1` + `MOD-2`:
  - `cd apps/packages/ui && bunx vitest run src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/utils/__tests__/template-guards.test.ts`
  - Result: `16 passed` test files, `46 passed` tests.
- Stage 5 positive-pattern regression guardrails completed (`DT-1`, `EVAL-1`, `CHUNK-1`, `WP-1`):
  - Data Tables and Evaluations golden-path/empty-state protections retained:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/DataTables/__tests__/DataTablesPage.golden-path.test.tsx`
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/EvaluationsTab.empty-state.test.tsx`
  - Added chunking positive-pattern tests for multi-input and mode navigation:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.golden-path.test.tsx`
  - Added workspace desktop 3-pane structural guardrail test:
    - `/Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx`
- Stage 5 validation run:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/DataTables/__tests__/DataTablesPage.golden-path.test.tsx src/components/Option/Evaluations/tabs/__tests__/EvaluationsTab.empty-state.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.golden-path.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx`
  - Result: `5 passed` test files, `8 passed` tests.
- Expanded workspace/playground rerun after Stage 5 completion:
  - `cd apps/packages/ui && bunx vitest run src/components/Flashcards/utils/__tests__/review-card-hygiene.test.ts src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlayground.progressive-disclosure.test.tsx src/components/WorkflowEditor/__tests__/step-registry.test.ts src/components/WorkflowEditor/__tests__/NodePalette.test.tsx src/components/WorkflowEditor/__tests__/WorkflowEditor.responsive.test.tsx src/components/DocumentWorkspace/__tests__/TabIconLabel.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.responsive-layout.test.tsx src/components/Option/ChunkingPlayground/__tests__/ChunkingPlayground.golden-path.test.tsx src/components/Option/DataTables/__tests__/DataTablesPage.golden-path.test.tsx src/components/Option/Evaluations/tabs/__tests__/EvaluationsTab.empty-state.test.tsx src/components/Option/Documentation/__tests__/DocumentationPage.template-fallback.test.tsx src/components/Option/Watchlists/SourcesTab/__tests__/empty-state.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Option/KanbanPlayground/__tests__/KanbanPlayground.empty-state.test.tsx src/components/Option/DataTables/__tests__/DataTablesList.a11y.test.tsx src/components/Option/DataTables/__tests__/ExportMenu.a11y.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/utils/__tests__/template-guards.test.ts`
  - Result: `20 passed` test files, `52 passed` tests.
