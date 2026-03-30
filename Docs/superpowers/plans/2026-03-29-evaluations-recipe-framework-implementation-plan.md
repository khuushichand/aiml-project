# Evaluations Recipe Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a recipe-first evaluations framework with API parity, a shared WebUI wizard/report flow, V1 embeddings retrieval and summarization recipes, and a small stabilization pass for the currently broken evaluations page contracts.

**Architecture:** Add a parent `recipe run` layer on top of the existing evaluations storage and run infrastructure instead of expanding the already-large generic evaluations endpoints further. Implement new backend recipe modules and recipe APIs, then add a new primary `Recipes` UX in the shared evaluations UI while keeping the old tabs secondary and fixing the four confirmed contract regressions separately so the shared route is not left partially broken.

**Tech Stack:** FastAPI, Pydantic, existing Evaluations DB + Jobs infrastructure, Python pytest, Bandit, React, TypeScript, Zustand store, TanStack Query, Ant Design, Vitest, Playwright

---

## File Structure

- `tldw_Server_API/app/api/v1/schemas/evaluation_recipe_schemas.py`
  Purpose: define recipe manifests, wizard-schema metadata, recipe run requests/responses, dataset validation responses, recommendation slot contracts, review-state metadata, and report models.
- `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_recipes.py`
  Purpose: expose recipe discovery, dataset validation, recipe run creation, status lookup, and report retrieval.
- `tldw_Server_API/app/api/v1/endpoints/evaluations/__init__.py`
  Purpose: register the new recipe router alongside the existing evaluations surfaces.
- `tldw_Server_API/app/core/DB_Management/migrations_v6_evaluation_recipes.py`
  Purpose: add recipe-run, child-run mapping, and immutable dataset snapshot persistence.
- `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py`
  Purpose: apply the new migration and add repository helpers for recipe runs, child runs, reports, and snapshot references.
- `tldw_Server_API/app/core/Evaluations/recipes/__init__.py`
  Purpose: export the recipe registry entry points.
- `tldw_Server_API/app/core/Evaluations/recipes/base.py`
  Purpose: define the base recipe interfaces for manifest, validation, execution, scoring, and report generation.
- `tldw_Server_API/app/core/Evaluations/recipes/registry.py`
  Purpose: register built-in recipes and look them up by id.
- `tldw_Server_API/app/core/Evaluations/recipes/dataset_snapshot.py`
  Purpose: normalize dataset envelope handling and compute immutable snapshot hashes/content refs.
- `tldw_Server_API/app/core/Evaluations/recipes/reporting.py`
  Purpose: implement the common recommendation slot shell, `null + reason_code` fallback behavior, confidence calculation, and report normalization.
- `tldw_Server_API/app/core/Evaluations/recipe_runs_service.py`
  Purpose: orchestrate parent recipe runs, child executions, reuse hashing, review-state rules, and report assembly.
- `tldw_Server_API/app/core/Evaluations/recipe_runs_jobs.py`
  Purpose: enqueue user-facing recipe jobs into the Jobs backend.
- `tldw_Server_API/app/core/Evaluations/recipe_runs_jobs_worker.py`
  Purpose: execute queued recipe jobs and persist child execution/report state.
- `tldw_Server_API/app/core/Evaluations/cli/evals_cli_enhanced.py`
  Purpose: add recipe-oriented CLI commands for recipe listing, dataset validation, run creation, run inspection, and report retrieval.
- `tldw_Server_API/app/core/Evaluations/recipes/embeddings_retrieval.py`
  Purpose: implement the V1 retrieval-only embeddings recipe on top of existing retrieval and embeddings helpers.
- `tldw_Server_API/app/core/Evaluations/recipes/summarization_quality.py`
  Purpose: implement the V1 summarization recipe with fixed source normalization/context policy and rubric scoring.
- `tldw_Server_API/app/core/Evaluations/embeddings_abtest_service.py`
  Purpose: introduce the seam needed to reuse embeddings retrieval machinery without forcing the current Chroma initialization behavior in recipe tests.
- `tldw_Server_API/app/api/v1/schemas/evaluation_schemas_unified.py`
  Purpose: reuse the existing `RunStatus` model in recipe responses and keep status vocabulary aligned.
- `tldw_Server_API/tests/Evaluations/test_recipe_registry.py`
  Purpose: verify recipe registration, manifest shape, and recipe lookup.
- `tldw_Server_API/tests/Evaluations/test_recipe_runs_repository.py`
  Purpose: verify new DB tables, dataset snapshot hashing, report persistence, and child-run mapping.
- `tldw_Server_API/tests/Evaluations/test_recipe_runs_service.py`
  Purpose: verify idempotency/reuse, parent-child orchestration, review-state transitions, and recommendation slot fallbacks.
