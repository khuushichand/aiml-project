# Text2SQL Retriever Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a secure text2sql retriever that works both as a standalone API and as a unified RAG source, returning SQL + results under strict read-only guardrails.

**Architecture:** Implement a shared `Text2SQLCoreService` with source-registry validation, schema catalog, SQL generation, AST guard, and adapter-based execution. Integrate this shared core into both `/api/v1/text2sql/query` and RAG source orchestration (`sources=["sql"]`) with fail-closed source handling. Apply strict policy controls (single read-only statement, limit clamp, timeout, read-only execution context, connector ACL).

**Tech Stack:** FastAPI, Pydantic v2, existing AuthNZ/RBAC deps, DB adapter abstractions, pytest, Hypothesis, Bandit, and `sqlglot` for SQL AST validation/rewrite.

---

### Task 1: Add Text2SQL module scaffolding and parser dependency

**Files:**
- Modify: `pyproject.toml`
- Create: `tldw_Server_API/app/core/Text2SQL/__init__.py`
- Create: `tldw_Server_API/tests/Text2SQL/test_imports.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Text2SQL/test_imports.py
from importlib import import_module


def test_text2sql_module_imports():
    mod = import_module("tldw_Server_API.app.core.Text2SQL")
    assert mod is not None
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Text2SQL/test_imports.py -v`
Expected: FAIL with `ModuleNotFoundError`.

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/Text2SQL/__init__.py
"""Text2SQL core package."""
```

Add dependency in `pyproject.toml`:
```toml
"sqlglot>=25.0.0",
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Text2SQL/test_imports.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add pyproject.toml tldw_Server_API/app/core/Text2SQL/__init__.py tldw_Server_API/tests/Text2SQL/test_imports.py
git commit -m "chore(text2sql): add module scaffold and sql parser dependency"
```

### Task 2: Implement canonical source registry (fail closed)

**Files:**
- Create: `tldw_Server_API/app/core/Text2SQL/source_registry.py`
- Create: `tldw_Server_API/tests/Text2SQL/test_source_registry.py`

**Step 1: Write the failing test**

```python
import pytest

from tldw_Server_API.app.core.Text2SQL.source_registry import normalize_source


def test_normalize_source_accepts_sql_alias():
    assert normalize_source("sql") == "sql"


def test_normalize_source_rejects_unknown_source():
    with pytest.raises(ValueError):
        normalize_source("unknown_source")
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Text2SQL/test_source_registry.py -v`
Expected: FAIL because module/functions do not exist.

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/Text2SQL/source_registry.py
ALIAS_MAP = {
    "media": "media_db",
    "media_db": "media_db",
    "notes": "notes",
    "characters": "characters",
    "character_cards": "characters",
    "chats": "chats",
    "kanban": "kanban",
    "kanban_db": "kanban",
    "sql": "sql",
}

ALLOWED_SOURCES = frozenset({"media_db", "notes", "characters", "chats", "kanban", "sql"})


def normalize_source(value: str) -> str:
    key = str(value).strip().lower()
    normalized = ALIAS_MAP.get(key, key)
    if normalized not in ALLOWED_SOURCES:
        raise ValueError(f"Invalid source '{value}'. Allowed: {sorted(ALLOWED_SOURCES)}")
    return normalized


def normalize_sources(values: list[str] | None) -> list[str]:
    if values is None:
        return ["media_db"]
    return [normalize_source(v) for v in values]
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Text2SQL/test_source_registry.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Text2SQL/source_registry.py tldw_Server_API/tests/Text2SQL/test_source_registry.py
git commit -m "feat(text2sql): add canonical fail-closed source registry"
```

### Task 3: Wire source registry into RAG schema and data source enum

**Files:**
- Modify: `tldw_Server_API/app/core/RAG/rag_service/types.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/rag_schemas_unified.py`
- Create: `tldw_Server_API/tests/RAG/test_rag_sources_sql_validation.py`

**Step 1: Write the failing test**

```python
import pytest

from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGRequest


def test_rag_sources_accept_sql():
    req = UnifiedRAGRequest(query="q", sources=["sql"])
    assert req.sources == ["sql"]


def test_rag_sources_reject_unknown():
    with pytest.raises(ValueError):
        UnifiedRAGRequest(query="q", sources=["bogus"])
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG/test_rag_sources_sql_validation.py -v`
Expected: FAIL because `sql` not allowed.

**Step 3: Write minimal implementation**

```python
# types.py
class DataSource(Enum):
    ...
    SQL = "sql"
```

