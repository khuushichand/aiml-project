# Synthetic Eval Dataset Generation And Review Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared synthetic eval dataset generation and review workflow that can generate corpus-grounded draft samples, preserve provenance and review state, expose a real review queue, and feed only approved samples into recipe-driven recommendations.

**Architecture:** Add a dedicated persistence layer for synthetic draft samples and review actions instead of hiding this state in ad hoc metadata. Build the shared backend service first, including provenance-aware weighting metadata and stratified generation hooks, then expose it through explicit API endpoints and a shared evaluations review surface that recipe flows can link into. Keep recipe integration narrow: retrieval tuning and answer quality consume approved samples through a generic dataset-promotion path rather than embedding the whole review workflow inside each recipe. Wire the new API router through the existing `evaluations_unified.py` subrouter composition instead of adding a parallel top-level router path in `main.py`.

**Tech Stack:** FastAPI, Pydantic, Evaluations DB + migrations, recipe-run services, existing media/notes backends, pytest, Vitest, Playwright, Bandit.

---

## File Map

**Create**
- `tldw_Server_API/app/api/v1/schemas/synthetic_eval_schemas.py`
  Shared request/response models for synthetic draft generation, review actions, filtered queue listing, and promoted datasets.
- `tldw_Server_API/app/core/Evaluations/synthetic_eval_repository.py`
  Persistence helpers for draft samples, provenance, review actions, and promotion state.
- `tldw_Server_API/app/core/Evaluations/synthetic_eval_service.py`
  Orchestrates source precedence, stratified draft generation, review transitions, and dataset promotion.
- `tldw_Server_API/app/core/Evaluations/synthetic_eval_generation.py`
  Encapsulates corpus inspection, gap analysis, and tuple-to-sample generation logic.
- `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_synthetic.py`
  REST endpoints for generation jobs, review queue listing, review actions, and recipe-filtered queue views.
- `tldw_Server_API/app/core/DB_Management/migrations_v7_synthetic_eval_workflow.py`
  Adds the SQLite schema for draft samples, provenance, review history, and promotion records.
- `tldw_Server_API/tests/Evaluations/test_synthetic_eval_service.py`
  Unit tests for precedence, provenance, weighting metadata, and promotion rules.
- `tldw_Server_API/tests/Evaluations/integration/test_synthetic_eval_api.py`
  API tests for generation, review, filtering, and promotion.
- `apps/packages/ui/src/components/Option/Evaluations/tabs/SyntheticReviewTab.tsx`
  Shared review queue surface for synthetic eval drafts.
- `apps/packages/ui/src/components/Option/Evaluations/hooks/useSyntheticEval.ts`
  React Query hooks for draft generation, queue listing, review actions, and promotion.
- `apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/SyntheticReviewTab.test.tsx`
  UI tests for queue filtering, review actions, and promotion.
- `apps/tldw-frontend/e2e/smoke/evaluations-synthetic-review.spec.ts`
  Browser smoke coverage for the shared review workflow.

**Modify**
- `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py`
  Add repository-facing methods and migration wiring.
- `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py`
  Include the new synthetic workflow router alongside the existing evaluations subrouters.
- `tldw_Server_API/app/core/Evaluations/recipe_runs_service.py`
  Add helper methods that consume only approved promoted samples.
- `tldw_Server_API/app/core/Evaluations/recipes/rag_retrieval_tuning.py`
  Accept promoted synthetic datasets as valid labeled/unlabeled inputs without special casing raw drafts.
- `tldw_Server_API/app/core/Evaluations/recipes/rag_answer_quality.py`
  Accept promoted synthetic answer-quality datasets and expected behavior labels.
- `tldw_Server_API/tests/Evaluations/test_recipe_runs_service.py`
  Cover the rule that only approved/promoted synthetic samples influence recipe runs.
- `apps/packages/ui/src/services/evaluations.ts`
  Add service functions/types for the synthetic workflow endpoints.
