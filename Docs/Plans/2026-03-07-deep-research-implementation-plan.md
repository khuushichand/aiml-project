# Deep Research Backend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a backend-first deep research module with durable research sessions, manifest-backed artifacts, Jobs-driven execution slices, checkpoint review, and a minimal API for create/status/approve/package flows.

**Architecture:** Implement a SQLite-first `research_session` repository behind a small service layer so the feature can ship incrementally without overcommitting to a second storage backend on day one. Keep active execution inside core Jobs, keep waiting-for-human state in the session store, and persist internal artifacts under per-user outputs with a DB-backed manifest. Reuse existing research adapters and Jobs streaming rather than inventing parallel orchestration or transport.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, sqlite3, pytest, core Jobs (`JobManager`, `WorkerSDK`), existing outputs/file-artifacts services in `tldw_Server_API`.

---

### Task 1: Create Research Session Persistence (TDD)

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/db_path_utils.py`
- Create: `tldw_Server_API/tests/Research/test_research_sessions_db.py`
- Create: `tldw_Server_API/tests/DB_Management/test_research_db_paths.py`

**Skill:** @test-driven-development

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Research/test_research_sessions_db.py
from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB


def test_create_session_and_checkpoint_round_trip(tmp_path):
    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="7",
        query="Compare local and external evidence on quantum networking",
        source_policy="balanced",
        autonomy_mode="checkpointed",
        limits_json={"max_searches": 25},
    )

    assert session.phase == "drafting_plan"
    stored = db.get_session(session.id)
    assert stored is not None
    assert stored.query.startswith("Compare")

    checkpoint = db.create_checkpoint(
        session_id=session.id,
        checkpoint_type="plan_review",
        proposed_payload={"focus_areas": ["background", "primary sources"]},
    )
    resolved = db.resolve_checkpoint(
        checkpoint.id,
        resolution="patched",
        user_patch_payload={"focus_areas": ["background", "contradictions"]},
    )

    assert resolved.status == "resolved"
    assert resolved.user_patch_payload["focus_areas"][1] == "contradictions"
```

```python
# tldw_Server_API/tests/DB_Management/test_research_db_paths.py
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


def test_research_db_path_is_per_user(tmp_path, monkeypatch):
    monkeypatch.setenv("TLDW_DATABASES_ROOT", str(tmp_path))
    path = DatabasePaths.get_research_sessions_db_path(42)
    assert path.name == "ResearchSessions.db"
    assert "user_databases/42" in str(path)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_sessions_db.py tldw_Server_API/tests/DB_Management/test_research_db_paths.py -v`

Expected: FAIL with `ModuleNotFoundError` and missing `DatabasePaths.get_research_sessions_db_path`.

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py
@dataclass
class ResearchSessionRow:
    id: str
    owner_user_id: str
    status: str
    phase: str
    query: str
    source_policy: str
    autonomy_mode: str
    limits_json: dict[str, Any]


class ResearchSessionsDB:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._ensure_schema()

    def create_session(...): ...
    def get_session(self, session_id: str): ...
    def update_phase(self, session_id: str, *, phase: str, status: str): ...
    def create_checkpoint(...): ...
    def resolve_checkpoint(...): ...
```

```python
# tldw_Server_API/app/core/DB_Management/db_path_utils.py
@staticmethod
def get_research_sessions_db_path(user_id: int | str) -> Path:
    return DatabasePaths.get_user_database_dir(user_id) / "ResearchSessions.db"
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_sessions_db.py tldw_Server_API/tests/DB_Management/test_research_db_paths.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/app/core/DB_Management/db_path_utils.py tldw_Server_API/tests/Research/test_research_sessions_db.py tldw_Server_API/tests/DB_Management/test_research_db_paths.py
git commit -m "feat(research): add research session persistence foundation"
```

### Task 2: Add Internal Artifact Store And Manifest Writes (TDD)

**Files:**
- Create: `tldw_Server_API/app/core/Research/__init__.py`
- Create: `tldw_Server_API/app/core/Research/models.py`
- Create: `tldw_Server_API/app/core/Research/artifact_store.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Create: `tldw_Server_API/tests/Research/test_research_artifact_store.py`

