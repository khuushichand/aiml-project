# Knowledge QA and Workspace Live-Backend E2E Design

**Date:** 2026-03-16

**Goal:** Replace permissive or selector-drifted e2e coverage for `/knowledge` and strengthen `/workspace-playground` around real backend behavior, so the suites prove feature contracts instead of mostly validating that the page does not crash.

## Context

The current targeted Playwright run against the live frontend and backend showed a split result:

- `/workspace-playground` smoke, parity, and current live-backend coverage passed.
- `/knowledge` failed 6 tests, clustered around settings, history, and one staged-loading assertion.

Code inspection and runtime evidence showed two classes of problems:

1. **False-positive assertions**
   - Several `knowledge-qa.spec.ts` cases use blanket `try/catch`, permissive fallbacks, or tautologies such as `expect(answer.length > 0 || noResults || true).toBeTruthy()`.
   - These tests can pass without proving the feature under test exists or works.

2. **Selector and contract drift**
   - The `KnowledgeQAPage` object targets broad fallback selectors that do not align tightly with the current Knowledge QA layout.
   - Some assertions assume direct text rendering for content that is intentionally split into structured markup, such as inline citation buttons.
   - Settings and history tests currently assume a specific path to those controls instead of matching the actual simple-layout and research-layout affordances.

## Chosen Approach

Use the live backend as the default source of truth for both routes, while making each test assert one explicit, user-visible contract.

This keeps the suites close to real usage and avoids reintroducing “passes because we mocked the world” behavior. Very small deterministic stubs remain acceptable only where the UI contract cannot be forced reliably from a live server in a single run, but they are not the primary strategy.

## `/knowledge` Design

The Knowledge QA suite will be reorganized around live-backend feature contracts:

- Initial search:
  Verify that a real search reaches the backend, renders either a grounded answer or a no-results recovery path, and surfaces the evidence panel when results exist.
- Citation and evidence behavior:
  Assert that at least one citation control exists when the answer includes citations, and that the evidence panel exposes a corresponding source item.
- Follow-up thread behavior:
  Assert that a follow-up creates another turn in the same conversation context rather than merely checking for an optional input.
- History behavior:
  Assert that history affordances open or expand using the current layout’s real controls and that a prior query can be restored.
- Settings behavior:
  Assert that settings can be opened from the current layout, that preset/expert changes are reflected in visible UI state, and that at least one changed setting affects the subsequent request payload or persisted state.

The current staged-loading regression remains useful, but its assertion will be updated to match the real rendered answer contract rather than raw flat text matching.

## `/workspace-playground` Design

The existing workspace suites already cover basic route health, parity structure, and one real-backend smoke path. They do not yet prove enough of the user-facing feature set.

The live-backend additions will focus on high-value feature contracts:

- Source selection affects downstream behavior:
  Selected sources should be reflected in the chat or studio context surfaces.
- Grounded chat path:
  A chat turn should execute with selected sources present and produce an assistant response without backend bootstrap regressions.
- Studio source-scoped generation:
  One studio output path should prove that generation works against the selected workspace sources in a real backend context.
- Workspace search/retrieval surface:
  One global-search interaction should prove workspace state is searchable and actionable, not just that the modal opens.

The current smoke/parity tests remain valuable for fast structure checks and should stay.

## Risks and Constraints

- Live-backend data variability means some assertions must target stable UI contracts rather than exact semantic content.
- Knowledge QA layout mode can change which controls are visible; tests need to interact with the current mode instead of assuming one fixed layout.
- If a truly important live-backend flow remains flaky, that instability should be reported as a coverage gap rather than hidden behind permissive assertions.

## Verification

Targeted verification will use:

- `bunx playwright test e2e/workflows/knowledge-qa.spec.ts e2e/workflows/workspace-playground.spec.ts e2e/workflows/workspace-playground.parity.spec.ts e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line`
- `source .venv/bin/activate && python -m bandit -r apps/tldw-frontend/e2e -f json -o /tmp/bandit_knowledge_workspace_e2e.json`

Success means:

- Knowledge QA no longer relies on tautological or catch-all assertions for the audited feature areas.
- Workspace playground covers at least one real-backend chat flow and one real-backend generation/search flow beyond pane smoke.
- The targeted suites pass against the running local frontend and backend.