```python
# rag_schemas_unified.py (inside sources validator)
from tldw_Server_API.app.core.Text2SQL.source_registry import normalize_sources

...
return normalize_sources(v)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG/test_rag_sources_sql_validation.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/RAG/rag_service/types.py tldw_Server_API/app/api/v1/schemas/rag_schemas_unified.py tldw_Server_API/tests/RAG/test_rag_sources_sql_validation.py
git commit -m "feat(rag): add sql datasource and centralized source validation"
```

### Task 4: Implement strict SQL guard (AST validation + deterministic LIMIT rewrite)

**Files:**
- Create: `tldw_Server_API/app/core/Text2SQL/sql_guard.py`
- Create: `tldw_Server_API/tests/Text2SQL/test_sql_guard.py`

**Step 1: Write the failing test**

```python
import pytest

from tldw_Server_API.app.core.Text2SQL.sql_guard import SqlGuard, SqlPolicyViolation


def test_guard_accepts_select_and_injects_limit():
    guard = SqlGuard(default_limit=100, max_limit=500)
    out = guard.validate_and_rewrite("SELECT id FROM media")
    assert "LIMIT 100" in out.sql.upper()


def test_guard_rejects_multi_statement():
    guard = SqlGuard(default_limit=100, max_limit=500)
    with pytest.raises(SqlPolicyViolation):
        guard.validate_and_rewrite("SELECT 1; SELECT 2")


def test_guard_rejects_write_statement():
    guard = SqlGuard(default_limit=100, max_limit=500)
    with pytest.raises(SqlPolicyViolation):
        guard.validate_and_rewrite("DELETE FROM media")
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Text2SQL/test_sql_guard.py -v`
Expected: FAIL due missing guard implementation.

**Step 3: Write minimal implementation**

```python
# sql_guard.py
from dataclasses import dataclass
import sqlglot
from sqlglot import exp


class SqlPolicyViolation(ValueError):
    pass


@dataclass
class GuardedSql:
    sql: str
    limit_injected: bool
    limit_clamped: bool


class SqlGuard:
    def __init__(self, default_limit: int, max_limit: int):
        self.default_limit = default_limit
        self.max_limit = max_limit

    def validate_and_rewrite(self, sql: str) -> GuardedSql:
        tree = sqlglot.parse_one(sql)
        if not isinstance(tree, (exp.Select, exp.With)):
            raise SqlPolicyViolation("Only SELECT/WITH queries are allowed")
        if ";" in sql.strip().rstrip(";"):
            raise SqlPolicyViolation("Multiple statements are not allowed")
        limit = tree.args.get("limit")
        injected = False
        clamped = False
        if limit is None:
            tree = tree.limit(self.default_limit)
            injected = True
        else:
            lit = int(limit.expression.this)
            if lit > self.max_limit:
                tree = tree.limit(self.max_limit)
                clamped = True
        return GuardedSql(sql=tree.sql(), limit_injected=injected, limit_clamped=clamped)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Text2SQL/test_sql_guard.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Text2SQL/sql_guard.py tldw_Server_API/tests/Text2SQL/test_sql_guard.py
git commit -m "feat(text2sql): add strict SQL AST guard with limit rewrite"
```

### Task 5: Add connector registry and executor interfaces (no raw DSNs in API)

**Files:**
- Create: `tldw_Server_API/app/core/Text2SQL/connectors.py`
- Create: `tldw_Server_API/app/core/Text2SQL/executor.py`
- Create: `tldw_Server_API/tests/Text2SQL/test_connectors.py`

**Step 1: Write the failing test**

```python
import pytest

from tldw_Server_API.app.core.Text2SQL.connectors import ConnectorRegistry


def test_connector_lookup_by_id_only():
    reg = ConnectorRegistry({"finance_warehouse": {"dialect": "postgresql"}})
    cfg = reg.get("finance_warehouse")
    assert cfg["dialect"] == "postgresql"


def test_connector_lookup_rejects_unknown_id():
    reg = ConnectorRegistry({})
    with pytest.raises(KeyError):
        reg.get("postgresql://raw-dsn-not-allowed")
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Text2SQL/test_connectors.py -v`
Expected: FAIL due missing classes.

**Step 3: Write minimal implementation**

```python
# connectors.py
class ConnectorRegistry:
    def __init__(self, mappings: dict[str, dict]):
        self._mappings = mappings

    def get(self, connector_id: str) -> dict:
        if connector_id not in self._mappings:
            raise KeyError(f"Unknown connector id: {connector_id}")
        return self._mappings[connector_id]
```

```python
# executor.py
from typing import Protocol


class SqlExecutor(Protocol):
    async def execute(self, sql: str, *, timeout_ms: int, max_rows: int) -> dict: ...
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Text2SQL/test_connectors.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Text2SQL/connectors.py tldw_Server_API/app/core/Text2SQL/executor.py tldw_Server_API/tests/Text2SQL/test_connectors.py
git commit -m "feat(text2sql): add connector-id registry and executor interface"
```

