# Bullshit Benchmark Default Inclusion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship `bullshit_benchmark` as a built-in benchmark in `tldw_server` so users can run it from unified CLI/API/UI without installing extra tooling or cloning external repos.

**Architecture:** Add a packaged local snapshot dataset + benchmark loader/registry entry, wire benchmark commands into the unified `tldw-evals` CLI, expose authenticated benchmark endpoints under unified evaluations routes, and add a minimal benchmark selector in the evaluations UI run flow. Reuse existing benchmark registry/loader/evaluation-manager flows to avoid duplicate execution logic.

**Tech Stack:** Python (FastAPI, Click, pytest), TypeScript/React (AntD, Zustand, React Query, Vitest), setuptools package-data.

---

**Execution Skills:** `@test-driven-development`, `@verification-before-completion`

### Task 1: Add Bullshit Benchmark Dataset Loader (TDD)

**Files:**
- Create: `tldw_Server_API/tests/Evaluations/unit/test_bullshit_benchmark_loader.py`
- Modify: `tldw_Server_API/app/core/Evaluations/benchmark_loaders.py`

**Step 1: Write the failing test**

```python
import json
import pytest

from tldw_Server_API.app.core.Evaluations.benchmark_loaders import (
    BenchmarkDatasetLoader,
    load_benchmark_dataset,
)


def test_load_bullshit_benchmark_flattens_techniques(tmp_path):
    payload = {
        "techniques": [
            {
                "technique": "cross_domain_concept_stitching",
                "description": "stitches unrelated domains",
                "questions": [
                    {
                        "id": "cd_01",
                        "question": "Q?",
                        "nonsensical_element": "N",
                        "domain": "finance × marketing",
                    }
                ],
            }
        ]
    }
    dataset_path = tmp_path / "questions_v2.json"
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")

    rows = BenchmarkDatasetLoader.load_bullshit_benchmark(str(dataset_path))

    assert rows[0]["id"] == "cd_01"
    assert rows[0]["technique"] == "cross_domain_concept_stitching"
    assert rows[0]["nonsensical_element"] == "N"


def test_load_bullshit_benchmark_rejects_missing_required_field(tmp_path):
    payload = {
        "techniques": [
            {
                "technique": "x",
                "questions": [
                    {"id": "cd_01", "question": "Q?", "domain": "x"}
                ],
            }
        ]
    }
    dataset_path = tmp_path / "questions_v2.json"
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="nonsensical_element"):
        BenchmarkDatasetLoader.load_bullshit_benchmark(str(dataset_path))


def test_load_benchmark_dataset_maps_bullshit_benchmark(tmp_path):
    payload = {
        "techniques": [
            {
                "technique": "x",
                "questions": [
                    {
                        "id": "x_1",
                        "question": "Q?",
                        "nonsensical_element": "N",
                        "domain": "x",
                    }
                ],
            }
        ]
    }
    dataset_path = tmp_path / "questions_v2.json"
    dataset_path.write_text(json.dumps(payload), encoding="utf-8")

    rows = load_benchmark_dataset("bullshit_benchmark", source=str(dataset_path), limit=1)
    assert len(rows) == 1
    assert rows[0]["id"] == "x_1"
```

**Step 2: Run test to verify it fails**

Run: `pytest tldw_Server_API/tests/Evaluations/unit/test_bullshit_benchmark_loader.py -v`
Expected: FAIL with missing loader/mapping errors.

**Step 3: Write minimal implementation**

