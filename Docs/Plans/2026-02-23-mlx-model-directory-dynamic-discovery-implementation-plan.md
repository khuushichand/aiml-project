# MLX Model Directory Dynamic Discovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add admin-safe MLX model directory discovery with dynamic on-access scanning and load-time model selection via server-resolved `model_id`, while preserving existing `model_path` behavior.

**Architecture:** Extend the existing MLX provider control plane with a dedicated `/mlx/models` endpoint and `model_id` load support. Keep discovery/validation logic in provider-layer utilities for deterministic testing and reuse, then update the Admin MLX UI to present selectable/non-selectable discovered models with explicit reasons and manual fallback.

**Tech Stack:** FastAPI, Pydantic, Python pathlib/os utilities, pytest/TestClient, React + AntD, Vitest + Testing Library, TypeScript API client.

---

Using @test-driven-development and @verification-before-completion.

## Stage 1: Discovery Core
**Goal**: Build deterministic MLX directory scanner with manifest validation and TTL caching behavior.
**Success Criteria**: Scanner returns stable, sorted model candidates with eligibility reasons and safe path metadata.
**Tests**: `tldw_Server_API/tests/LLM_Calls/test_mlx_model_discovery.py`
**Status**: Not Started

### Task 1: Add failing unit tests for model discovery rules

**Files:**
- Create: `tldw_Server_API/tests/LLM_Calls/test_mlx_model_discovery.py`
- Reference: `tldw_Server_API/tests/LLM_Calls/test_mlx_provider.py`

**Step 1: Write the failing test**

```python
def test_discovery_marks_valid_manifest_selectable(tmp_path):
    model_dir = tmp_path / "mlx_models" / "qwen-mini"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}")
    (model_dir / "tokenizer.json").write_text("{}")
    (model_dir / "weights.safetensors").write_text("x")

    result = discover_mlx_models(tmp_path / "mlx_models")
    assert result.available_models[0]["selectable"] is True
    assert result.available_models[0]["reasons"] == []
```

Add tests for:
- recursive discovery in nested directories
- non-selectable reasons for missing tokenizer/weights/config
- symlinked directories/files ignored
- name-ascending sort

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Calls/test_mlx_model_discovery.py -v
```

Expected: FAIL because discovery API does not exist yet.

**Step 3: Commit (tests only)**

```bash
git add tldw_Server_API/tests/LLM_Calls/test_mlx_model_discovery.py
git commit -m "test: add failing MLX model discovery manifest coverage"
```

### Task 2: Implement discovery utility with eligibility reasons

**Files:**
- Create: `tldw_Server_API/app/core/LLM_Calls/providers/mlx_model_discovery.py`
- Modify: `tldw_Server_API/app/core/LLM_Calls/providers/mlx_provider.py`
- Test: `tldw_Server_API/tests/LLM_Calls/test_mlx_model_discovery.py`

**Step 1: Write minimal implementation**

```python
def _validate_manifest(path: Path) -> tuple[bool, list[str]]:
    reasons = []
    if not (path / "config.json").is_file():
        reasons.append("Missing config.json")
    if not ((path / "tokenizer.json").is_file() or (path / "tokenizer.model").is_file()):
        reasons.append("Missing tokenizer.json or tokenizer.model")
    has_weights = any(path.glob("*.safetensors")) or any(path.glob("*.bin"))
    if not has_weights:
        reasons.append("Missing *.safetensors or *.bin weights")
    return (len(reasons) == 0, reasons)
```

Implement:
- recursive walk
- symlink ignore
- stable id/relative path normalization
- sorted output
- response object with `warnings` and model metadata

**Step 2: Run tests to verify pass**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Calls/test_mlx_model_discovery.py -v
```

Expected: PASS.

**Step 3: Commit**

```bash
git add tldw_Server_API/app/core/LLM_Calls/providers/mlx_model_discovery.py tldw_Server_API/app/core/LLM_Calls/providers/mlx_provider.py tldw_Server_API/tests/LLM_Calls/test_mlx_model_discovery.py
git commit -m "feat+test: add MLX model directory discovery with manifest validation"
```

## Stage 2: API Contract
**Goal**: Expose discovery endpoint and `model_id` load path safely.
**Success Criteria**: `/mlx/models` returns 200 with warnings when needed; `/mlx/load` accepts `model_id` and blocks traversal.
**Tests**: `tldw_Server_API/tests/LLM_Local/test_mlx_management_api.py`, `tldw_Server_API/tests/AuthNZ_Unit/test_mlx_permissions_claims.py`
**Status**: Not Started