### Task 6: Implement Text2SQLCoreService orchestration

**Files:**
- Create: `tldw_Server_API/app/core/Text2SQL/service.py`
- Create: `tldw_Server_API/tests/Text2SQL/test_service.py`

**Step 1: Write the failing test**

```python
import pytest

from tldw_Server_API.app.core.Text2SQL.service import Text2SQLCoreService


class StubGenerator:
    async def generate(self, **kwargs):
        return {"sql": "SELECT id FROM media"}


class StubExecutor:
    async def execute(self, sql: str, *, timeout_ms: int, max_rows: int):
        return {"columns": ["id"], "rows": [[1], [2]], "row_count": 2}


@pytest.mark.asyncio
async def test_service_returns_sql_and_rows():
    svc = Text2SQLCoreService(generator=StubGenerator(), executor=StubExecutor())
    result = await svc.generate_and_execute(query="list ids", target_id="media_db")
    assert result["sql"]
    assert result["row_count"] == 2
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Text2SQL/test_service.py -v`
Expected: FAIL due missing service.

**Step 3: Write minimal implementation**

```python
# service.py
import time

from .sql_guard import SqlGuard


class Text2SQLCoreService:
    def __init__(self, *, generator, executor, guard: SqlGuard | None = None):
        self.generator = generator
        self.executor = executor
        self.guard = guard or SqlGuard(default_limit=100, max_limit=500)

    async def generate_and_execute(self, *, query: str, target_id: str, timeout_ms: int = 5000, max_rows: int = 100):
        t0 = time.perf_counter()
        generated = await self.generator.generate(query=query, target_id=target_id)
        guarded = self.guard.validate_and_rewrite(generated["sql"])
        out = await self.executor.execute(guarded.sql, timeout_ms=timeout_ms, max_rows=max_rows)
        return {
            "sql": guarded.sql,
            "columns": out["columns"],
            "rows": out["rows"],
            "row_count": out["row_count"],
            "duration_ms": int((time.perf_counter() - t0) * 1000),
            "guardrail": {"limit_injected": guarded.limit_injected, "limit_clamped": guarded.limit_clamped},
            "target_id": target_id,
        }
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Text2SQL/test_service.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Text2SQL/service.py tldw_Server_API/tests/Text2SQL/test_service.py
git commit -m "feat(text2sql): add core generate+guard+execute service"
```

### Task 7: Add standalone Text2SQL endpoint

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/text2sql_schemas.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/text2sql.py`
- Modify: `tldw_Server_API/app/main.py`
- Create: `tldw_Server_API/tests/integration/test_text2sql_endpoint.py`

**Step 1: Write the failing test**

```python
def test_text2sql_route_exists(test_client):
    r = test_client.post("/api/v1/text2sql/query", json={"query": "count media", "target_id": "media_db"})
    assert r.status_code in (200, 422, 403)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/integration/test_text2sql_endpoint.py::test_text2sql_route_exists -v`
Expected: FAIL with 404.

**Step 3: Write minimal implementation**

```python
# text2sql_schemas.py
from pydantic import BaseModel, Field


class Text2SQLRequest(BaseModel):
    query: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)
    max_rows: int = Field(default=100, ge=1, le=1000)


class Text2SQLResponse(BaseModel):
    sql: str
    columns: list[str]
    rows: list[list]
    row_count: int
    duration_ms: int
    target_id: str
    guardrail: dict
```

```python
# text2sql.py
router = APIRouter(prefix="/api/v1/text2sql", tags=["text2sql"])

@router.post("/query", response_model=Text2SQLResponse)
async def query_text2sql(...):
    ...
```

```python
# main.py include router
from tldw_Server_API.app.api.v1.endpoints.text2sql import router as text2sql_router
app.include_router(text2sql_router, tags=["text2sql"])
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/integration/test_text2sql_endpoint.py::test_text2sql_route_exists -v`
Expected: PASS (non-404).

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/text2sql_schemas.py tldw_Server_API/app/api/v1/endpoints/text2sql.py tldw_Server_API/app/main.py tldw_Server_API/tests/integration/test_text2sql_endpoint.py
git commit -m "feat(api): add text2sql query endpoint"
```

### Task 8: Add SQL retriever and integrate into multi-source RAG pipeline

**Files:**
- Modify: `tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py`
- Modify: `tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py`
- Create: `tldw_Server_API/tests/RAG/test_sql_retriever_integration.py`

**Step 1: Write the failing test**