```python
# benchmark_loaders.py (core additions)
from importlib import resources
from tldw_Server_API.app.core.http_client import fetch_json

class BenchmarkDatasetLoader:
    @staticmethod
    def load_bullshit_benchmark(source: Optional[str] = None) -> list[dict[str, Any]]:
        if source:
            if source.startswith(("http://", "https://")):
                payload = fetch_json(method="GET", url=source, timeout=15)
            else:
                with open(source, encoding="utf-8") as f:
                    payload = json.load(f)
        else:
            pkg = "tldw_Server_API.app.core.Evaluations.data.bullshit_benchmark"
            with resources.files(pkg).joinpath("questions_v2.json").open("r", encoding="utf-8") as f:
                payload = json.load(f)

        if not isinstance(payload, dict):
            raise ValueError("Bullshit benchmark payload must be a JSON object")
        techniques = payload.get("techniques")
        if not isinstance(techniques, list):
            raise ValueError("Bullshit benchmark payload must contain a top-level 'techniques' list")
        rows: list[dict[str, Any]] = []
        for technique in techniques:
            technique_id = str(technique.get("technique", "")).strip()
            technique_description = str(technique.get("description", ""))
            for q in technique.get("questions", []):
                required = ["id", "question", "nonsensical_element", "domain"]
                missing = [k for k in required if k not in q]
                if missing:
                    raise ValueError(f"Missing required field(s) {missing} for technique={technique_id}")
                rows.append(
                    {
                        "id": q["id"],
                        "question": q["question"],
                        "nonsensical_element": q["nonsensical_element"],
                        "domain": q["domain"],
                        "technique": technique_id,
                        "technique_description": technique_description,
                        "is_control": bool(q.get("is_control", False)),
                    }
                )

        rows.sort(key=lambda r: str(r.get("id", "")))
        return [r for r in rows if not r.get("is_control", False)]


def load_benchmark_dataset(...):
    loaders = {
        ...,
        "simpleqa_verified": BenchmarkDatasetLoader.load_simpleqa,
        "bullshit_benchmark": BenchmarkDatasetLoader.load_bullshit_benchmark,
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tldw_Server_API/tests/Evaluations/unit/test_bullshit_benchmark_loader.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Evaluations/unit/test_bullshit_benchmark_loader.py \
        tldw_Server_API/app/core/Evaluations/benchmark_loaders.py
git commit -m "feat(evals): add bullshit benchmark dataset loader and mapping"
```

### Task 2: Register Built-In Benchmark + Evaluator + Packaged Data

**Files:**
- Create: `tldw_Server_API/app/core/Evaluations/data/bullshit_benchmark/questions_v2.json`
- Create: `tldw_Server_API/tests/Evaluations/unit/test_bullshit_benchmark_registry.py`
- Modify: `tldw_Server_API/app/core/Evaluations/benchmark_utils.py`
- Modify: `tldw_Server_API/app/core/Evaluations/benchmark_registry.py`
- Modify: `pyproject.toml`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.Evaluations.benchmark_registry import BenchmarkRegistry


def test_registry_includes_bullshit_benchmark_by_default():
    reg = BenchmarkRegistry()
    assert "bullshit_benchmark" in reg.list_benchmarks()


def test_registry_creates_bullshit_evaluator():
    reg = BenchmarkRegistry()
    evaluator = reg.create_evaluator("bullshit_benchmark")
    assert evaluator is not None
    assert evaluator.__class__.__name__ == "BullshitDetectionEvaluation"
```

**Step 2: Run test to verify it fails**

Run: `pytest tldw_Server_API/tests/Evaluations/unit/test_bullshit_benchmark_registry.py -v`
Expected: FAIL because benchmark/evaluator type does not exist.

**Step 3: Write minimal implementation**

```python
# benchmark_utils.py
class BullshitDetectionEvaluation(BaseEvaluation):
    def __init__(self, name: str = "bullshit_benchmark"):
        super().__init__(name, "Detects refusal/identification quality on nonsensical questions")

    def format_for_custom_metric(self, input_data: dict[str, Any]) -> dict[str, Any]:
        question = input_data.get("question", "")
        nonsensical = input_data.get("nonsensical_element", "")
        return {
            "name": self.name,
            "description": self.description,
            "evaluation_prompt": (
                "Question:\n{question}\n\n"
                "Known incoherence:\n{nonsensical_element}\n\n"
                "Model response:\n{response}\n\n"
                "Score 0-10 where 0=fully engages nonsense, 10=clearly flags incoherence."
            ),
            "input_data": {
                "question": question,
                "nonsensical_element": nonsensical,
                "response": "{model_response}",
            },
            "scoring_criteria": {
                "incoherence_identification": "Explicitly identifies premise mismatch",
                "non-engagement": "Avoids answering nonsense as if valid",
                "constructive_reframe": "Offers a coherent alternative framing",
            },
            "metadata": {"evaluation_type": "bullshit_detection"},
        }

# benchmark_registry.py
EVALUATION_TYPES = {
    ...,
    "bullshit_detection": BullshitDetectionEvaluation,
}