- `apps/packages/ui/src/store/evaluations.tsx`
  Extend the shared tab/store contract so the review workflow can be selected and deep-linked cleanly.
- `apps/packages/ui/src/components/Option/Evaluations/EvaluationsPage.tsx`
  Add a dedicated shared review sub-surface or tab entry point.
- `apps/packages/ui/src/components/Option/Evaluations/tabs/RecipesTab.tsx`
  Add filtered links into the shared review workflow instead of embedding review state locally.
- `apps/packages/ui/src/assets/locale/en/evaluations.json`
  Add review-tab labels and user-facing workflow copy that is now shared across recipes.
- `apps/tldw-frontend/e2e/utils/page-objects/EvaluationsPage.ts`
  Add page-object helpers for the review queue.

**Reference**
- `Docs/superpowers/specs/2026-03-29-synthetic-eval-dataset-generation-and-review-workflow-design.md`
  Approved design for the shared workflow.
- `Docs/superpowers/specs/2026-03-29-rag-answer-quality-recipe-design.md`
  Downstream consumer contract for answer-quality drafts.
- `Docs/superpowers/specs/2026-03-29-rag-retrieval-tuning-recipe-design.md`
  Retrieval consumer contract for synthetic query drafts.
- `tldw_Server_API/app/core/Evaluations/recipes/dataset_snapshot.py`
  Existing dataset snapshot/content-hash helpers to reuse for promoted datasets.
- `apps/packages/ui/src/components/Option/Evaluations/tabs/DatasetsTab.tsx`
  Existing dataset viewing patterns worth reusing for promoted sample previews.

## Scope Guardrails

- This workflow is shared infrastructure plus a shared review UI, not a recipe-local add-on.
- Synthetic drafts must never affect recipe recommendations until approved and promoted.
- Source precedence is fixed in V1: `real -> seed examples -> corpus-grounded synthetic`.
- Generation must stay stratified across both `media_db` and `notes`, plus query intent and difficulty.
- The workflow must support both retrieval-style and answer-quality-style draft shapes, but it does not need to support every future recipe in V1.

### Task 1: Add Persistence, Schemas, And Migration

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/synthetic_eval_schemas.py`
- Create: `tldw_Server_API/app/core/DB_Management/migrations_v7_synthetic_eval_workflow.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py`
- Create: `tldw_Server_API/app/core/Evaluations/synthetic_eval_repository.py`
- Create: `tldw_Server_API/tests/Evaluations/test_synthetic_eval_service.py`

- [x] **Step 1: Write the failing repository/schema tests**

```python
def test_repository_persists_draft_samples_with_provenance_and_review_state() -> None:
    ...
    assert row["provenance"] == "synthetic_from_corpus"
    assert row["review_state"] == "draft"
```

```python
def test_repository_records_review_action_history() -> None:
    ...
    assert history[-1]["action"] == "edit_and_approve"
```

- [x] **Step 2: Run the targeted tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Evaluations/test_synthetic_eval_service.py -v`

Expected: FAIL because the schemas/repository do not exist yet.

- [x] **Step 3: Implement the migration and repository**

Add dedicated tables for:
- draft sample records
- review actions/history
- promotion records

Keep the row shape generic enough for both retrieval and answer-quality draft payloads.

- [x] **Step 4: Run the targeted tests again**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Evaluations/test_synthetic_eval_service.py -v`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/synthetic_eval_schemas.py \
        tldw_Server_API/app/core/DB_Management/migrations_v7_synthetic_eval_workflow.py \
        tldw_Server_API/app/core/DB_Management/Evaluations_DB.py \
        tldw_Server_API/app/core/Evaluations/synthetic_eval_repository.py \
        tldw_Server_API/tests/Evaluations/test_synthetic_eval_service.py
git commit -m "feat: add synthetic eval workflow persistence"
```

### Task 2: Implement Stratified Draft Generation And Source Precedence

