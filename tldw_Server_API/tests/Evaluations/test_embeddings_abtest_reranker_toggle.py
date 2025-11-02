import os
import json
import asyncio
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


@pytest.mark.integration
def test_reranker_toggle_controls_reranking(monkeypatch):
    # Force admin-only off to avoid admin check failures in CI
    monkeypatch.setenv('EVALS_HEAVY_ADMIN_ONLY', 'false')
    # Enable test-mode synthetic embeddings
    monkeypatch.setenv('TESTING', 'true')

    client = TestClient(app)

    # Minimal AB test config with two arms (same provider/model for stability)
    config = {
        "arms": [
            {"provider": "openai", "model": "text-embedding-3-small"},
        ],
        "media_ids": [],
        "chunking": {"method": "words", "size": 1000, "overlap": 200},
        "retrieval": {"k": 3, "search_mode": "vector", "re_ranker": {"provider": "flashrank", "model": "default"}},
        "queries": [{"text": "alpha"}, {"text": "beta"}],
        "reuse_existing": True
    }

    # Create test
    resp = client.post("/api/v1/evaluations/embeddings/abtest", json={"name": "toggle-test", "config": config})
    assert resp.status_code == 200
    test_id = resp.json()["test_id"]

    # Run without reranker
    no_rr_cfg = config.copy()
    no_rr_cfg["retrieval"] = dict(config["retrieval"], apply_reranker=False)
    resp = client.post(f"/api/v1/evaluations/embeddings/abtest/{test_id}/run", json={"name": "toggle-test", "config": no_rr_cfg})
    assert resp.status_code == 200

    # Poll summary
    def _get_status():
        r = client.get(f"/api/v1/evaluations/embeddings/abtest/{test_id}")
        assert r.status_code == 200
        return r.json()

    # Wait until completed
    for _ in range(50):
        s = _get_status()
        if s.get('status') == 'completed':
            break
        asyncio.sleep(0.1)

    # Export JSON and capture baseline results
    r = client.get(f"/api/v1/evaluations/embeddings/abtest/{test_id}/export", params={"format": "json"})
    assert r.status_code == 200
    baseline = r.json()

    # Run again with reranker ON; this will create new results appended in DB
    rr_cfg = config.copy()
    rr_cfg["retrieval"] = dict(config["retrieval"], apply_reranker=True)
    resp = client.post(f"/api/v1/evaluations/embeddings/abtest/{test_id}/run", json={"name": "toggle-test", "config": rr_cfg})
    assert resp.status_code == 200

    for _ in range(50):
        s = _get_status()
        if s.get('status') == 'completed':
            break
        asyncio.sleep(0.1)

    r = client.get(f"/api/v1/evaluations/embeddings/abtest/{test_id}/export", params={"format": "json"})
    assert r.status_code == 200
    after = r.json()

    # Heuristic check: when reranker applied, expect to see some rerank_scores present in later rows
    def _has_rerank(rows):
        for row in rows.get('results', []):
            try:
                scores = json.loads(row.get('rerank_scores') or 'null')
                if scores:
                    return True
            except Exception:
                pass
        return False

    assert not _has_rerank(baseline), "Baseline without reranker should not have rerank_scores"
    assert _has_rerank(after), "With apply_reranker=true, rerank_scores should be present"