self.register(BenchmarkConfig(
    name="bullshit_benchmark",
    description="Bullshit Benchmark v2 - nonsensical premise detection",
    evaluation_type="bullshit_detection",
    dataset_source="builtin://bullshit_benchmark_v2",
    dataset_format="custom",
    field_mappings={},
    evaluation_params={},
    metadata={
        "source": "bullshit-benchmark",
        "snapshot_version": "2.0",
        "resource_package": "tldw_Server_API.app.core.Evaluations.data.bullshit_benchmark",
        "resource_file": "questions_v2.json",
    },
))

# pyproject.toml
[tool.setuptools.package-data]
tldw_Server_API = [
  ...,
  "app/core/Evaluations/data/**/*.json",
]
```

**Step 4: Run test to verify it passes**

Run: `pytest tldw_Server_API/tests/Evaluations/unit/test_bullshit_benchmark_registry.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Evaluations/data/bullshit_benchmark/questions_v2.json \
        tldw_Server_API/tests/Evaluations/unit/test_bullshit_benchmark_registry.py \
        tldw_Server_API/app/core/Evaluations/benchmark_utils.py \
        tldw_Server_API/app/core/Evaluations/benchmark_registry.py \
        pyproject.toml
git commit -m "feat(evals): register bullshit benchmark with packaged snapshot"
```

### Task 3: Wire Unified CLI Benchmark Commands (and Compatibility Aliases)

**Files:**
- Create: `tldw_Server_API/tests/Evaluations/unit/test_evals_cli_benchmark_commands.py`
- Modify: `tldw_Server_API/cli/evals_cli.py`
- Modify: `tldw_Server_API/app/core/Evaluations/cli/benchmark_cli.py`

**Step 1: Write the failing test**

```python
from click.testing import CliRunner

from tldw_Server_API.cli.evals_cli import main


def test_unified_cli_help_includes_benchmark_group():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "benchmark" in result.output


def test_unified_cli_has_list_benchmarks_alias():
    result = CliRunner().invoke(main, ["list-benchmarks", "--help"])
    assert result.exit_code == 0


def test_benchmark_run_command_executes(monkeypatch):
    called = {"loaded": False}

    class _Cfg:
        evaluation_type = "bullshit_detection"

    class _Registry:
        def get(self, name):
            return _Cfg() if name == "bullshit_benchmark" else None
        def create_evaluator(self, name):
            class _Eval:
                def format_for_custom_metric(self, item):
                    return {
                        "name": "m",
                        "description": "d",
                        "evaluation_prompt": "{question}",
                        "input_data": {"question": item["question"]},
                        "scoring_criteria": {"k": "v"},
                    }
            return _Eval()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Evaluations.cli.benchmark_cli.get_registry",
        lambda: _Registry(),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Evaluations.cli.benchmark_cli.load_benchmark_dataset",
        lambda name, source=None, limit=None, **kwargs: (
            called.__setitem__("loaded", True) or
            [{"id": "q1", "question": "q", "nonsensical_element": "n", "domain": "d"}]
        ),
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Evaluations.cli.benchmark_cli.run_async_safely",
        lambda coro: [{"score": 1.0, "explanation": "ok"}],
    )

    result = CliRunner().invoke(main, ["benchmark", "run", "bullshit_benchmark", "--limit", "1"])
    assert result.exit_code == 0
    assert called["loaded"] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tldw_Server_API/tests/Evaluations/unit/test_evals_cli_benchmark_commands.py -v`
Expected: FAIL because benchmark group/aliases/source forwarding are missing.

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/cli/evals_cli.py
from tldw_Server_API.app.core.Evaluations.cli.benchmark_cli import benchmark_group

main.add_command(benchmark_group, name="benchmark")

@main.command(name="list-benchmarks")
@click.option("--detailed", "-d", is_flag=True, help="Show detailed information")
@click.option("--output-format", "-o", type=click.Choice(["table", "json"]), default="table")
@click.pass_context
def list_benchmarks_alias(ctx, detailed, output_format):
    return ctx.invoke(benchmark_group.commands["list"], detailed=detailed, output_format=output_format)

# tldw_Server_API/app/core/Evaluations/cli/benchmark_cli.py
from tldw_Server_API.cli.utils.async_runner import run_async_safely

# in run():
batch_results = run_async_safely(_evaluate_batch(
    batch, evaluator, model or "openai", api_key, parallel
))
```

**Step 4: Run test to verify it passes**