- `tldw_Server_API/tests/Evaluations/test_recipe_runs_jobs_worker.py`
  Purpose: verify job execution, reuse/resume behavior, and failure propagation.
- `tldw_Server_API/tests/Evaluations/test_recipe_embeddings_retrieval.py`
  Purpose: verify retrieval metrics, unlabeled review sampling, and recipe report generation.
- `tldw_Server_API/tests/Evaluations/test_recipe_summarization_quality.py`
  Purpose: verify source normalization, rubric scoring, grounding gates, and report behavior.
- `tldw_Server_API/tests/Evaluations/integration/test_recipe_runs_api.py`
  Purpose: verify the end-to-end recipe API surface.
- `tldw_Server_API/tests/Evaluations/unit/test_evals_cli_recipe_commands.py`
  Purpose: verify CLI parity for recipe listing, validation, run creation, and report retrieval.
- `apps/packages/ui/src/services/evaluations.ts`
  Purpose: add typed recipe manifest, validate-dataset, create-run, status, and report client helpers; keep existing generic eval helpers intact.
- `apps/packages/ui/src/store/evaluations.tsx`
  Purpose: add state for active recipe, wizard progress, draft config, recipe runs, and report payloads.
- `apps/packages/ui/src/components/Option/Evaluations/tabs/RecipesTab.tsx`
  Purpose: become the primary entry tab for the new recipe-first flow.
- `apps/packages/ui/src/components/Option/Evaluations/components/RecipeRunWizard.tsx`
  Purpose: render the guided wizard for recipe choice, labeled/unlabeled mode, dataset setup, candidate selection, and constraints.
- `apps/packages/ui/src/components/Option/Evaluations/components/RecipeRunReport.tsx`
  Purpose: render recommendation cards, metric breakdowns, confidence messaging, and report exports.
- `apps/packages/ui/src/components/Option/Evaluations/components/RecommendationCard.tsx`
  Purpose: encapsulate per-slot recommendation rendering and `null + reason` fallback presentation.
- `apps/packages/ui/src/components/Option/Evaluations/hooks/useRecipeRuns.ts`
  Purpose: encapsulate recipe query and mutation logic for the new UX.
- `apps/packages/ui/src/components/Option/Evaluations/EvaluationsPage.tsx`
  Purpose: make the recipe flow the primary path while keeping the old tabs secondary.
- `apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RecipesTab.wizard.test.tsx`
  Purpose: verify labeled/unlabeled branching and task-specific step rendering.
- `apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RecipesTab.report.test.tsx`
  Purpose: verify recommendation slots, fallback states, and confidence messaging.
- `apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/WebhooksTab.contract.test.tsx`
  Purpose: lock down the fixed list/delete contract for webhooks.
- `apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/HistoryTab.filters.test.tsx`
  Purpose: verify the corrected history payload/field mapping.
- `apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/DatasetsTab.pagination.test.tsx`
  Purpose: verify dataset viewer behavior after the pagination contract decision.
- `apps/packages/ui/src/components/WorkflowEditor/dynamic-options.ts`
  Purpose: remove or replace the non-existent global runs dependency.
- `apps/tldw-frontend/e2e/utils/page-objects/EvaluationsPage.ts`
  Purpose: add helpers for the recipe tab, wizard progression, and report assertions.
- `apps/tldw-frontend/e2e/workflows/tier-2-features/evaluations.spec.ts`
  Purpose: extend the existing evaluations E2E flow to cover the recipe-first happy path and regressions in the shared route.

## Stages

### Stage 1: Backend Recipe Contracts And Persistence

**Goal:** Land the recipe registry, recipe schemas, and DB persistence required for parent recipe runs and immutable dataset snapshots.

**Success Criteria:** Recipe manifests can be listed, recipe runs can be persisted as parent records, and every run records an immutable dataset snapshot reference or content hash.

**Tests:** `python -m pytest tldw_Server_API/tests/Evaluations/test_recipe_registry.py tldw_Server_API/tests/Evaluations/test_recipe_runs_repository.py -v`

**Status:** Not Started

### Stage 2: Recipe Job Orchestration And APIs

**Goal:** Expose recipe endpoints and wire parent recipe runs to Jobs-based execution and report retrieval.

**Success Criteria:** The API and CLI can list and inspect recipes, validate a dataset before launch, create a recipe run, reuse a prior completed run when config hashes match, expose status with the existing `RunStatus` vocabulary, and return a normalized report shell.

**Tests:** `python -m pytest tldw_Server_API/tests/Evaluations/test_recipe_runs_service.py tldw_Server_API/tests/Evaluations/test_recipe_runs_jobs_worker.py tldw_Server_API/tests/Evaluations/integration/test_recipe_runs_api.py tldw_Server_API/tests/Evaluations/unit/test_evals_cli_recipe_commands.py -v`