**Skill:** @test-driven-development

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.DB_Management.ResearchSessionsDB import ResearchSessionsDB
from tldw_Server_API.app.core.Research.artifact_store import ResearchArtifactStore


def test_write_json_artifact_records_manifest(tmp_path):
    db = ResearchSessionsDB(tmp_path / "research.db")
    session = db.create_session(
        owner_user_id="1",
        query="Test query",
        source_policy="balanced",
        autonomy_mode="autonomous",
        limits_json={},
    )
    store = ResearchArtifactStore(base_dir=tmp_path / "outputs", db=db)

    artifact = store.write_json(
        owner_user_id=1,
        session_id=session.id,
        artifact_name="plan.json",
        payload={"focus_areas": ["history", "market structure"]},
        phase="drafting_plan",
        job_id="123",
    )

    assert artifact.byte_size > 0
    manifest = db.list_artifacts(session.id)
    assert manifest[0].artifact_name == "plan.json"
    assert (tmp_path / "outputs" / "research" / session.id / "plan.json").exists()
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_artifact_store.py -v`

Expected: FAIL with `ModuleNotFoundError` for `artifact_store` and missing artifact manifest methods.

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/Research/artifact_store.py
class ResearchArtifactStore:
    def __init__(self, *, base_dir: Path, db: ResearchSessionsDB):
        self.base_dir = Path(base_dir)
        self.db = db

    def write_json(self, *, owner_user_id: int, session_id: str, artifact_name: str, payload: dict[str, Any], phase: str, job_id: str | None) -> ResearchArtifact:
        session_dir = self.base_dir / "research" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / artifact_name
        encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        path.write_bytes(encoded)
        checksum = hashlib.sha256(encoded).hexdigest()
        return self.db.record_artifact(...)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_artifact_store.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/__init__.py tldw_Server_API/app/core/Research/models.py tldw_Server_API/app/core/Research/artifact_store.py tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/tests/Research/test_research_artifact_store.py
git commit -m "feat(research): add manifest-backed internal artifact store"
```

### Task 3: Build Planner, Limits, And Checkpoint Merge Logic (TDD)

**Files:**
- Create: `tldw_Server_API/app/core/Research/planner.py`
- Create: `tldw_Server_API/app/core/Research/limits.py`
- Create: `tldw_Server_API/app/core/Research/checkpoint_service.py`
- Create: `tldw_Server_API/tests/Research/test_research_planner.py`
- Create: `tldw_Server_API/tests/Research/test_research_limits.py`
- Create: `tldw_Server_API/tests/Research/test_research_checkpoint_service.py`

**Skill:** @test-driven-development

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.Research.checkpoint_service import apply_checkpoint_patch
from tldw_Server_API.app.core.Research.limits import ResearchLimits, ensure_limit_available
from tldw_Server_API.app.core.Research.planner import build_initial_plan


def test_build_initial_plan_produces_bounded_focus_areas():
    plan = build_initial_plan(
        query="Assess how local corpus notes and external web sources disagree on GPU memory bandwidth trends",
        source_policy="balanced",
        autonomy_mode="checkpointed",
    )
    assert 3 <= len(plan.focus_areas) <= 7
    assert plan.stop_criteria["min_cited_sections"] >= 1


def test_checkpoint_patch_replaces_focus_areas_without_dropping_other_keys():
    merged = apply_checkpoint_patch(
        proposed_payload={"focus_areas": ["background"], "source_policy": "balanced"},
        patch_payload={"focus_areas": ["background", "contradictions"]},
    )
    assert merged["source_policy"] == "balanced"
    assert merged["focus_areas"][1] == "contradictions"


def test_limits_raise_when_budget_exhausted():
    limits = ResearchLimits(max_searches=2, max_fetched_docs=5, max_runtime_seconds=300)
    usage = {"searches": 2}
    exc = ensure_limit_available(limits, usage, "searches")
    assert exc.code == "research_limit_exceeded"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_planner.py tldw_Server_API/tests/Research/test_research_limits.py tldw_Server_API/tests/Research/test_research_checkpoint_service.py -v`

Expected: FAIL with missing planner, limits, and checkpoint modules.

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/Research/planner.py
def build_initial_plan(*, query: str, source_policy: str, autonomy_mode: str) -> ResearchPlan:
    focus_areas = _seed_focus_areas(query)[:5]
    return ResearchPlan(
        focus_areas=focus_areas,
        source_policy=source_policy,
        autonomy_mode=autonomy_mode,
        stop_criteria={"min_cited_sections": 1, "max_iterations": 3},
    )
```

