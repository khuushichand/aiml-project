import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit


pytestmark = [pytest.mark.integration, pytest.mark.bench]


@pytest.fixture(autouse=True)
def _test_mode(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")


@pytest.fixture()
def client_with_overrides(monkeypatch):
    async def override_user():
        return User(id=1, username="tester", email=None, is_active=True)

    async def _noop():
        return None

    # Disable RBAC to avoid DB
    import tldw_Server_API.app.api.v1.API_Deps.auth_deps as auth_deps
    async def _no_rbac(*args, **kwargs):  # noqa: ARG001
        return None
    monkeypatch.setattr(auth_deps, "enforce_rbac_rate_limit", _no_rbac)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[check_rate_limit] = _noop

    try:
        # Skip if TestClient cannot disable lifespan (older Starlette); avoids startup DB issues in CI
        import inspect as _inspect
        if 'lifespan' not in _inspect.signature(TestClient.__init__).parameters:
            import pytest as _pytest
            _pytest.skip("TestClient lacks 'lifespan' support; skipping ablation benchmark smoke")
        # Disable lifespan to avoid heavy startup (DB, services) and ignore server exceptions
        with TestClient(fastapi_app, raise_server_exceptions=False, lifespan='off') as client:
            yield client
    finally:
        fastapi_app.dependency_overrides.clear()


def test_rag_benchmarks_ablate_latency_and_accuracy(client_with_overrides, monkeypatch):
    client = client_with_overrides

    # Patch retrievers for both unified and agentic paths
    from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource

    content = (
        "# Residuals\nResidual connections help gradient flow in deep networks.\n\n"
        "# Results\nWe ran 42 experiments and observed consistent results."
    )

    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass
        async def retrieve(self, *args, **kwargs):
            return [Document(id="bm1", content=content, metadata={"title": "Paper"}, source=DataSource.MEDIA_DB, score=0.9)]

    import tldw_Server_API.app.core.RAG.rag_service.agentic_chunker as ac
    import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as up
    monkeypatch.setattr(ac, "MultiDatabaseRetriever", FakeRetriever)
    monkeypatch.setattr(up, "MultiDatabaseRetriever", FakeRetriever)

    # Patch generator to return determinstic answer referencing both sentences and the number
    class FakeAnswerGenerator:
        def __init__(self, *args, **kwargs):
            pass
        async def generate(self, *, query: str, context: str, prompt_template=None, max_tokens=None, temperature=None):  # noqa: ARG002
            return {"answer": "Residual connections help gradient flow. We ran 42 experiments."}

    import tldw_Server_API.app.core.RAG.rag_service.generation as gen_mod
    monkeypatch.setattr(gen_mod, "AnswerGenerator", FakeAnswerGenerator, raising=False)
    # unified_pipeline imported AnswerGenerator at module level; patch there too
    monkeypatch.setattr(up, "AnswerGenerator", FakeAnswerGenerator, raising=False)

    # Run ablations with answer generation
    payload = {
        "query": "What do residual connections do and how many experiments?",
        "top_k": 5,
        "search_mode": "fts",
        "with_answer": True,
        "reranking_strategy": "none"
    }
    resp = client.post("/api/v1/rag/ablate", json=payload)
    assert resp.status_code == 200, resp.text
    out = resp.json()
    runs = out.get("runs") or []
    assert len(runs) == 4

    # Collect simple benchmark stats: total_time and citation coverage (accuracy proxy)
    stats = {}
    for r in runs:
        label = r.get("label")
        res = r.get("result") or {}
        md = res.get("metadata") or {}
        total_time = float(res.get("total_time", 0.0))
        coverage = float((md.get("hard_citations") or {}).get("coverage", 0.0)) if md.get("hard_citations") else 0.0
        stats[label] = {"time": total_time, "coverage": coverage}

    # All variants should return quickly in test env and have non-negative coverage
    assert all(v["time"] >= 0.0 for v in stats.values())
    assert all(0.0 <= v["coverage"] <= 1.0 for v in stats.values())

    # Ensure agentic variants advertise strategy
    for r in runs:
        if r.get("label") in ("agentic", "agentic_strict"):
            assert r["result"].get("metadata", {}).get("strategy") == "agentic"