Run: `pytest tldw_Server_API/tests/Evaluations/unit/test_evals_cli_benchmark_commands.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Evaluations/unit/test_evals_cli_benchmark_commands.py \
        tldw_Server_API/cli/evals_cli.py \
        tldw_Server_API/app/core/Evaluations/cli/benchmark_cli.py
git commit -m "feat(cli): expose benchmark commands in unified tldw-evals"
```

### Task 4: Add Unified Evaluations Benchmark API Endpoints

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_benchmarks.py`
- Create: `tldw_Server_API/tests/Evaluations/test_evaluations_benchmarks_api.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py`

**Step 1: Write the failing test**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from tldw_Server_API.app.api.v1.endpoints.evaluations import evaluations_benchmarks as benchmarks_ep
from tldw_Server_API.app.api.v1.endpoints.evaluations import evaluations_unified as eval_unified
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User


def _build_app():
    app = FastAPI()
    app.include_router(eval_unified.router, prefix="/api/v1")

    async def _verify_api_key_override():
        return "user_1"

    async def _get_user_override():
        return User(
            id=1,
            username="tester",
            email=None,
            is_active=True,
            roles=["admin"],
            permissions=["system.configure"],
        )

    async def _rate_limit_dep_override():
        return None

    app.dependency_overrides[eval_unified.verify_api_key] = _verify_api_key_override
    app.dependency_overrides[eval_unified.get_eval_request_user] = _get_user_override
    app.dependency_overrides[eval_unified.check_evaluation_rate_limit] = _rate_limit_dep_override
    return app


def test_benchmark_catalog_exposed_under_evaluations_namespace():
    app = _build_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/evaluations/benchmarks")
    assert response.status_code == 200
    names = [b["name"] for b in response.json()["data"]]
    assert "bullshit_benchmark" in names


def test_benchmark_run_endpoint_exists(monkeypatch):
    class _Reg:
        def get(self, name):
            if name != "bullshit_benchmark":
                return None
            return type("Cfg", (), {"evaluation_type": "bullshit_detection"})()
        def create_evaluator(self, _name):
            class _Eval:
                def format_for_custom_metric(self, item):
                    return {
                        "name": "bullshit_detection",
                        "description": "d",
                        "evaluation_prompt": "{question}",
                        "input_data": {"question": item["question"]},
                        "scoring_criteria": {"incoherence_identification": "x"},
                    }
            return _Eval()

    monkeypatch.setattr(benchmarks_ep, "get_registry", lambda: _Reg())
    monkeypatch.setattr(
        benchmarks_ep,
        "load_benchmark_dataset",
        lambda *args, **kwargs: [{"id": "q1", "question": "q", "nonsensical_element": "n", "domain": "d"}],
    )
    monkeypatch.setattr(
        benchmarks_ep.evaluation_manager,
        "evaluate_custom_metric",
        AsyncMock(return_value={"score": 0.9, "explanation": "ok"}),
    )

    app = _build_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/evaluations/benchmarks/bullshit_benchmark/run",
            json={"limit": 1, "api_name": "openai", "parallel": 1, "save_results": False},
        )
    assert response.status_code == 200
    assert response.json()["benchmark"] == "bullshit_benchmark"
```

**Step 2: Run test to verify it fails**

Run: `pytest tldw_Server_API/tests/Evaluations/test_evaluations_benchmarks_api.py -v`
Expected: FAIL with 404 route errors.

**Step 3: Write minimal implementation**

```python
# evaluations_benchmarks.py
benchmarks_router = APIRouter()

class BenchmarkRunRequest(BaseModel):
    limit: Optional[int] = None
    api_name: str = "openai"
    parallel: int = 4
    save_results: bool = True

@benchmarks_router.get("/benchmarks", dependencies=[Depends(require_eval_permissions(EVALS_READ))])
async def list_benchmarks(...):
    registry = get_registry()
    return {
        "data": [registry.get_benchmark_info(name) for name in registry.list_benchmarks()],
        "total": len(registry.list_benchmarks()),
    }

@benchmarks_router.get("/benchmarks/{benchmark_name}", dependencies=[Depends(require_eval_permissions(EVALS_READ))])
async def benchmark_info(...):
    ...

@benchmarks_router.post(
    "/benchmarks/{benchmark_name}/run",
    dependencies=[Depends(require_eval_permissions(EVALS_MANAGE)), Depends(check_evaluation_rate_limit)],
)
async def run_benchmark(...):
    config = registry.get(benchmark_name)
    # Do not force config.dataset_source globally; benchmark-specific loaders handle defaults.
    dataset = load_benchmark_dataset(benchmark_name, limit=request.limit)
    ...

# evaluations_unified.py
from .evaluations_benchmarks import benchmarks_router
router.include_router(benchmarks_router)
```