**Status:** Not Started

### Stage 3: Built-In V1 Recipes

**Goal:** Implement the V1 retrieval-only embeddings recipe and the V1 summarization-quality recipe.

**Success Criteria:** Both recipes can validate datasets, execute candidate comparisons, enforce recommendation fallback rules, and generate normalized reports.

**Tests:** `python -m pytest tldw_Server_API/tests/Evaluations/test_recipe_embeddings_retrieval.py tldw_Server_API/tests/Evaluations/test_recipe_summarization_quality.py -v`

**Status:** Not Started

### Stage 4: Shared WebUI Wizard And Report Flow

**Goal:** Add a new primary recipe-first flow to the shared evaluations page without making the old tabs the implementation foundation.

**Success Criteria:** A user can choose a recipe, complete the wizard, launch a run, poll status, and read a recommendation-first report from both the web page and extension route.

**Tests:** `bunx vitest run apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RecipesTab.wizard.test.tsx apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RecipesTab.report.test.tsx`

**Status:** Not Started

### Stage 5: Shared Evaluations Surface Stabilization

**Goal:** Fix the concrete frontend/backend contract mismatches already identified in the current webhooks, history, datasets, and dynamic-options surfaces.

**Success Criteria:** The existing shared evaluations page no longer depends on the wrong webhook payload shape, wrong history field names, fake dataset paging, or a non-existent global runs endpoint.

**Tests:** `bunx vitest run apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/WebhooksTab.contract.test.tsx apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/HistoryTab.filters.test.tsx apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/DatasetsTab.pagination.test.tsx`

**Status:** Not Started

### Stage 6: End-To-End And Security Verification

**Goal:** Prove the recipe flow works through the real shared route and confirm the touched backend scope does not introduce new Bandit findings.

**Success Criteria:** The evaluations E2E passes, targeted backend/UI tests pass, and Bandit reports no new issues in the touched backend paths.

**Tests:** `bunx playwright test apps/tldw-frontend/e2e/workflows/tier-2-features/evaluations.spec.ts --reporter=line`, `python -m bandit -r tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_recipes.py tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_datasets.py tldw_Server_API/app/core/Evaluations/recipe_runs_service.py tldw_Server_API/app/core/Evaluations/recipe_runs_jobs.py tldw_Server_API/app/core/Evaluations/recipe_runs_jobs_worker.py tldw_Server_API/app/core/Evaluations/recipes -f json -o /tmp/bandit_evaluations_recipe_framework.json`

**Status:** Not Started

## Task 1: Add Recipe Schemas, Registry, And Persistence

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/evaluation_recipe_schemas.py`
- Create: `tldw_Server_API/app/core/Evaluations/recipes/__init__.py`
- Create: `tldw_Server_API/app/core/Evaluations/recipes/base.py`
- Create: `tldw_Server_API/app/core/Evaluations/recipes/registry.py`
- Create: `tldw_Server_API/app/core/Evaluations/recipes/dataset_snapshot.py`
- Create: `tldw_Server_API/app/core/Evaluations/recipes/reporting.py`
- Create: `tldw_Server_API/app/core/DB_Management/migrations_v6_evaluation_recipes.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/evaluation_schemas_unified.py`
- Test: `tldw_Server_API/tests/Evaluations/test_recipe_registry.py`
- Test: `tldw_Server_API/tests/Evaluations/test_recipe_runs_repository.py`

- [ ] **Step 1: Write the failing registry and repository tests**

Add tests that prove:

1. built-in recipe manifests can be listed by id
2. recipe-run rows persist `dataset_snapshot_ref` or a content hash
3. mandatory recommendation slots can store `null + reason_code`
4. parent recipe runs can map to zero or more child run ids
5. recipe runs persist `recipe_version`, `review_state`, and a typed `confidence` summary

Use concrete assertions such as:

```python
manifest = get_recipe_registry().get("embeddings_retrieval")
assert manifest.id == "embeddings_retrieval"
assert manifest.version == "v1"
assert "best_overall" in manifest.recommendation_slots

run_id = db.create_recipe_run(
    recipe_id="embeddings_retrieval",
    recipe_version="v1",
    dataset_id="ds_demo",
    dataset_version="v1",
    dataset_snapshot_ref="sha256:abc123",
    status="pending",
    config_hash="cfg:demo",
)
row = db.get_recipe_run(run_id)
assert row["dataset_snapshot_ref"] == "sha256:abc123"
```

- [ ] **Step 2: Run the targeted backend tests to verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Evaluations/test_recipe_registry.py \
  tldw_Server_API/tests/Evaluations/test_recipe_runs_repository.py -v
```