```python
import pytest

from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline


@pytest.mark.asyncio
async def test_unified_rag_accepts_sql_source(monkeypatch):
    result = await unified_rag_pipeline(query="sql question", sources=["sql"], enable_generation=False)
    assert result is not None
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG/test_sql_retriever_integration.py -v`
Expected: FAIL because `sql` source is not mapped/retrieved.

**Step 3: Write minimal implementation**

```python
# database_retrievers.py
class SQLRetriever(BaseRetriever):
    async def retrieve(self, query: str, **kwargs) -> list[Document]:
        # call Text2SQLCoreService and map rows -> Document
        ...
```

Update `MultiDatabaseRetriever.__init__`:
```python
if "sql" in db_paths:
    self.retrievers[DataSource.SQL] = SQLRetriever(...)
```

Update source mapping in `unified_pipeline.py` to use canonical registry and explicit SQL mapping:
```python
"sql": DataSource.SQL,
```

Remove fallback defaults that map unknown entries to `DataSource.MEDIA_DB`; raise on unknown source.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG/test_sql_retriever_integration.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py tldw_Server_API/tests/RAG/test_sql_retriever_integration.py
git commit -m "feat(rag): integrate sql retriever source into unified pipeline"
```

### Task 9: Add SQL fusion weight and tabular-to-document budget controls

**Files:**
- Modify: `tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py`
- Modify: `tldw_Server_API/app/core/Text2SQL/service.py`
- Create: `tldw_Server_API/tests/Text2SQL/test_result_budgeting.py`

**Step 1: Write the failing test**

```python
def test_sql_rows_are_truncated_when_budget_exceeded():
    # large mock rows should be capped and annotated
    ...
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Text2SQL/test_result_budgeting.py -v`
Expected: FAIL due missing budget enforcement.

**Step 3: Write minimal implementation**

```python
# service.py
MAX_CELL_CHARS = 512
MAX_ROWS = 500

# clamp/trim rows and add truncation metadata
```

```python
# database_retrievers.py weighted fusion defaults
weights = {
    ...,
    DataSource.SQL: 0.9,
}
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Text2SQL/test_result_budgeting.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Text2SQL/service.py tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py tldw_Server_API/tests/Text2SQL/test_result_budgeting.py
git commit -m "feat(text2sql): enforce tabular result budgets and sql fusion weight"
```

### Task 10: Add RBAC permission and connector ACL enforcement

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/permissions.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/text2sql.py`
- Create: `tldw_Server_API/tests/Security/test_text2sql_rbac_and_acl.py`

**Step 1: Write the failing test**

```python
def test_text2sql_requires_sql_read_permission(test_client):
    r = test_client.post("/api/v1/text2sql/query", json={"query": "q", "target_id": "media_db"})
    assert r.status_code in (401, 403)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Security/test_text2sql_rbac_and_acl.py -v`
Expected: FAIL because endpoint not permission-gated correctly.

**Step 3: Write minimal implementation**

```python
# permissions.py
SQL_READ = "sql.read"
```

```python
# text2sql.py dependencies
dependencies=[Depends(check_rate_limit), Depends(require_permissions(SQL_READ))]
```

Add ACL check in endpoint/service before execution:
```python
if not connector_acl_allows(current_user, request.target_id):
    raise HTTPException(status_code=403, detail="unauthorized_target")
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Security/test_text2sql_rbac_and_acl.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/permissions.py tldw_Server_API/app/api/v1/endpoints/text2sql.py tldw_Server_API/tests/Security/test_text2sql_rbac_and_acl.py
git commit -m "feat(security): add sql.read permission and connector ACL checks"
```

### Task 11: Verification, security scan, and docs updates

**Files:**
- Modify: `Docs/API-related/RAG_API_Documentation.md`
- Modify: `Docs/API-related/API_README.md`
- Modify: `CHANGELOG.md`

**Step 1: Write/adjust failing documentation checks (if any)**

```markdown
Add endpoint docs for `/api/v1/text2sql/query` and `sources=["sql"]`.
```

**Step 2: Run focused test suite and verify all pass**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Text2SQL -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG/test_sql_retriever_integration.py -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Security/test_text2sql_rbac_and_acl.py -v`

Expected: PASS.

**Step 3: Run Bandit on touched scope**

Run:
- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Text2SQL tldw_Server_API/app/api/v1/endpoints/text2sql.py tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py -f json -o /tmp/bandit_text2sql.json`

Expected: no new high-severity findings in changed code.

**Step 4: Final smoke check for endpoint contract**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/integration/test_text2sql_endpoint.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add Docs/API-related/RAG_API_Documentation.md Docs/API-related/API_README.md CHANGELOG.md /tmp/bandit_text2sql.json
git commit -m "docs(text2sql): document endpoint, rag source, and verification artifacts"
```

