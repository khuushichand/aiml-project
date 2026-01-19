import os
import time
from pathlib import Path
from uuid import uuid4

import pytest


def _api_key() -> str:
    return os.environ.get("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")


def _auth_headers() -> dict:
    return {"X-API-KEY": _api_key()}


def _require_ok(resp, label: str) -> None:
    if not resp.ok:
        raise AssertionError(f"{label} failed: status={resp.status} body={resp.text()}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _sample_doc_path() -> Path:
    return _repo_root() / "tldw_Server_API/tests/Media_Ingestion_Modification/test_media/sample.txt"


def _ingest_sample_document(page, headers, suffix: str) -> int:
    sample_path = _sample_doc_path()
    ingest_resp = page.request.post(
        "/api/v1/media/add",
        headers=headers,
        multipart={
            "media_type": "document",
            "title": f"E2E RAG doc {suffix}",
            "perform_analysis": "false",
            "files": {
                "name": sample_path.name,
                "mimeType": "text/plain",
                "buffer": sample_path.read_bytes(),
            },
        },
    )
    _require_ok(ingest_resp, "ingest document")
    ingest_payload = ingest_resp.json()
    results = ingest_payload.get("results", [])
    assert results, "Expected ingest results"
    media_id = next((item.get("db_id") for item in results if item.get("db_id")), None)
    assert media_id is not None
    return int(media_id)


@pytest.mark.e2e
def test_rag_pipeline_local_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    media_id = _ingest_sample_document(page, headers, suffix)

    embed_resp = page.request.post(
        f"/api/v1/media/{media_id}/embeddings",
        headers=headers,
        json={},
    )
    _require_ok(embed_resp, "create embeddings job")
    embed_payload = embed_resp.json()
    job_id = embed_payload.get("job_id")
    assert job_id

    job_status_resp = page.request.get(
        f"/api/v1/media/embeddings/jobs/{job_id}",
        headers=headers,
    )
    _require_ok(job_status_resp, "get embeddings job")

    time.sleep(0.5)

    rag_resp = page.request.post(
        "/api/v1/rag/search",
        headers=headers,
        json={
            "query": "tldw text processing endpoint",
            "sources": ["media_db"],
            "search_mode": "fts",
            "enable_reranking": True,
            "reranking_strategy": "flashrank",
            "enable_generation": False,
            "top_k": 5,
        },
    )
    _require_ok(rag_resp, "rag search")
    rag_payload = rag_resp.json()
    documents = rag_payload.get("documents", [])
    assert documents, "Expected RAG documents"
    timings = rag_payload.get("timings", {})
    assert "reranking" in timings

    delete_resp = page.request.delete(f"/api/v1/media/{media_id}", headers=headers)
    assert delete_resp.status == 204


@pytest.mark.e2e
def test_rag_pipeline_external_embedding_workflow(page, server_url):
    if os.getenv("TLDW_E2E_EXTERNAL_RAG", "").lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("External RAG flow disabled; set TLDW_E2E_EXTERNAL_RAG=1 to enable.")
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set; skipping external embeddings flow.")

    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    media_id = _ingest_sample_document(page, headers, suffix)

    model_name = os.getenv("TLDW_E2E_EMBEDDINGS_MODEL", "text-embedding-3-small")
    embed_resp = page.request.post(
        "/api/v1/embeddings",
        headers=headers,
        json={
            "model": model_name,
            "input": f"E2E external embeddings {suffix}",
        },
    )
    _require_ok(embed_resp, "create external embeddings")
    embed_payload = embed_resp.json()
    assert embed_payload.get("data"), "Expected embeddings data"

    rag_resp = page.request.post(
        "/api/v1/rag/search",
        headers=headers,
        json={
            "query": "tldw text processing endpoint",
            "sources": ["media_db"],
            "search_mode": "fts",
            "enable_reranking": True,
            "reranking_strategy": "flashrank",
            "enable_generation": False,
            "top_k": 5,
        },
    )
    _require_ok(rag_resp, "rag search (external)")
    rag_payload = rag_resp.json()
    documents = rag_payload.get("documents", [])
    assert documents, "Expected RAG documents"

    delete_resp = page.request.delete(f"/api/v1/media/{media_id}", headers=headers)
    assert delete_resp.status == 204