```python
# tldw_Server_API/app/core/Research/checkpoint_service.py
def apply_checkpoint_patch(*, proposed_payload: dict[str, Any], patch_payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(proposed_payload)
    merged.update(patch_payload)
    return merged
```

```python
# tldw_Server_API/app/core/Research/limits.py
@dataclass(frozen=True)
class ResearchLimits:
    max_searches: int
    max_fetched_docs: int
    max_runtime_seconds: int


def ensure_limit_available(limits: ResearchLimits, usage: dict[str, int], key: str):
    current = int(usage.get(key, 0))
    limit = getattr(limits, f"max_{key}")
    if current >= limit:
        return ResearchLimitError(code="research_limit_exceeded", limit_key=key)
    return None
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_planner.py tldw_Server_API/tests/Research/test_research_limits.py tldw_Server_API/tests/Research/test_research_checkpoint_service.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/planner.py tldw_Server_API/app/core/Research/limits.py tldw_Server_API/app/core/Research/checkpoint_service.py tldw_Server_API/tests/Research/test_research_planner.py tldw_Server_API/tests/Research/test_research_limits.py tldw_Server_API/tests/Research/test_research_checkpoint_service.py
git commit -m "feat(research): add planning, limit, and checkpoint primitives"
```

### Task 4: Wire Research Sessions To Core Jobs And Worker Slices (TDD)

**Files:**
- Create: `tldw_Server_API/app/core/Research/service.py`
- Create: `tldw_Server_API/app/core/Research/jobs.py`
- Create: `tldw_Server_API/app/core/Research/jobs_worker.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Create: `tldw_Server_API/tests/Research/test_research_jobs_service.py`
- Create: `tldw_Server_API/tests/Research/test_research_jobs_worker.py`

**Skill:** @test-driven-development

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.Research.jobs import enqueue_research_phase_job
from tldw_Server_API.app.core.Research.service import ResearchService


def test_create_session_enqueues_planning_job(monkeypatch, tmp_path):
    captured = {}

    class DummyJobs:
        def create_job(self, **kwargs):
            captured.update(kwargs)
            return {"id": 9, "uuid": "job-9", "status": "queued"}

    service = ResearchService(
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
        job_manager=DummyJobs(),
    )

    session = service.create_session(
        owner_user_id="1",
        query="Map evidence gaps between internal notes and public filings",
        source_policy="balanced",
        autonomy_mode="checkpointed",
    )

    assert session.phase == "drafting_plan"
    assert captured["domain"] == "research"
    assert captured["job_type"] == "research_phase"
    assert captured["payload"]["session_id"] == session.id
```

```python
import asyncio

from tldw_Server_API.app.core.Research.jobs import handle_research_phase_job


async def test_planning_job_writes_plan_and_opens_checkpoint(tmp_path):
    result = await handle_research_phase_job(
        {
            "id": 5,
            "payload": {
                "session_id": "rs_1",
                "phase": "drafting_plan",
                "checkpoint_id": None,
                "policy_version": 1,
            },
        },
        research_db_path=tmp_path / "research.db",
        outputs_dir=tmp_path / "outputs",
        seed_session={
            "id": "rs_1",
            "owner_user_id": "1",
            "query": "Test planning",
            "source_policy": "balanced",
            "autonomy_mode": "checkpointed",
            "phase": "drafting_plan",
            "status": "queued",
        },
    )

    assert result["phase"] == "awaiting_plan_review"
    assert result["artifacts_written"] >= 1
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_jobs_worker.py -v`

