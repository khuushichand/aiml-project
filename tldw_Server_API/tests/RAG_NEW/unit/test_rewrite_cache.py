from pathlib import Path

import pytest

from tldw_Server_API.app.core.RAG.rag_service.rewrite_cache import (
    RewriteCache,
    _is_relative_to,
)

pytestmark = pytest.mark.unit


def test_rewrite_cache_put_get(tmp_path, monkeypatch):


    p = tmp_path / "rc.jsonl"
    monkeypatch.setenv("RAG_REWRITE_CACHE_PATH", str(p))
    rc = RewriteCache()

    q = "What is CUDA?"
    rewrites = ["compute unified device architecture", "nvidia cuda"]
    rc.put(q, rewrites, intent="FACTUAL", corpus="ml")

    out = rc.get(q, intent="FACTUAL", corpus="ml")
    assert out is not None
    assert any("compute unified" in r for r in out)


def test_rewrite_cache_user_id_path_is_sandboxed(tmp_path, monkeypatch):


    monkeypatch.chdir(tmp_path)
    rc = RewriteCache(user_id="../evil")
    base_dir = (tmp_path / "Databases" / "user_databases").resolve()
    cache_path = Path(rc.path).resolve()
    assert _is_relative_to(cache_path, base_dir)
    assert cache_path.name == "rewrite_cache.jsonl"


def test_rewrite_cache_user_id_preserves_safe_segment(tmp_path, monkeypatch):


    monkeypatch.chdir(tmp_path)
    rc = RewriteCache(user_id="user_123")
    cache_path = Path(rc.path).resolve()
    assert cache_path.parent.name == "Rewrite_Cache"
    assert cache_path.parent.parent.name == "user_123"


def test_rewrite_cache_user_id_with_special_chars(tmp_path, monkeypatch):


    monkeypatch.chdir(tmp_path)
    rc = RewriteCache(user_id="user_abc-123")
    cache_path = Path(rc.path).resolve()
    assert cache_path.parent.parent.name == "user_abc-123"


def test_rewrite_cache_unsafe_user_id_is_hashed(tmp_path, monkeypatch):


    monkeypatch.chdir(tmp_path)
    rc = RewriteCache(user_id="../../etc/passwd")
    cache_path = Path(rc.path).resolve()
    assert cache_path.parent.parent.name.startswith("user_")
    assert cache_path.parent.parent.name != "../../etc/passwd"
    rc2 = RewriteCache(user_id="../../etc/passwd")
    cache_path2 = Path(rc2.path).resolve()
    assert cache_path.parent.parent.name == cache_path2.parent.parent.name
