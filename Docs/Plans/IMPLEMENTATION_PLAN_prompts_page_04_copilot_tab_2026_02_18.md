# Implementation Plan: Prompts Page - Copilot Tab

## Scope

Components: Copilot table and editor paths in `apps/packages/ui/src/components/Option/Prompt/index.tsx`, copilot prompt service contracts
Finding IDs: `4.1` through `4.4`

## Finding Coverage

- Placeholder requirement clarity: `4.1`
- Authoring/iteration productivity: `4.2`, `4.3`
- API contract safety for updates: `4.4`

## Stage 1: Copilot Authoring Guardrails and Contract Verification
**Goal**: Make required prompt format explicit and prevent destructive update ambiguity.
**Success Criteria**:
- Copilot editor adds helper text explaining required `{text}` placeholder.
- Placeholder pattern is highlighted or validated inline before submit.
- `setAllCopilotPrompts` behavior is verified against backend contract.
- If endpoint is full-replace, UI migrates to per-item update/upsert path.
**Tests**:
- Form validation tests for required placeholder messaging.
- Integration test confirming edit operation does not remove unrelated prompts.
- Service unit test documenting and enforcing update contract semantics.
**Status**: Complete

## Stage 2: Copilot-to-Custom and Clipboard Actions
**Goal**: Remove manual copy friction for prompt iteration workflows.
**Success Criteria**:
- Copilot row action menu includes `Copy to Custom`.
- Copilot row action menu includes `Copy to clipboard`.
- `Copy to Custom` opens Custom drawer prefilled and marked as new draft.
**Tests**:
- Component tests for new action visibility and disabled/loading states.
- Integration test for `Copy to Custom` data transfer to Custom tab drawer.
- Clipboard action test with success/error feedback behavior.
**Status**: Complete

## Stage 3: Copilot Search and Filter Parity
**Goal**: Bring Copilot list discoverability closer to Custom tab standards.
**Success Criteria**:
- Copilot table header includes text search.
- Optional keyword filter support added where data allows.
- Filtering performance remains responsive for larger copilot sets.
**Tests**:
- Unit tests for copilot filter predicate behavior.
- Component tests for search input state and filtered table output.
**Status**: Complete

## Dependencies

- `Copy to Custom` should reuse Custom tab create/edit schema and validation path.