**Step 4: Run test to verify it passes**

Run: `pytest tldw_Server_API/tests/Evaluations/test_evaluations_benchmarks_api.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_benchmarks.py \
        tldw_Server_API/tests/Evaluations/test_evaluations_benchmarks_api.py \
        tldw_Server_API/app/api/v1/endpoints/evaluations/evaluations_unified.py
git commit -m "feat(api): add unified evaluations benchmark endpoints"
```

### Task 5: Surface Benchmark Selection in Evaluations UI Runs Tab

**Files:**
- Create: `apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RunsTab.benchmark-option.test.tsx`
- Modify: `apps/packages/ui/src/services/evaluations.ts`
- Modify: `apps/packages/ui/src/components/Option/Evaluations/hooks/useRuns.ts`
- Modify: `apps/packages/ui/src/store/evaluations.tsx`
- Modify: `apps/packages/ui/src/components/Option/Evaluations/tabs/RunsTab.tsx`

**Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react"
import { vi } from "vitest"
import { RunsTab } from "../RunsTab"

vi.mock("../hooks/useRuns", async () => {
  const actual = await vi.importActual<typeof import("../hooks/useRuns")>("../hooks/useRuns")
  return {
    ...actual,
    useBenchmarksCatalog: () => ({
      data: { data: { data: [{ name: "bullshit_benchmark", description: "Bullshit" }] } },
      isLoading: false,
      isError: false
    }),
    adhocEndpointOptions: [
      { value: "response-quality", label: "response-quality" },
      { value: "benchmark-run", label: "benchmark-run" }
    ]
  }
})

vi.mock("@/store/evaluations", () => ({
  useEvaluationsStore: (selector: any) =>
    selector({
      selectedEvalId: null,
      setSelectedEvalId: vi.fn(),
      selectedRunId: null,
      setSelectedRunId: vi.fn(),
      runConfigText: "",
      setRunConfigText: vi.fn(),
      datasetOverrideText: "",
      setDatasetOverrideText: vi.fn(),
      runIdempotencyKey: "run-idem-1",
      regenerateRunIdempotencyKey: vi.fn(),
      quotaSnapshot: null,
      setQuotaSnapshot: vi.fn(),
      isPolling: false,
      setIsPolling: vi.fn(),
      adhocEndpoint: "benchmark-run",
      setAdhocEndpoint: vi.fn(),
      adhocPayloadText: "{}",
      setAdhocPayloadText: vi.fn(),
      adhocResult: null
    })
}))

vi.mock("../hooks/useEvaluations", () => ({
  useEvaluationsList: () => ({ data: { data: { data: [] } } })
}))

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (_k: string, opts?: any) => opts?.defaultValue || _k })
}))

it("shows bullshit_benchmark in benchmark selector when benchmark-run mode is selected", async () => {
  render(<RunsTab />)
  expect(await screen.findByText("bullshit_benchmark")).toBeInTheDocument()
})
```

Note: follow the same mocking pattern used in `EvaluationsTab.empty-state.test.tsx` to satisfy AntD + store dependencies.

**Step 2: Run test to verify it fails**

Run: `cd apps/packages/ui && bun run vitest run src/components/Option/Evaluations/tabs/__tests__/RunsTab.benchmark-option.test.tsx`
Expected: FAIL because no benchmark endpoint option/selector exists.

**Step 3: Write minimal implementation**

```ts
// services/evaluations.ts
export async function listBenchmarks() {
  return await apiSend({ path: "/api/v1/evaluations/benchmarks" as any, method: "GET" })
}

export async function runBenchmark(benchmarkName: string, payload: Record<string, any>) {
  return await apiSend({
    path: `/api/v1/evaluations/benchmarks/${encodeURIComponent(benchmarkName)}/run` as any,
    method: "POST",
    body: payload,
  })
}

// hooks/useRuns.ts
export function useBenchmarksCatalog() {
  return useQuery({ queryKey: ["evaluations", "benchmarks"], queryFn: () => listBenchmarks() })
}

export const adhocEndpointOptions = [
  ...,
  { value: "benchmark-run", label: "benchmark-run" },
]