**Files:**
- Create: `tldw_Server_API/app/core/Evaluations/synthetic_eval_generation.py`
- Create: `tldw_Server_API/app/core/Evaluations/synthetic_eval_service.py`
- Modify: `tldw_Server_API/tests/Evaluations/test_synthetic_eval_service.py`

- [x] **Step 1: Write the failing service tests**

```python
def test_generation_prefers_real_examples_before_synthetic_fill() -> None:
    ...
    assert result.source_breakdown["real"] > 0
    assert result.source_breakdown["synthetic_from_corpus"] > 0
```

```python
def test_generation_is_stratified_across_media_notes_intent_and_difficulty() -> None:
    ...
    assert "media_db" in result.coverage["sources"]
    assert "notes" in result.coverage["sources"]
```

- [x] **Step 2: Run the targeted tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Evaluations/test_synthetic_eval_service.py -k "generation or precedence" -v`

Expected: FAIL because the service is not implemented yet.

- [x] **Step 3: Implement the shared generation service**

Use a small helper pipeline:
- resolve corpus scope
- ingest real examples and seed examples
- detect missing coverage
- generate structured tuples
- convert tuples into draft samples
- persist provenance and draft review state

Do not make external LLM calls directly from tests; mock the generation boundary cleanly.

- [x] **Step 4: Run the targeted tests again**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Evaluations/test_synthetic_eval_service.py -k "generation or precedence" -v`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Evaluations/synthetic_eval_generation.py \
        tldw_Server_API/app/core/Evaluations/synthetic_eval_service.py \
        tldw_Server_API/tests/Evaluations/test_synthetic_eval_service.py
git commit -m "feat: generate synthetic eval drafts with stratification"
```

### Task 3: Add Review Queue APIs And Promotion Rules

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_synthetic.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py`
- Create: `tldw_Server_API/tests/Evaluations/integration/test_synthetic_eval_api.py`
- Modify: `tldw_Server_API/app/core/Evaluations/recipe_runs_service.py`
- Modify: `tldw_Server_API/tests/Evaluations/test_recipe_runs_service.py`

- [x] **Step 1: Write the failing API and integration tests**

```python
def test_synthetic_queue_filters_by_recipe_kind(client) -> None:
    ...
    assert all(item["recipe_kind"] == "rag_answer_quality" for item in response.json()["data"])
```

```python
def test_recipe_runs_ignore_unapproved_synthetic_drafts() -> None:
    ...
    assert validation["sample_count"] == 0
```

- [x] **Step 2: Run the targeted tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Evaluations/integration/test_synthetic_eval_api.py tldw_Server_API/tests/Evaluations/test_recipe_runs_service.py -k "synthetic or approved" -v`

Expected: FAIL because the endpoints and promotion rules do not exist yet.

- [x] **Step 3: Implement the endpoints and gating rules**

Expose endpoints for:
- creating a generation job / draft batch
- listing queue items with filters
- applying review actions
- promoting approved items into a dataset snapshot

Recipe services should only consume promoted datasets or approved promoted samples, never raw drafts.

- [x] **Step 4: Run the targeted tests again**

Run the same command from Step 2.

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_synthetic.py \
        tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py \
        tldw_Server_API/tests/Evaluations/integration/test_synthetic_eval_api.py \
        tldw_Server_API/app/core/Evaluations/recipe_runs_service.py \
        tldw_Server_API/tests/Evaluations/test_recipe_runs_service.py
git commit -m "feat: add synthetic eval review and promotion APIs"
```

### Task 4: Build The Shared Review UI Surface

