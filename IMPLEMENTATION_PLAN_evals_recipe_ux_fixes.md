## Stage 1: Auth And Recipe Load States
**Goal**: Fix the API key placeholder mismatch and make recipe manifest failures visible instead of falling back to a false empty state.
**Success Criteria**: Demo/local keys accepted consistently; recipe fetch errors render actionable UI; targeted unit tests cover both behaviors.
**Tests**: `bunx vitest run apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RecipesTab.launch.test.tsx apps/packages/ui/src/components/Option/Evaluations/__tests__/EvaluationsPage.recipe-tab.test.tsx`
**Status**: Complete

## Stage 2: Recipe E2E Coverage And User-Facing Errors
**Goal**: Replace the stale legacy evaluations E2E with recipe-first assertions and map raw recipe enqueue failures to human-readable recovery guidance.
**Success Criteria**: Tier-2 evaluations E2E covers the recipe tab path; UI no longer shows raw backend failure tokens for recipe launch failures.
**Tests**: `npx playwright test e2e/workflows/tier-2-features/evaluations.spec.ts --project=tier-2 --reporter=line`
**Status**: Complete

## Stage 3: Runtime Readiness And Validation Semantics
**Goal**: Surface recipe worker readiness explicitly and distinguish dataset validation from execution readiness.
**Success Criteria**: Backend exposes recipe-run readiness; UI disables or explains unavailable run actions; validation panel separates dataset validity from runtime prerequisites.
**Tests**: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Evaluations/test_recipe_runs_jobs_worker.py tldw_Server_API/tests/Evaluations/integration/test_recipe_runs_api.py -v` and targeted vitest coverage for the recipe tab.
**Status**: Complete

## Stage 4: Notifications Friction And Empty Saved-Dataset UX
**Goal**: Reduce notifications auth/CORS noise on the web client and make the saved-dataset path actionable when no datasets exist.
**Success Criteria**: Notifications requests use the correct request path in web mode; saved-dataset affordance explains what to do next instead of presenting a dead control.
**Tests**: Targeted vitest for recipe tab plus any existing notifications/web-mode tests that cover the adjusted path.
**Status**: Complete

## Stage 5: Guided Recipe Launch And Happy-Path Smoke Coverage
**Goal**: Replace the JSON-first recipe launcher with a beginner-friendlier guided surface and add one real smoke test for the recipe happy path.
**Success Criteria**: Recipe launch UI supports guided model/dataset entry with advanced JSON kept behind disclosure; smoke coverage exercises a successful validate-and-run recipe flow on a fixture stack.
**Tests**: targeted vitest for the new recipe controls and `npx playwright test` for the new recipe smoke spec.
**Status**: Complete
