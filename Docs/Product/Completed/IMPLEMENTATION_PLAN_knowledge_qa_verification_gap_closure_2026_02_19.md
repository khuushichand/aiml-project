# Implementation Plan: Knowledge QA Verification Gap Closure

## Stage 1: CI Accessibility Gate Wiring
**Goal**: Ensure Stage 4 axe checks for Knowledge QA are executed in CI.
**Success Criteria**:
- Frontend UX workflow runs Stage 4 high-risk axe routes before later smoke stages.
- Frontend package scripts include a dedicated Stage 4 command.
**Tests**:
- Workflow dry-check via file validation and command references.
**Status**: Complete

## Stage 2: Source Rendering Scalability Benchmark Coverage
**Goal**: Add explicit test evidence for 10/25/50 source render paths.
**Success Criteria**:
- A KnowledgeQA test exercises render paths for 10, 25, and 50 results.
- Test verifies threshold pagination strategy and records bounded render timings.
**Tests**:
- Vitest test(s) in `KnowledgeQA/__tests__` for large result rendering.
**Status**: Complete

## Stage 3: Progressive Long-Running Search E2E Evidence
**Goal**: Add deterministic E2E verification of progressive in-flight feedback for long searches.
**Success Criteria**:
- KnowledgeQA workflow test forces delayed search response and verifies stage transitions.
- Test validates completion content after delayed response.
**Tests**:
- Playwright workflow test under `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`.
**Status**: Complete

## Stage 4: Validation and Evidence Pass
**Goal**: Confirm added tests/workflow changes execute and document outcomes.
**Success Criteria**:
- Targeted Vitest and Playwright specs run (or clearly report blockers).
- Plan statuses updated to reflect completion state.
**Tests**:
- `bunx vitest run src/components/Option/KnowledgeQA/__tests__/...` (targeted)
- `bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep ...` (targeted if environment permits)
**Status**: Complete

### Verification Evidence
- CI gate wiring:
  - Added frontend script `e2e:smoke:stage4` in `apps/tldw-frontend/package.json`.
  - Added workflow step `Run Stage 4 accessibility axe gate` in `.github/workflows/frontend-ux-gates.yml`.
- Source rendering benchmark/perf coverage:
  - Added `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/SourceList.performance.test.tsx`.
  - Verified 10/25/50 result render-path benchmarks and threshold pagination behavior.
- Progressive long-running workflow evidence:
  - Added delayed-progress E2E test in `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`.
  - Test command (targeted):  
    `TLDW_SERVER_URL=http://127.0.0.1:8000 TLDW_API_KEY=smoke-ci-key-12345 bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "shows progressive loading stages for delayed long-running searches" --reporter=line`
  - Result: `1 passed`.
- Targeted unit/integration validation command:
  - `bunx vitest run src/components/Option/KnowledgeQA/__tests__/SourceList.performance.test.tsx src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx`
  - Result: `3 passed` files, `11 passed` tests.