**Files:**
- Create: `apps/packages/ui/src/components/Option/Evaluations/tabs/SyntheticReviewTab.tsx`
- Create: `apps/packages/ui/src/components/Option/Evaluations/hooks/useSyntheticEval.ts`
- Create: `apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/SyntheticReviewTab.test.tsx`
- Modify: `apps/packages/ui/src/services/evaluations.ts`
- Modify: `apps/packages/ui/src/store/evaluations.tsx`
- Modify: `apps/packages/ui/src/components/Option/Evaluations/EvaluationsPage.tsx`
- Modify: `apps/packages/ui/src/components/Option/Evaluations/tabs/RecipesTab.tsx`
- Modify: `apps/packages/ui/src/assets/locale/en/evaluations.json`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/EvaluationsPage.ts`
- Create: `apps/tldw-frontend/e2e/smoke/evaluations-synthetic-review.spec.ts`

- [x] **Step 1: Write the failing UI and browser tests**

Cover:
- filtered queue views for retrieval versus answer-quality drafts
- approve / reject / edit-and-approve flows
- promotion into a dataset
- recipe entry points that deep-link into filtered review views

- [x] **Step 2: Run the targeted tests to verify they fail**

Run:
- `bunx vitest run apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/SyntheticReviewTab.test.tsx --maxWorkers=1 --no-file-parallelism`
- `npx playwright test apps/tldw-frontend/e2e/smoke/evaluations-synthetic-review.spec.ts --reporter=line`

Expected: FAIL because the shared review surface does not exist yet.

- [x] **Step 3: Implement the shared review tab**

Keep it separate from `RecipesTab`. Recipes should link into filtered views instead of embedding the queue inline.

- [x] **Step 4: Run the targeted UI/browser tests again**

Run the same commands from Step 2.

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Evaluations/tabs/SyntheticReviewTab.tsx \
        apps/packages/ui/src/components/Option/Evaluations/hooks/useSyntheticEval.ts \
        apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/SyntheticReviewTab.test.tsx \
        apps/packages/ui/src/services/evaluations.ts \
        apps/packages/ui/src/store/evaluations.tsx \
        apps/packages/ui/src/components/Option/Evaluations/EvaluationsPage.tsx \
        apps/packages/ui/src/components/Option/Evaluations/tabs/RecipesTab.tsx \
        apps/packages/ui/src/assets/locale/en/evaluations.json \
        apps/tldw-frontend/e2e/utils/page-objects/EvaluationsPage.ts \
        apps/tldw-frontend/e2e/smoke/evaluations-synthetic-review.spec.ts
git commit -m "feat: add synthetic eval review workflow UI"
```

### Task 5: Final Verification

**Files:**
- No new files; verification only.

- [x] **Step 1: Run the full touched backend suite**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Evaluations/test_synthetic_eval_service.py tldw_Server_API/tests/Evaluations/integration/test_synthetic_eval_api.py tldw_Server_API/tests/Evaluations/test_recipe_runs_service.py -v`

Expected: PASS.

- [x] **Step 2: Run the focused frontend suite**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/SyntheticReviewTab.test.tsx --maxWorkers=1 --no-file-parallelism`

Expected: PASS.

- [x] **Step 3: Run the browser smoke**

Run: `npx playwright test apps/tldw-frontend/e2e/smoke/evaluations-synthetic-review.spec.ts --reporter=line`

Expected: PASS.

- [x] **Step 4: Run Bandit on the touched backend scope**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/schemas/synthetic_eval_schemas.py tldw_Server_API/app/core/Evaluations/synthetic_eval_repository.py tldw_Server_API/app/core/Evaluations/synthetic_eval_service.py tldw_Server_API/app/core/Evaluations/synthetic_eval_generation.py tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_synthetic.py tldw_Server_API/app/core/DB_Management/Evaluations_DB.py -f json -o /tmp/bandit_synthetic_eval_workflow.json`

Expected: no new findings in touched scope.

- [ ] **Step 5: Commit any verification-driven fixes**

```bash
git add <touched_files>
git commit -m "fix: polish synthetic eval workflow verification"
```

## Implementation Notes

- Keep review state, provenance, and promotion state separate. They are related but not interchangeable.
- Use the shared workflow to produce ordinary promoted datasets for recipes rather than teaching each recipe about draft review internals.
- When in doubt, bias toward explicit review-state transitions and auditable history over implicit magic.