Expected: FAIL with missing `ResearchService` and research Jobs handler.

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/Research/service.py
class ResearchService:
    def create_session(...):
        session = self.db.create_session(...)
        job = enqueue_research_phase_job(
            jm=self.job_manager,
            session_id=session.id,
            phase="drafting_plan",
            owner_user_id=session.owner_user_id,
        )
        self.db.attach_active_job(session.id, str(job["id"]))
        return self.db.get_session(session.id)
```

```python
# tldw_Server_API/app/core/Research/jobs.py
def enqueue_research_phase_job(*, jm, session_id: str, phase: str, owner_user_id: str, checkpoint_id: str | None = None):
    return jm.create_job(
        domain="research",
        queue="default",
        job_type="research_phase",
        payload={"session_id": session_id, "phase": phase, "checkpoint_id": checkpoint_id, "policy_version": 1},
        owner_user_id=owner_user_id,
        idempotency_key=f"research:{session_id}:{phase}:{checkpoint_id or 'none'}",
    )
```

```python
# tldw_Server_API/app/core/Research/jobs_worker.py
async def run_research_jobs_worker(stop_event: asyncio.Event | None = None) -> None:
    cfg = WorkerConfig(domain="research", queue="default", worker_id=f"research-{os.getpid()}")
    sdk = WorkerSDK(jobs_manager_from_env(), cfg)
    await sdk.run(handler=handle_research_phase_job)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_jobs_worker.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/service.py tldw_Server_API/app/core/Research/jobs.py tldw_Server_API/app/core/Research/jobs_worker.py tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_jobs_worker.py
git commit -m "feat(research): drive research sessions through core Jobs slices"
```

### Task 5: Add Research Runs API And Router Registration (TDD)

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/research_runs.py`
- Modify: `tldw_Server_API/app/main.py`
- Create: `tldw_Server_API/tests/Research/test_research_runs_endpoint.py`

**Skill:** @test-driven-development

**Step 1: Write the failing test**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User