Expected: FAIL because the recipe schema, registry, and persistence layer do not exist yet.

- [ ] **Step 3: Implement the minimal schema and persistence layer**

Implement the boring foundation first:

- add typed recipe manifest and report-slot schemas in `evaluation_recipe_schemas.py`
- add a minimal `RecipeDefinition` protocol or base class in `base.py`
- create registry helpers such as:

```python
class RecipeDefinition(Protocol):
    id: str
    version: str
    display_name: str
    recommendation_slots: list[str]

def register_recipe(recipe: RecipeDefinition) -> None:
    ...

def get_recipe(recipe_id: str) -> RecipeDefinition:
    ...
```

- add DB migration + helpers for `evaluation_recipe_runs`, `evaluation_recipe_run_children`, and immutable dataset snapshot references
- include explicit columns or payload fields for:
  - `recipe_version`
  - `review_state`
  - `confidence_json`
- keep status aligned to `RunStatus` from `evaluation_schemas_unified.py`

- [ ] **Step 4: Re-run the targeted backend tests**

Run the pytest command from Step 2.

Expected: PASS for registry listing, recipe-run persistence, and report-slot fallback storage.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/evaluation_recipe_schemas.py \
  tldw_Server_API/app/core/Evaluations/recipes/__init__.py \
  tldw_Server_API/app/core/Evaluations/recipes/base.py \
  tldw_Server_API/app/core/Evaluations/recipes/registry.py \
  tldw_Server_API/app/core/Evaluations/recipes/dataset_snapshot.py \
  tldw_Server_API/app/core/Evaluations/recipes/reporting.py \
  tldw_Server_API/app/core/DB_Management/migrations_v6_evaluation_recipes.py \
  tldw_Server_API/app/core/DB_Management/Evaluations_DB.py \
  tldw_Server_API/app/api/v1/schemas/evaluation_schemas_unified.py \
  tldw_Server_API/tests/Evaluations/test_recipe_registry.py \
  tldw_Server_API/tests/Evaluations/test_recipe_runs_repository.py
git commit -m "feat: add evaluation recipe run persistence"
```

## Task 2: Add Recipe APIs And Jobs-Based Orchestration

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_recipes.py`
- Create: `tldw_Server_API/app/core/Evaluations/recipe_runs_service.py`
- Create: `tldw_Server_API/app/core/Evaluations/recipe_runs_jobs.py`
- Create: `tldw_Server_API/app/core/Evaluations/recipe_runs_jobs_worker.py`
- Modify: `tldw_Server_API/app/core/Evaluations/cli/evals_cli_enhanced.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/evaluations/__init__.py`
- Test: `tldw_Server_API/tests/Evaluations/test_recipe_runs_service.py`
- Test: `tldw_Server_API/tests/Evaluations/test_recipe_runs_jobs_worker.py`
- Test: `tldw_Server_API/tests/Evaluations/integration/test_recipe_runs_api.py`
- Test: `tldw_Server_API/tests/Evaluations/unit/test_evals_cli_recipe_commands.py`

- [ ] **Step 1: Write the failing service, worker, and API tests**

Add tests that prove:

1. `POST /api/v1/evaluations/recipes/{recipe_id}/runs` creates a parent recipe run
2. `GET /api/v1/evaluations/recipes/{recipe_id}` returns a single manifest
3. `POST /api/v1/evaluations/recipes/{recipe_id}/validate-dataset` returns validation errors before launch
4. `GET /api/v1/evaluations/recipe-runs/{run_id}` returns run metadata without requiring the full report
5. identical requests reuse a completed run unless `force_rerun=True`
6. status responses use `pending`, `running`, `completed`, `failed`, `cancelled`
7. reports always return `best_overall`, `best_cheap`, and `best_local`, even if some are `null`
8. the CLI supports `recipes list`, `recipes validate-dataset`, `recipes run`, and `recipes report`

Example assertion:

```python
resp = client.post(
    "/api/v1/evaluations/recipes/embeddings_retrieval/runs",
    json={"dataset_id": "ds1", "candidate_models": ["m1", "m2"]},
    headers=auth_headers,
)
assert resp.status_code == 202
assert resp.json()["status"] == "pending"
```

- [ ] **Step 2: Run the targeted backend tests to verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Evaluations/test_recipe_runs_service.py \
  tldw_Server_API/tests/Evaluations/test_recipe_runs_jobs_worker.py \
  tldw_Server_API/tests/Evaluations/integration/test_recipe_runs_api.py \
  tldw_Server_API/tests/Evaluations/unit/test_evals_cli_recipe_commands.py -v