### Task 3: Add failing API contract tests for `/mlx/models` and `model_id` load

**Files:**
- Modify: `tldw_Server_API/tests/LLM_Local/test_mlx_management_api.py`
- Modify: `tldw_Server_API/tests/AuthNZ_Unit/test_mlx_permissions_claims.py`
- Reference: `tldw_Server_API/app/api/v1/endpoints/mlx.py`

**Step 1: Write the failing tests**

```python
def test_mlx_models_returns_200_with_warning_when_model_dir_unset(...):
    response = client.get("/api/v1/llm/providers/mlx/models")
    assert response.status_code == 200
    body = response.json()
    assert body["available_models"] == []
    assert body["warnings"]
```

```python
def test_mlx_load_with_model_id_resolves_and_calls_registry(...):
    response = client.post("/api/v1/llm/providers/mlx/load", json={"model_id": "family/model-a"})
    assert response.status_code == 200
    assert registry.last_model_path.endswith("family/model-a")
```

```python
def test_mlx_load_rejects_traversal_model_id(...):
    response = client.post("/api/v1/llm/providers/mlx/load", json={"model_id": "../escape"})
    assert response.status_code == 400
```

Also add RBAC coverage for `GET /api/v1/llm/providers/mlx/models`.

**Step 2: Run tests to verify fail**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Local/test_mlx_management_api.py tldw_Server_API/tests/AuthNZ_Unit/test_mlx_permissions_claims.py -v
```

Expected: FAIL on missing endpoint/fields.

**Step 3: Commit (tests only)**

```bash
git add tldw_Server_API/tests/LLM_Local/test_mlx_management_api.py tldw_Server_API/tests/AuthNZ_Unit/test_mlx_permissions_claims.py
git commit -m "test: add failing MLX models endpoint and model_id load contract tests"
```

### Task 4: Implement schema and endpoint changes

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/mlx.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mlx.py`
- Modify: `tldw_Server_API/app/core/LLM_Calls/providers/mlx_provider.py`
- Test: `tldw_Server_API/tests/LLM_Local/test_mlx_management_api.py`

**Step 1: Implement minimal contract support**

Add `model_id` to `MLXLoadRequest`:

```python
class MLXLoadRequest(BaseModel):
    model_id: str | None = Field(default=None, description="Relative model id under MLX_MODEL_DIR")
    model_path: str | None = Field(default=None, description="Local path or repo id for the MLX model")
```

Add endpoint:

```python
@router.get("/llm/providers/mlx/models", dependencies=[Depends(check_rate_limit), Depends(require_roles("admin"))])
async def list_mlx_models(...):
    return _normalize_mlx_response(registry.list_models(refresh=refresh))
```

Update `/load` resolution:
- use `model_id` first (safe resolve under `MLX_MODEL_DIR`)
- fallback to existing `model_path` behavior
- map invalid ids to `HTTP 400`

**Step 2: Run tests to verify pass**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Local/test_mlx_management_api.py tldw_Server_API/tests/AuthNZ_Unit/test_mlx_permissions_claims.py -v
```

Expected: PASS.

**Step 3: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/mlx.py tldw_Server_API/app/api/v1/endpoints/mlx.py tldw_Server_API/app/core/LLM_Calls/providers/mlx_provider.py tldw_Server_API/tests/LLM_Local/test_mlx_management_api.py tldw_Server_API/tests/AuthNZ_Unit/test_mlx_permissions_claims.py
git commit -m "feat+test: add MLX models listing endpoint and model_id load support"
```

## Stage 3: Admin UI Integration
**Goal**: Make model selection explicit and safe in Admin MLX UI with clear selectability reasons.
**Success Criteria**: Users can pick discovered models, understand disabled items, refresh list, and still use manual fallback.
**Tests**: `apps/packages/ui/src/components/Option/Admin/__tests__/MlxAdminPage.test.tsx`
**Status**: Not Started

