# Implementation Plan: Prompts Page - Missing Functionality and Backend Gaps

## Scope

Components: Prompts UI tabs and actions, Studio settings access points, backend prompts collections/export/share integration in `tldw_Server_API/app/api/v1/endpoints/prompts.py`
Finding IDs: `10.1` through `10.6`

## Finding Coverage

- Collections and higher-order organization: `10.1`, `10.6`
- Usage analytics and sharing ergonomics: `10.2`, `10.3`
- Fast execution and settings control from Prompts page: `10.4`, `10.5`

## Stage 1: Collections Foundation and Information Architecture
**Goal**: Introduce structured prompt organization beyond flat keywords.
**Success Criteria**:
- Prompts UI exposes collection creation, listing, and assignment using existing backend endpoints.
- Collection views show prompt counts and support quick membership edits.
- Collections integrate with current keyword filters without breaking existing workflows.
**Tests**:
- Integration tests for create/fetch/update collection flows.
- Component tests for collection assignment and filtering behavior.
**Status**: Complete

## Stage 2: Usage Tracking and Surfacing
**Goal**: Provide evidence of prompt effectiveness and recency of use.
**Success Criteria**:
- Prompt schema includes `usageCount` and `lastUsedAt`.
- "Use in Chat" flow increments usage metrics reliably.
- Table/list views can sort/filter by usage fields where appropriate.
**Tests**:
- Unit tests for usage increment/update behavior.
- Integration tests for chat handoff updating usage metadata.
**Status**: Complete

## Stage 3: Shareable Prompt Links for Synced Prompts
**Goal**: Enable collaborative sharing without file export/import overhead.
**Success Criteria**:
- Synced prompts expose share-link action using server identity.
- Receiver flow resolves shared prompt and supports pull/import.
- Access-control and not-found behaviors are clearly messaged.
**Tests**:
- Integration tests for share-link generation and open flows.
- Negative-path tests for unauthorized/missing prompts.
**Status**: Complete

## Stage 4: Quick Test Path from Custom Tab
**Goal**: Shorten feedback loop for prompt iteration.
**Success Criteria**:
- Custom tab row actions include `Quick test`.
- Synced prompts can open Studio execution context directly.
- Local-only prompts can execute via simplified test modal against chat endpoint.
**Tests**:
- Component tests for quick-test action availability by prompt type/sync state.
- Integration tests for quick-test submission and result rendering.
**Status**: Complete

## Stage 5: Prompt Studio Settings UI Exposure
**Goal**: Make existing Studio settings user-configurable in-context.
**Success Criteria**:
- Studio tab header includes settings entry point.
- Settings panel supports default project selection and auto-sync toggle.
- Setting changes persist and immediately influence sync/project routing behavior.
**Tests**:
- Component tests for settings panel controls and persistence.
- Integration tests for default-project and auto-sync behavior changes.
**Status**: Complete

## Dependencies

- Collections and hierarchy work should sequence ahead of major filter UX redesign.
- Usage/sharing fields require backend schema migrations and API compatibility checks.
