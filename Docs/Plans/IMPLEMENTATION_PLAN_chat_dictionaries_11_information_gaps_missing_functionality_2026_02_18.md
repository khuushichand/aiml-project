# Implementation Plan: Chat Dictionaries - Information Gaps and Missing Functionality

## Scope

Components: dictionaries domain model, option workspace UX architecture, keyboard shortcut layer, reusable templates, long-horizon sharing/composition capabilities
Finding IDs: `11.1` through `11.8`

## Finding Coverage

- Version history and reversibility: `11.1`
- Starter enablement and authoring assistance: `11.2`, `11.3`
- Organization and discoverability improvements: `11.4`
- Efficiency accelerators: `11.5`
- Collaboration and composition roadmap: `11.6`, `11.7`
- Maintainability and component decomposition: `11.8`

## Stage 1: Modularize Dictionaries Workspace Architecture
**Goal**: Split monolithic manager into maintainable units without behavior regressions.
**Success Criteria**:
- `Manager.tsx` responsibilities are decomposed into focused components.
- Proposed split includes `DictionaryList`, `DictionaryForm`, `EntryManager`, `EntryForm`, `ValidationPanel`, `PreviewPanel`, `ImportExport`, `StatsModal`.
- Data hooks and mutation logic are centralized in reusable domain hooks.
- Lazy-loading boundaries are introduced for rarely-used panels/modals.
**Tests**:
- Component-level regression tests for each extracted module.
- Integration tests for end-to-end dictionary CRUD flow parity.
- Bundle analysis check confirming lazy-loaded chunks for optional features.
**Status**: In Progress
**Progress Notes (2026-02-18)**:
- Extracted create/edit dictionary modal form markup into:
  - `apps/packages/ui/src/components/Option/Dictionaries/components/DictionaryFormModal.tsx`
- Added targeted component coverage for reusable dictionary form behavior:
  - `apps/packages/ui/src/components/Option/Dictionaries/__tests__/DictionaryFormModal.test.tsx`
- Extracted import + conflict-resolution modal markup into:
  - `apps/packages/ui/src/components/Option/Dictionaries/components/DictionaryImportModal.tsx`
- Added targeted component coverage for import modal interaction wiring:
  - `apps/packages/ui/src/components/Option/Dictionaries/__tests__/DictionaryImportModal.test.tsx`
- Extracted dictionary list/search/empty-error state surface into:
  - `apps/packages/ui/src/components/Option/Dictionaries/components/DictionaryListSection.tsx`
- Added targeted component coverage for dictionary list section interactions:
  - `apps/packages/ui/src/components/Option/Dictionaries/__tests__/DictionaryListSection.test.tsx`
- Extracted quick-assign modal UI into:
  - `apps/packages/ui/src/components/Option/Dictionaries/components/DictionaryQuickAssignModal.tsx`
- Replaced inline quick-assign modal markup in:
  - `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`
- Extracted dictionary statistics rendering from `Manager.tsx` into:
  - `apps/packages/ui/src/components/Option/Dictionaries/DictionaryStatsModal.tsx`
- Added a lazy-load boundary for statistics UI in manager:
  - `React.lazy` + `Suspense` wrapper in `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`
- Removed statistics-only helper functions from `Manager.tsx` to reduce monolith scope.
- Regression validation completed for stats, accessibility focus, and responsive dictionary actions:
  - `Manager.statsStage1.test.tsx`
  - `Manager.accessibilityStage2.test.tsx`
  - `Manager.accessibilityStage3.test.tsx`
  - `Manager.responsiveStage1.test.tsx`
- Additional regression validation completed for create/edit modal parity:
  - `Manager.chatIntegrationStage3.test.tsx`
  - `Manager.stage1.test.tsx`
- Additional quick-assign parity validation completed with:
  - `Manager.chatIntegrationStage1.test.tsx`
- Additional import workflow parity validation completed with:
  - `Manager.importStage1.test.tsx`
- Extracted row action cell renderer into:
  - `apps/packages/ui/src/components/Option/Dictionaries/components/DictionaryActionsCell.tsx`
- Extracted validation status cell renderer into:
  - `apps/packages/ui/src/components/Option/Dictionaries/components/DictionaryValidationStatusCell.tsx`
- Additional action/status parity validation completed with:
  - `Manager.validationStage1.test.tsx`
- Reliability hardening applied for lazy-loaded stats modal test timing:
  - `Manager.statsStage1.test.tsx`
- Extracted dictionary list table column construction into:
  - `apps/packages/ui/src/components/Option/Dictionaries/components/useDictionaryTableColumns.tsx`
- Moved shared dictionary chat-reference formatting/parsing helpers from manager to:
  - `apps/packages/ui/src/components/Option/Dictionaries/listUtils.ts`
- Added utility coverage for moved chat-reference helpers:
  - `apps/packages/ui/src/components/Option/Dictionaries/__tests__/listUtils.test.ts`
- Regression validation completed across list/import/stats/chat/accessibility flows after column extraction:
  - `listUtils.test.ts`
  - `DictionaryListSection.test.tsx`
  - `DictionaryImportModal.test.tsx`
  - `DictionaryFormModal.test.tsx`
  - `Manager.stage1.test.tsx`
  - `Manager.importStage1.test.tsx`
  - `Manager.statsStage1.test.tsx`
  - `Manager.chatIntegrationStage1.test.tsx`
  - `Manager.chatIntegrationStage2.test.tsx`
  - `Manager.responsiveStage1.test.tsx`
  - `Manager.accessibilityStage2.test.tsx`
  - `Manager.accessibilityStage3.test.tsx`

## Stage 2: Power-User Baseline Features
**Goal**: Improve first-run value and authoring speed for non-expert users.
**Success Criteria**:
- Starter templates are available from create flow (at least three curated templates).
- Regex helper guidance is integrated near regex entry controls.
- Dictionary metadata supports tags/categories with list filtering support.
- Keyboard shortcuts are implemented for create, submit, and validate actions.
**Tests**:
- Component tests for template selection and prefill behavior.
- Integration tests for tag create/filter and persistence.
- Keyboard interaction tests for shortcut registration and scope safety.
**Status**: Not Started

## Stage 3: Versioning, Composition, and Sharing Roadmap
**Goal**: Establish a durable foundation for advanced lifecycle and collaboration.
**Success Criteria**:
- Dictionary version history is stored and viewable with revert capability.
- Composition model supports dictionary includes/inheritance semantics.
- Share/community capability is documented as staged roadmap (or implemented MVP).
- Access controls and trust boundaries are defined for shared artifacts.
**Tests**:
- Backend tests for version snapshot creation and revert correctness.
- Integration tests for include-resolution order and cycle detection.
- Contract tests for export/import behavior with version/composition metadata.
**Status**: Not Started

## Stage 4: Documentation and Adoption Readiness
**Goal**: Ensure advanced capabilities are understandable and operable.
**Success Criteria**:
- User docs explain template usage, tags, shortcuts, and regex helper examples.
- Technical docs specify composition precedence and versioning retention policy.
- Rollout checklist defines feature flags/migration guards for incremental release.
- Success metrics are defined (template adoption, shortcut usage, revert events).
**Tests**:
- Documentation completeness checklist against implemented capabilities.
- Release readiness checklist validation in staging environment.
**Status**: Not Started

## Dependencies

- Versioning and composition may require schema migrations and compatibility adapters.
- Shared/community features should follow existing AuthNZ and RBAC patterns.