```

Expected: FAIL because the service, worker, and router do not exist yet.

- [ ] **Step 3: Implement the minimal orchestration layer**

Build the parent-run orchestration before any recipe-specific logic:

- `recipe_runs_service.py` should:
  - resolve the recipe from the registry
  - resolve immutable model/judge identifiers for the reuse hash
  - include these hash inputs explicitly:
    - `recipe_id`
    - `recipe_version`
    - dataset snapshot ref or content hash
    - resolved model ids
    - versioned judge config
    - prompts
    - weights
    - comparison mode
    - source normalization/context policy
    - execution policy
  - create or reuse the parent recipe run
  - attach child run ids as they are created
- the recipe run request schema should include both an explicit rerun override and the persisted per-run config chosen by the user:

```python
class RecipeRunRequest(BaseModel):
    dataset_id: str
    candidate_models: list[str]
    data_mode: Literal["labeled", "unlabeled"]
    run_config: dict[str, Any]
    force_rerun: bool = False
```

- `run_config` should capture the recipe-specific choices needed for reproducibility, including:
  - selected goal or task
  - weights
  - judge settings
  - thresholds
  - sample size
  - comparison mode
  - source normalization/context policy
  - execution policy

- `recipe_runs_jobs.py` should enqueue Jobs-visible work
- `recipe_runs_jobs_worker.py` should execute one recipe run and persist a normalized report
- `evaluations_recipes.py` should expose:

```python
@router.get("/recipes")
async def list_recipes(): ...

@router.get("/recipes/{recipe_id}")
async def get_recipe_manifest(...): ...

@router.post("/recipes/{recipe_id}/validate-dataset")
async def validate_recipe_dataset(...): ...

@router.post("/recipes/{recipe_id}/runs")
async def create_recipe_run(...): ...

@router.get("/recipe-runs/{run_id}")
async def get_recipe_run(...): ...

@router.get("/recipe-runs/{run_id}/report")
async def get_recipe_report(...): ...
```

- extend `evals_cli_enhanced.py` with concrete recipe commands:

```python
@cli.group("recipes")
def recipes_group():
    ...

@recipes_group.command("list")
def list_recipes(): ...

@recipes_group.command("run")
def run_recipe(...): ...
```

- [ ] **Step 4: Re-run the targeted backend tests**

Run the pytest command from Step 2.

Expected: PASS for parent-run creation, status alignment, reuse, and report retrieval.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_recipes.py \
  tldw_Server_API/app/core/Evaluations/recipe_runs_service.py \
  tldw_Server_API/app/core/Evaluations/recipe_runs_jobs.py \
  tldw_Server_API/app/core/Evaluations/recipe_runs_jobs_worker.py \
  tldw_Server_API/app/core/Evaluations/cli/evals_cli_enhanced.py \
  tldw_Server_API/app/api/v1/endpoints/evaluations/__init__.py \
  tldw_Server_API/tests/Evaluations/test_recipe_runs_service.py \
  tldw_Server_API/tests/Evaluations/test_recipe_runs_jobs_worker.py \
  tldw_Server_API/tests/Evaluations/integration/test_recipe_runs_api.py \
  tldw_Server_API/tests/Evaluations/unit/test_evals_cli_recipe_commands.py
git commit -m "feat: add evaluation recipe run APIs"
```

## Task 3: Implement The V1 Embeddings Retrieval Recipe

**Files:**
- Create: `tldw_Server_API/app/core/Evaluations/recipes/embeddings_retrieval.py`
- Modify: `tldw_Server_API/app/core/Evaluations/embeddings_abtest_service.py`
- Modify: `tldw_Server_API/app/core/Evaluations/metrics_retrieval.py`
- Test: `tldw_Server_API/tests/Evaluations/test_recipe_embeddings_retrieval.py`
- Test: `tldw_Server_API/tests/Evaluations/test_embeddings_abtest_retrieval.py`

- [ ] **Step 1: Write the failing embeddings recipe tests**

Add tests that prove:

1. labeled retrieval datasets validate `query_id` and expected ids
2. unlabeled retrieval runs reserve a human review sample
3. the recipe supports both `embedding-only comparison` and `retrieval-stack comparison`
4. the recipe can emit `best_overall`, `best_cheap`, and `best_local`
5. the recipe does not instantiate the brittle Chroma path in tests without an injectable manager factory

Use a focused test like:

```python
report = await recipe.build_report(results=[
    {"model": "m1", "recall_at_k": 0.9, "cost_usd": 0.12, "is_local": False},
    {"model": "m2", "recall_at_k": 0.82, "cost_usd": 0.00, "is_local": True},
])
assert report["best_overall"]["model"] == "m1"
assert report["best_local"]["model"] == "m2"
```

- [ ] **Step 2: Run the targeted embeddings tests to verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Evaluations/test_recipe_embeddings_retrieval.py \
  tldw_Server_API/tests/Evaluations/test_embeddings_abtest_retrieval.py -v