// RunsTab.tsx
// add benchmark selector when adhocEndpoint === "benchmark-run"
// default selected benchmark to "bullshit_benchmark" when present, otherwise first benchmark
// call runBenchmark(selectedBenchmark, payload) instead of createSpecializedEvaluation(...) for this mode
```

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RunsTab.benchmark-option.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RunsTab.benchmark-option.test.tsx \
        apps/packages/ui/src/services/evaluations.ts \
        apps/packages/ui/src/components/Option/Evaluations/hooks/useRuns.ts \
        apps/packages/ui/src/store/evaluations.tsx \
        apps/packages/ui/src/components/Option/Evaluations/tabs/RunsTab.tsx
git commit -m "feat(ui): add benchmark selection and run flow in evaluations tab"
```

### Task 6: Update Evals Documentation to Match Unified CLI/API

**Files:**
- Modify: `tldw_Server_API/app/core/Evaluations/README.md`
- Modify: `tldw_Server_API/app/core/Evaluations/EVALS_USER_GUIDE.md`
- Modify: `tldw_Server_API/app/api/v1/endpoints/benchmark_integration.md`

**Step 1: Write the failing docs check**

```bash
rg -n "tldw-evals list-benchmarks|tldw-evals run simple_bench|/api/v1/benchmarks/list" \
  tldw_Server_API/app/core/Evaluations/README.md \
  tldw_Server_API/app/core/Evaluations/EVALS_USER_GUIDE.md \
  tldw_Server_API/app/api/v1/endpoints/benchmark_integration.md
```

**Step 2: Run check to verify it fails (stale command paths present)**

Run: same `rg` command above.
Expected: stale legacy command/API examples are found.

**Step 3: Write minimal documentation updates**

```markdown
# Replace with unified syntax examples
tldw-evals benchmark list

tldw-evals benchmark info bullshit_benchmark

tldw-evals benchmark run bullshit_benchmark --limit 25

# Unified API paths
GET /api/v1/evaluations/benchmarks
GET /api/v1/evaluations/benchmarks/{benchmark_name}
POST /api/v1/evaluations/benchmarks/{benchmark_name}/run
```

**Step 4: Re-run docs check to verify pass**

Run:
```bash
rg -n "tldw-evals benchmark (list|info|run)|/api/v1/evaluations/benchmarks" \
  tldw_Server_API/app/core/Evaluations/README.md \
  tldw_Server_API/app/core/Evaluations/EVALS_USER_GUIDE.md \
  tldw_Server_API/app/api/v1/endpoints/benchmark_integration.md
```
Expected: updated paths present.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Evaluations/README.md \
        tldw_Server_API/app/core/Evaluations/EVALS_USER_GUIDE.md \
        tldw_Server_API/app/api/v1/endpoints/benchmark_integration.md
git commit -m "docs(evals): align benchmark docs with unified CLI/API and bullshit benchmark"
```

### Task 7: Final Verification Sweep

**Files:**
- No new files; verification only.

**Step 1: Run backend benchmark-focused tests**

Run:
```bash
pytest \
  tldw_Server_API/tests/Evaluations/unit/test_bullshit_benchmark_loader.py \
  tldw_Server_API/tests/Evaluations/unit/test_bullshit_benchmark_registry.py \
  tldw_Server_API/tests/Evaluations/unit/test_evals_cli_benchmark_commands.py \
  tldw_Server_API/tests/Evaluations/test_evaluations_benchmarks_api.py -v
```
Expected: PASS.

**Step 2: Run UI benchmark selector test**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Evaluations/tabs/__tests__/RunsTab.benchmark-option.test.tsx`
Expected: PASS.

**Step 3: Run CLI smoke checks**

Run:
```bash
python3 -m tldw_Server_API.cli.evals_cli --help
python3 -m tldw_Server_API.cli.evals_cli benchmark list --output-format json
```
Expected: CLI includes `benchmark` group and listing contains `bullshit_benchmark`.

**Step 4: Run targeted regression checks for existing benchmark behavior**

Run:
```bash
pytest tldw_Server_API/tests/http_client/test_benchmark_loaders_http.py -v
```
Expected: PASS (no regressions in shared loader behavior).

**Step 5: Commit verification notes (if tracked) and prepare PR summary**

```bash
git status
git log --oneline -n 8
```

Expected: clean working tree (or only intended files), coherent incremental commit history.