def test_create_and_approve_research_run(monkeypatch, tmp_path):
    from tldw_Server_API.app.api.v1.endpoints.research_runs import router

    app = FastAPI()
    app.include_router(router)

    class StubService:
        def create_session(self, **kwargs):
            return {
                "id": "rs_1",
                "status": "queued",
                "phase": "drafting_plan",
                "active_job_id": "9",
            }

        def approve_checkpoint(self, session_id: str, checkpoint_id: str, patch_payload=None):
            return {"id": session_id, "phase": "collecting", "status": "queued", "latest_checkpoint_id": checkpoint_id}

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.research_runs.get_research_service",
        lambda: StubService(),
    )

    with TestClient(app) as client:
        create_resp = client.post("/api/v1/research/runs", json={"query": "Test deep research run"})
        assert create_resp.status_code == 200
        assert create_resp.json()["id"] == "rs_1"

        approve_resp = client.post(
            "/api/v1/research/runs/rs_1/checkpoints/cp_1/patch-and-approve",
            json={"patch_payload": {"focus_areas": ["background", "counterevidence"]}},
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["phase"] == "collecting"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`

Expected: FAIL with missing router and schemas.

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py
class ResearchRunCreateRequest(BaseModel):
    query: str
    source_policy: str = "balanced"
    autonomy_mode: str = "checkpointed"


class ResearchRunResponse(BaseModel):
    id: str
    status: str
    phase: str
    active_job_id: str | None = None
```

```python
# tldw_Server_API/app/api/v1/endpoints/research_runs.py
router = APIRouter(prefix="/api/v1/research", tags=["research-runs"])


@router.post("/runs", response_model=ResearchRunResponse)
async def create_research_run(body: ResearchRunCreateRequest, current_user: User = Depends(get_request_user)):
    service = get_research_service()
    return service.create_session(owner_user_id=str(current_user.id), **body.model_dump())
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_runs_endpoint.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py tldw_Server_API/app/api/v1/endpoints/research_runs.py tldw_Server_API/app/main.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py
git commit -m "feat(api): add deep research runs endpoints"
```

### Task 6: Package Final Output, Export It, And Verify End-To-End (TDD)

**Files:**
- Create: `tldw_Server_API/app/core/Research/exporter.py`
- Create: `tldw_Server_API/app/core/File_Artifacts/adapters/research_package_adapter.py`
- Modify: `tldw_Server_API/app/core/File_Artifacts/adapter_registry.py`
- Modify: `tldw_Server_API/app/core/Research/service.py`
- Create: `tldw_Server_API/tests/Research/test_research_exporter.py`
- Create: `tldw_Server_API/tests/Research/test_research_package_adapter.py`
- Create: `tldw_Server_API/tests/e2e/test_deep_research_runs.py`

**Skill:** @test-driven-development

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.Research.exporter import build_final_package


def test_build_final_package_requires_citations():
    package = build_final_package(
        brief={"query": "Test"},
        outline={"sections": ["Overview"]},
        report_markdown="# Overview\nBody",
        claims=[{"text": "Claim", "citations": [{"source_id": "src_1"}]}],
        source_inventory=[{"source_id": "src_1", "title": "Source 1"}],
    )
    assert package["claims"][0]["citations"][0]["source_id"] == "src_1"
    assert package["report_markdown"].startswith("# Overview")
```

```python
from tldw_Server_API.app.core.File_Artifacts.adapter_registry import FileAdapterRegistry


def test_research_package_adapter_registers_and_exports_markdown():
    registry = FileAdapterRegistry()
    adapter = registry.get_adapter("research_package")
    assert adapter is not None
    export = adapter.export(
        {
            "question": "What changed?",
            "report_markdown": "# Report\nAnswer",
            "claims": [{"text": "Claim", "citations": [{"source_id": "src_1"}]}],
            "source_inventory": [{"source_id": "src_1", "title": "Source 1"}],
        },
        format="md",
    )
    assert export.status == "ready"
    assert export.content.startswith(b"# Report")
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_exporter.py tldw_Server_API/tests/Research/test_research_package_adapter.py -v`

Expected: FAIL with missing exporter and missing `research_package` adapter.

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/Research/exporter.py
def build_final_package(*, brief, outline, report_markdown, claims, source_inventory):
    for claim in claims:
        if not claim.get("citations"):
            raise ValueError("claim_missing_citations")
    return {
        "question": brief["query"],
        "outline": outline,
        "report_markdown": report_markdown,
        "claims": claims,
        "source_inventory": source_inventory,
        "unresolved_questions": [],
    }
```

```python
# tldw_Server_API/app/core/File_Artifacts/adapters/research_package_adapter.py
class ResearchPackageAdapter:
    file_type = "research_package"
    export_formats = {"json", "md"}

    def normalize(self, payload):
        return payload

    def validate(self, structured):
        return []

    def export(self, structured, *, format: str):
        if format == "json":
            content = json.dumps(structured, indent=2).encode("utf-8")
        else:
            content = structured["report_markdown"].encode("utf-8")
        return ExportResult(status="ready", content=content, bytes_len=len(content), content_type="text/markdown" if format == "md" else "application/json")
```

**Step 4: Run verification suite**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_exporter.py tldw_Server_API/tests/Research/test_research_package_adapter.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Research tldw_Server_API/app/api/v1/endpoints/research_runs.py tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py -f json -o /tmp/bandit_deep_research.json
```

Expected: pytest PASS, Bandit reports no new high-signal findings in touched files.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Research/exporter.py tldw_Server_API/app/core/File_Artifacts/adapters/research_package_adapter.py tldw_Server_API/app/core/File_Artifacts/adapter_registry.py tldw_Server_API/app/core/Research/service.py tldw_Server_API/tests/Research/test_research_exporter.py tldw_Server_API/tests/Research/test_research_package_adapter.py tldw_Server_API/tests/e2e/test_deep_research_runs.py
git commit -m "feat(research): package and export deep research results"
```

## Notes For Execution

- Keep the implementation SQLite-first, but do not leak SQLite specifics beyond `ResearchSessionsDB`.
- Keep Jobs payloads tiny; never stuff research artifacts or raw fetched content into Jobs payload/result.
- Reuse `tldw_Server_API/app/core/RAG/rag_service/research_agent.py` and `tldw_Server_API/app/core/Workflows/adapters/research/` as implementation references, not as the public domain abstraction.
- Defer workflow/chat consumers until this backend contract is stable and verified.