```

Expected: FAIL because the recipe file does not exist and the current embeddings service still has the Chroma test seam problem.

- [ ] **Step 3: Implement the retrieval recipe and the test seam**

Implement only the retrieval-focused V1 recipe:

- validate a retrieval dataset payload with query ids and expected ids
- reuse existing retrieval metrics where possible
- support both:
  - `embedding_only`
  - `retrieval_stack`
- add an injectable collection-manager seam in `embeddings_abtest_service.py`, for example:

```python
def get_collection_manager(*, user_id: str, embedding_config: dict[str, Any]):
    return ChromaDBManager(user_id=user_id, user_embedding_config=embedding_config)
```

- make the recipe compute:
  - `Recall@k`
  - `MRR`
  - `nDCG`
  - latency
  - cost
- reserve a review sample automatically in unlabeled mode
- record confidence inputs needed by the common report shell:
  - sample count
  - score spread or bootstrap variance
  - winner margin
  - judge agreement when available

- [ ] **Step 4: Re-run the targeted embeddings tests**

Run the pytest command from Step 2.

Expected: PASS for retrieval validation, report generation, and the focused retrieval test seam.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Evaluations/recipes/embeddings_retrieval.py \
  tldw_Server_API/app/core/Evaluations/embeddings_abtest_service.py \
  tldw_Server_API/app/core/Evaluations/metrics_retrieval.py \
  tldw_Server_API/tests/Evaluations/test_recipe_embeddings_retrieval.py \
  tldw_Server_API/tests/Evaluations/test_embeddings_abtest_retrieval.py
git commit -m "feat: add embeddings retrieval recipe"
```

## Task 4: Implement The V1 Summarization Quality Recipe

**Files:**
- Create: `tldw_Server_API/app/core/Evaluations/recipes/summarization_quality.py`
- Modify: `tldw_Server_API/app/core/Evaluations/response_quality_evaluator.py`
- Modify: `tldw_Server_API/app/core/Evaluations/ms_g_eval.py`
- Test: `tldw_Server_API/tests/Evaluations/test_recipe_summarization_quality.py`

- [ ] **Step 1: Write the failing summarization recipe tests**

Add tests that prove:

1. a run-wide source normalization policy is frozen before candidate execution
2. candidates that fail grounding cannot win overall
3. unlabeled runs reserve a review sample and can remain `review_required`
4. labeled runs can use references without requiring manual review by default
5. confidence fields are emitted in the normalized report payload

Use assertions like:

```python
policy = recipe.build_context_policy(documents=[doc], max_source_tokens=8000)
assert policy["mode"] in {"single_pass", "map_reduce"}

report = recipe.finalize_report([...])
assert report["best_overall"] is None
assert report["best_overall_reason_code"] == "no_candidate_passed_grounding"
```

- [ ] **Step 2: Run the targeted summarization tests to verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Evaluations/test_recipe_summarization_quality.py -v
```

Expected: FAIL because the recipe and its normalization policy do not exist yet.

- [ ] **Step 3: Implement the summarization recipe**

Implement the minimal reliable V1 path:

- freeze source normalization and context policy per run
- keep candidate prompt structure identical within the run
- score the weighted rubric:
  - grounding
  - coverage
  - concise usefulness
- support references or preference pairs as supporting evidence in labeled mode
- mark candidates ineligible when grounding gates fail
- emit the common confidence object needed by the shared report shell:
  - `sample_count`
  - `variance` or `bootstrap_spread`
  - `winner_margin`
  - `judge_agreement`
  - `warning_codes`

Use a focused helper shape such as:

```python
class SummarizationContextPolicy(TypedDict):
    mode: Literal["single_pass", "map_reduce"]
    max_source_tokens: int
    chunk_size: int | None
    overlap: int | None
```

- [ ] **Step 4: Re-run the targeted summarization tests**

Run the pytest command from Step 2.

Expected: PASS for policy freezing, grounding gates, and report slot fallbacks.

- [ ] **Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Evaluations/recipes/summarization_quality.py \
  tldw_Server_API/app/core/Evaluations/response_quality_evaluator.py \
  tldw_Server_API/app/core/Evaluations/ms_g_eval.py \
  tldw_Server_API/tests/Evaluations/test_recipe_summarization_quality.py
git commit -m "feat: add summarization quality recipe"
```

## Task 5: Add The Shared Recipe Wizard And Report UX