### Task 5: Add failing frontend tests for discovered-model flow

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Admin/__tests__/MlxAdminPage.test.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`

**Step 1: Write failing tests**

```tsx
it("loads discovered model using model_id", async () => {
  apiMock.getMlxModels.mockResolvedValue({
    backend: "mlx",
    model_dir_configured: true,
    warnings: [],
    available_models: [{ id: "family/model-a", name: "model-a", selectable: true, reasons: [] }]
  })
  render(<MlxAdminPage />)
  // select model-a and click Load
  expect(apiMock.loadMlxModel).toHaveBeenCalledWith(expect.objectContaining({ model_id: "family/model-a" }))
})
```

Add tests for:
- disabled non-selectable entry shows reason
- model directory/warning copy visible when unavailable
- manual path fallback still posts `model_path`

**Step 2: Run tests to verify fail**

Run:
```bash
cd apps/packages/ui && bunx vitest run src/components/Option/Admin/__tests__/MlxAdminPage.test.tsx
```

Expected: FAIL (missing client method/UI wiring).

**Step 3: Commit (tests only)**

```bash
git add apps/packages/ui/src/components/Option/Admin/__tests__/MlxAdminPage.test.tsx
git commit -m "test: add failing MLX admin discovered-model selection coverage"
```

### Task 6: Implement API client and Admin UI updates

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Modify: `apps/packages/ui/src/components/Option/Admin/MlxAdminPage.tsx`
- Modify: `apps/packages/ui/src/utils/build-mlx-load-request.ts`
- Test: `apps/packages/ui/src/components/Option/Admin/__tests__/MlxAdminPage.test.tsx`

**Step 1: Add client types/methods and UI behavior**

Add client types and endpoint:

```ts
export interface MlxDiscoveredModel {
  id: string
  name: string
  selectable: boolean
  reasons: string[]
  relative_path?: string
  modified_at?: number | null
  size_bytes?: number | null
}

async getMlxModels(refresh = false): Promise<MlxModelListResponse> { ... }
```

UI updates:
- render discovered model select + refresh
- disable non-selectable entries with reason text
- keep manual input section
- send `model_id` when discovered model selected; fallback `model_path` for manual mode

**Step 2: Run tests to verify pass**

Run:
```bash
cd apps/packages/ui && bunx vitest run src/components/Option/Admin/__tests__/MlxAdminPage.test.tsx
```

Expected: PASS.

**Step 3: Commit**

```bash
git add apps/packages/ui/src/services/tldw/TldwApiClient.ts apps/packages/ui/src/components/Option/Admin/MlxAdminPage.tsx apps/packages/ui/src/utils/build-mlx-load-request.ts apps/packages/ui/src/components/Option/Admin/__tests__/MlxAdminPage.test.tsx
git commit -m "feat+test: wire MLX discovered model selection into admin UI"
```

## Stage 4: Docs and Final Verification
**Goal**: Document new configuration and endpoint, then validate touched scope including security checks.
**Success Criteria**: Docs updated; targeted backend/frontend tests and Bandit pass.
**Tests**: targeted pytest/vitest + Bandit on changed backend paths.
**Status**: Not Started

### Task 7: Update docs and run verification suite

**Files:**
- Modify: `Docs/User_Guides/Server/Authentication_Setup.md`
- Modify: `Docs/Published/User_Guides/Server/Authentication_Setup.md`
- Optional: `Docs/API-related/Providers_API_Documentation.md` (if MLX admin endpoints documented there)

**Step 1: Document new behavior**
- Add `MLX_MODEL_DIR` config guidance.
- Add `GET /api/v1/llm/providers/mlx/models` usage example.
- Clarify discovered-model selection vs manual path fallback.

**Step 2: Run verification commands**

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Calls/test_mlx_model_discovery.py tldw_Server_API/tests/LLM_Local/test_mlx_management_api.py tldw_Server_API/tests/AuthNZ_Unit/test_mlx_permissions_claims.py -v
```

```bash
cd apps/packages/ui && bunx vitest run src/components/Option/Admin/__tests__/MlxAdminPage.test.tsx
```

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/mlx.py tldw_Server_API/app/core/LLM_Calls/providers/mlx_provider.py tldw_Server_API/app/core/LLM_Calls/providers/mlx_model_discovery.py -f json -o /tmp/bandit_mlx_model_directory_dynamic_discovery.json
```

Expected:
- all targeted tests PASS
- Bandit shows no new actionable findings in changed scope

**Step 3: Commit**

```bash
git add Docs/User_Guides/Server/Authentication_Setup.md Docs/Published/User_Guides/Server/Authentication_Setup.md
git commit -m "docs: add MLX model directory discovery and model_id loading guidance"
```

### Task 8: Final branch verification snapshot

**Files:**
- No code changes required (verification-only task)

**Step 1: Run final status/log checks**

```bash
git status --short
git log --oneline -n 10
```

Expected:
- only intended files changed
- commit history reflects TDD sequence

**Step 2: Prepare handoff summary**
- List API changes (`/mlx/models`, `model_id` support).
- List UI behavior changes.
- List test evidence and Bandit report path.

**Step 3: Commit (if summary artifacts were added)**

```bash
# Only if artifacts/files were created during handoff
git add <artifact-paths>
git commit -m "chore: finalize MLX model directory discovery verification"
```
