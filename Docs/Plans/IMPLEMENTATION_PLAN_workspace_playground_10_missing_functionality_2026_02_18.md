# Implementation Plan: Workspace Playground - Information Gaps and Missing Functionality

## Scope

Features beyond immediate UX defects: export/import, shortcuts, versioning, annotations, collaboration, templates
Finding IDs: `10.1` through `10.10`

## Finding Coverage

- Near-term high-impact functionality: `10.4`, `10.8`, `10.7`
- Research-depth capabilities: `10.2`, `10.3`, `10.6`, `10.10`
- Ecosystem and long-term scale: `10.5`, `10.9`, `10.1`

## Stage 1: Immediate Power-User Baseline
**Goal**: Ship high-value capabilities that reduce lock-in and improve speed.
**Success Criteria**:
- Workspace export/import supports structured bundle format (JSON/ZIP manifest).
- Keyboard shortcuts implemented for pane focus, new workspace, new note, submit.
- Artifacts track `previousVersionId` for regenerate lineage.
**Tests**:
- Integration tests for export/import roundtrip fidelity.
- Shortcut tests for key bindings and focus behavior.
- Unit tests for artifact version linkage creation.
**Status**: Complete

### Stage 1 Progress Notes (2026-02-18)
- Added structured workspace export/import bundle support in the workspace store, including chat session payloads and snapshot hydration.
- Added WorkspaceHeader actions for `Export Workspace` and `Import Workspace` (JSON bundle file flow).
- Expanded keyboard shortcuts:
  - `Cmd/Ctrl+1`, `Cmd/Ctrl+2`, `Cmd/Ctrl+3` for pane focus routing.
  - `Cmd/Ctrl+Shift+N` for new workspace.
  - `Cmd/Ctrl+N` for new note draft (with confirmation when note content exists).
  - `Cmd/Ctrl+Enter` submit support in chat composer.
- Added artifact lineage field `previousVersionId` and wired "Create new version" regenerate flow to set lineage.
- Added/updated tests for:
  - workspace export/import roundtrip fidelity (`workspace.test.ts`)
  - workspace shortcuts (`WorkspacePlayground.stage3.test.tsx`)
  - version-linkage in regenerate new version (`StudioPane.stage1.test.tsx`)
  - header export/import actions (`WorkspaceHeader.test.tsx`)

## Stage 2: Deep Research Workflow Features
**Goal**: Expand analytical depth and exploration flexibility.
**Success Criteria**:
- Source preview supports highlights/annotations.
- New `Compare sources` output type supports multi-source claim comparison.
- Chat branching supports variant paths from prior turns.
- Generation views show token/cost estimates and workspace cumulative totals.
**Tests**:
- Integration tests for annotation create/edit/delete lifecycle.
- Output generation tests for compare-source schema/prompt formation.
- Unit tests for conversation branch tree operations.
- Unit/integration tests for cost estimation display and aggregation.
**Status**: Complete

### Stage 2 Progress Notes (2026-02-18)
- Added source preview + annotation workflow in Sources pane:
  - Per-source modal entrypoint (`Preview & annotate`) from each source row.
  - Local highlight/annotation lifecycle: create, edit, delete per source.
  - Covered with stage test for create/edit/delete flow.
- Implemented `compare_sources` generation output end-to-end:
  - Added output type into shared workspace artifact types/config.
  - Added Studio generation handling with two-source guard, prompt, and UX affordances.
  - Added stage test coverage for disabled state + generation behavior + usage metrics.
- Wired chat branching and variant exploration in Chat pane:
  - Connected `PlaygroundMessage` branch action to `createChatBranch(index)`.
  - Connected variant pager callbacks (`onSwipePrev`/`onSwipeNext`) to in-place variant switching.
  - Added stage tests for branch routing and variant switching behavior.
- Extended generation usage visibility:
  - Added estimated token/cost model and usage extraction on generation results.
  - Added cumulative workspace usage summary and per-artifact usage display in Studio outputs.
  - Covered by Stage 2 studio tests.
- Validation:
  - `bunx vitest run src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx` (all passing).

## Stage 3: Templates, Citation Export, and Collaboration Roadmap
**Goal**: Improve onboarding repeatability and external interoperability.
**Success Criteria**:
- Workspace templates ship with at least three presets.
- Citation export supports BibTeX for workspace source set.
- Collaboration design and phased server-sync implementation plan documented.
**Tests**:
- Integration tests for template bootstrap and initial state correctness.
- Unit tests for BibTeX generation from source metadata.
- Contract tests for future sync payload shape/versioning.
**Status**: Complete

### Stage 3 Progress Notes (2026-02-18)
- Confirmed workspace template presets and create-from-template flow:
  - Presets in `WorkspaceHeader` utility layer (`WORKSPACE_TEMPLATE_PRESETS`) include:
    - `literature_review`
    - `interview_analysis`
    - `product_brief`
  - Workspace menu action seeds starter note content/keywords after template selection.
- Confirmed BibTeX citation export for workspace sources:
  - BibTeX serialization helpers:
    - `buildWorkspaceBibtex(...)`
    - `createWorkspaceBibtexFilename(...)`
  - Workspace menu includes `Export Citations (BibTeX)` action and file download flow.
- Confirmed collaboration + server-sync roadmap and payload contract:
  - Collaboration design doc:
    - `Docs/Design/WORKSPACE_PLAYGROUND_COLLABORATION_SYNC_PLAN_2026_02_18.md`
  - Versioned contract + runtime guard:
    - `apps/packages/ui/src/store/workspace-sync-contract.ts`
  - Contract coverage:
    - `apps/packages/ui/src/store/__tests__/workspace-sync-contract.test.ts`
- Validation run:
  - `bunx vitest run src/components/Option/WorkspacePlayground/__tests__/workspace-header.utils.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx src/store/__tests__/workspace-sync-contract.test.ts` (all passing).
  - `bunx vitest run src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage2.responsive.test.tsx` (all passing).

## Dependencies

- Version lineage and compare views should align with Category 3 regenerate behavior.
- Collaboration work depends on backend API strategy outside the current localStorage-only model.