**Files:**
- Create: `apps/packages/ui/src/components/Option/Evaluations/tabs/RecipesTab.tsx`
- Create: `apps/packages/ui/src/components/Option/Evaluations/components/RecipeRunWizard.tsx`
- Create: `apps/packages/ui/src/components/Option/Evaluations/components/RecipeRunReport.tsx`
- Create: `apps/packages/ui/src/components/Option/Evaluations/components/RecommendationCard.tsx`
- Create: `apps/packages/ui/src/components/Option/Evaluations/hooks/useRecipeRuns.ts`
- Modify: `apps/packages/ui/src/services/evaluations.ts`
- Modify: `apps/packages/ui/src/store/evaluations.tsx`
- Modify: `apps/packages/ui/src/components/Option/Evaluations/EvaluationsPage.tsx`
- Modify: `apps/packages/ui/src/components/Option/Evaluations/components/index.ts`
- Modify: `apps/packages/ui/src/components/Option/Evaluations/tabs/index.ts`
- Test: `apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RecipesTab.wizard.test.tsx`
- Test: `apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RecipesTab.report.test.tsx`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/EvaluationsPage.ts`
- Modify: `apps/tldw-frontend/e2e/workflows/tier-2-features/evaluations.spec.ts`

- [ ] **Step 1: Write the failing UI tests**

Add tests that prove:

1. `Recipes` is the primary tab
2. selecting `Embeddings` vs `Summarization` changes the wizard steps
3. labeled vs unlabeled changes the review messaging
4. `null + reason` recommendation slots render as explanatory empty states instead of fake winners
5. confidence warnings render for low-sample or close-call reports
6. `Simple mode` hides advanced controls while `Advanced` exposes weights, judge settings, sample sizes, and thresholds from the recipe manifest
7. the wizard includes an explicit dataset step for selecting an existing dataset or creating one before launch

Example test:

```tsx
render(<RecipesTab />)
await user.click(screen.getByRole("button", { name: /Embeddings/i }))
expect(screen.getByText(/What are embeddings for/i)).toBeInTheDocument()
```

- [ ] **Step 2: Run the targeted UI tests to verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RecipesTab.wizard.test.tsx \
  apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RecipesTab.report.test.tsx
```

Expected: FAIL because the new tab, hook, and components do not exist yet.

- [ ] **Step 3: Implement the wizard/report flow**

Build the new primary UX without entangling it with the old generic tabs:

- add typed recipe helpers to `services/evaluations.ts`
- add recipe draft/report state to `store/evaluations.tsx`
- implement `RecipesTab.tsx` as the new first tab
- keep `RecipeRunWizard.tsx` focused on step logic and `RecipeRunReport.tsx` focused on output
- use `RecommendationCard.tsx` to render both real winners and `null + reason` fallbacks consistently
- give the wizard an explicit dataset step before launch so the user can choose between:
  - an existing `dataset_id`
  - new dataset creation or upload
- make the wizard manifest-driven enough to support:
  - `Simple mode` defaults
  - recipe-declared `Advanced` controls
  - per-recipe weight/judge/sample-size/threshold fields without hardcoding them in each component
- add a shared `confidence` rendering contract to the store/report types so the UI can show:
  - low sample warnings
  - close-call warnings
  - judge-agreement warnings

- [ ] **Step 4: Re-run the targeted UI tests**

Run the vitest command from Step 2.

Expected: PASS for wizard branching and recommendation report rendering.

- [ ] **Step 5: Extend the evaluations E2E flow and run it**

Update the existing shared-route E2E to cover:

1. landing on the recipe tab
2. choosing a recipe
3. submitting a simple run
4. seeing recommendation cards

Run:

```bash
bunx playwright test apps/tldw-frontend/e2e/workflows/tier-2-features/evaluations.spec.ts --reporter=line
```

Expected: PASS for the recipe-first happy path.

- [ ] **Step 6: Commit**

```bash
git add apps/packages/ui/src/services/evaluations.ts \
  apps/packages/ui/src/store/evaluations.tsx \
  apps/packages/ui/src/components/Option/Evaluations/tabs/RecipesTab.tsx \
  apps/packages/ui/src/components/Option/Evaluations/components/RecipeRunWizard.tsx \
  apps/packages/ui/src/components/Option/Evaluations/components/RecipeRunReport.tsx \
  apps/packages/ui/src/components/Option/Evaluations/components/RecommendationCard.tsx \
  apps/packages/ui/src/components/Option/Evaluations/hooks/useRecipeRuns.ts \
  apps/packages/ui/src/components/Option/Evaluations/EvaluationsPage.tsx \
  apps/packages/ui/src/components/Option/Evaluations/components/index.ts \
  apps/packages/ui/src/components/Option/Evaluations/tabs/index.ts \
  apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RecipesTab.wizard.test.tsx \
  apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RecipesTab.report.test.tsx \
  apps/tldw-frontend/e2e/utils/page-objects/EvaluationsPage.ts \
  apps/tldw-frontend/e2e/workflows/tier-2-features/evaluations.spec.ts
git commit -m "feat: add evaluations recipe wizard"
```

## Task 6: Stabilize The Existing Shared Evaluations Surface And Run Final Verification

**Files:**
- Modify: `apps/packages/ui/src/services/evaluations.ts`
- Modify: `apps/packages/ui/src/components/Option/Evaluations/hooks/useWebhooks.ts`
- Modify: `apps/packages/ui/src/components/Option/Evaluations/tabs/WebhooksTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/Evaluations/hooks/useHistory.ts`
- Modify: `apps/packages/ui/src/components/Option/Evaluations/tabs/HistoryTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/Evaluations/hooks/useDatasets.ts`
- Modify: `apps/packages/ui/src/components/Option/Evaluations/tabs/DatasetsTab.tsx`
- Modify: `apps/packages/ui/src/components/WorkflowEditor/dynamic-options.ts`
- Modify: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_datasets.py`
- Test: `apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/WebhooksTab.contract.test.tsx`
- Test: `apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/HistoryTab.filters.test.tsx`
- Test: `apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/DatasetsTab.pagination.test.tsx`

- [ ] **Step 1: Write the failing regression tests**

Add tests that prove:

1. webhooks list can read the backend list payload and delete by URL
2. history sends `evaluation_type` and reads `evaluation_type` / `evaluation_id`
3. dataset viewer either pages correctly from the backend or removes fake paging behavior
4. dynamic options no longer call the non-existent global runs endpoint

Example assertions:

```tsx
expect(deleteWebhook).toHaveBeenCalledWith("https://example.com/hook")
expect(getHistory).toHaveBeenCalledWith({ evaluation_type: "rag" })
```

- [ ] **Step 2: Run the targeted regression tests to verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/WebhooksTab.contract.test.tsx \
  apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/HistoryTab.filters.test.tsx \
  apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/DatasetsTab.pagination.test.tsx
```

Expected: FAIL because the existing UI contracts are still wrong.

- [ ] **Step 3: Implement the targeted fixes**

Make the smallest fixes needed to stabilize the old shared surface:

- align webhook list/delete to backend `webhook_id`, `status`, and URL-based delete
- align history request/response fields to `evaluation_type` and `evaluation_id`
- choose one dataset-viewer behavior and make it honest:
  - either add real backend paging to `evaluations_datasets.py`
  - or remove fake client paging and show the limited preview honestly
- remove or replace the nonexistent global-runs call in `dynamic-options.ts`

- [ ] **Step 4: Re-run targeted tests, backend tests, and security checks**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/WebhooksTab.contract.test.tsx \
  apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/HistoryTab.filters.test.tsx \
  apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/DatasetsTab.pagination.test.tsx

source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Evaluations/test_recipe_registry.py \
  tldw_Server_API/tests/Evaluations/test_recipe_runs_repository.py \
  tldw_Server_API/tests/Evaluations/test_recipe_runs_service.py \
  tldw_Server_API/tests/Evaluations/test_recipe_runs_jobs_worker.py \
  tldw_Server_API/tests/Evaluations/test_recipe_embeddings_retrieval.py \
  tldw_Server_API/tests/Evaluations/test_recipe_summarization_quality.py \
  tldw_Server_API/tests/Evaluations/integration/test_recipe_runs_api.py -v

python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_datasets.py \
  tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_recipes.py \
  tldw_Server_API/app/core/Evaluations/recipe_runs_service.py \
  tldw_Server_API/app/core/Evaluations/recipe_runs_jobs.py \
  tldw_Server_API/app/core/Evaluations/recipe_runs_jobs_worker.py \
  tldw_Server_API/app/core/Evaluations/recipes \
  -f json -o /tmp/bandit_evaluations_recipe_framework.json
```

Expected:

- Vitest PASS
- targeted pytest PASS
- Bandit finishes with no new findings in touched scope

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/services/evaluations.ts \
  apps/packages/ui/src/components/Option/Evaluations/hooks/useWebhooks.ts \
  apps/packages/ui/src/components/Option/Evaluations/tabs/WebhooksTab.tsx \
  apps/packages/ui/src/components/Option/Evaluations/hooks/useHistory.ts \
  apps/packages/ui/src/components/Option/Evaluations/tabs/HistoryTab.tsx \
  apps/packages/ui/src/components/Option/Evaluations/hooks/useDatasets.ts \
  apps/packages/ui/src/components/Option/Evaluations/tabs/DatasetsTab.tsx \
  apps/packages/ui/src/components/WorkflowEditor/dynamic-options.ts \
  tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_datasets.py \
  apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/WebhooksTab.contract.test.tsx \
  apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/HistoryTab.filters.test.tsx \
  apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/DatasetsTab.pagination.test.tsx
git commit -m "fix: stabilize shared evaluations page contracts"
```
