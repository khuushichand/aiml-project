"""Unit tests for media module helpers and retrieval behaviours."""

from datetime import datetime
from types import MethodType, SimpleNamespace
from typing import Any, Dict, List

import pytest

from tldw_Server_API.app.core.MCP_unified.modules.implementations.media_module import MediaModule
from tldw_Server_API.app.core.MCP_unified.modules.base import ModuleConfig


class FakeMediaDB:
    def __init__(self) -> None:
        # Prepare deterministic 5 chunks of 10 chars each
        self._chunks = [
            {"chunk_index": 0, "uuid": "u0", "chunk_text": "A" * 10},
            {"chunk_index": 1, "uuid": "u1", "chunk_text": "B" * 10},
            {"chunk_index": 2, "uuid": "u2", "chunk_text": "C" * 10},
            {"chunk_index": 3, "uuid": "u3", "chunk_text": "D" * 10},
            {"chunk_index": 4, "uuid": "u4", "chunk_text": "E" * 10},
        ]

    def get_media_by_id(self, media_id: int, include_deleted: bool = False, include_trash: bool = False) -> Dict[str, Any]:
        full = "".join(c["chunk_text"] for c in self._chunks)
        return {
            "id": media_id,
            "title": "T",
            "content": full,
            "type": "html",
            "url": None,
            "ingestion_date": None,
            "last_modified": None,
            "version": 1,
        }

    def has_unvectorized_chunks(self, media_id: int) -> bool:
        return True

    def get_unvectorized_chunk_index_by_uuid(self, media_id: int, chunk_uuid: str):
        for c in self._chunks:
            if c["uuid"] == chunk_uuid:
                return c["chunk_index"]
        return None

    def get_unvectorized_anchor_index_for_offset(self, media_id: int, approx_offset: int):
        # Map 10-char chunks
        return max(0, min(4, approx_offset // 10))

    def get_unvectorized_chunks_in_range(self, media_id: int, start_index: int, end_index: int) -> List[Dict[str, Any]]:
        si = max(0, min(start_index, end_index))
        ei = min(max(start_index, end_index), len(self._chunks) - 1)
        return [self._chunks[i] for i in range(si, ei + 1)]


@pytest.mark.asyncio
async def test_media_get_chunk_with_siblings_budget():
    mod = MediaModule(ModuleConfig(name="media"))

    # Monkeypatch per-user DB open to our fake
    mod._open_media_db = lambda ctx: FakeMediaDB()  # type: ignore[attr-defined]

    # Anchor around approx_offset=12 → chunk_index 1, cpt=1 → 10 tokens per chunk
    out = await mod.execute_tool(
        "media.get",
        {
            "media_id": 42,
            "retrieval": {
                "mode": "chunk_with_siblings",
                "max_tokens": 25,  # can fit 2 chunks (10 + 10) and not a third (would be 30)
                "chars_per_token": 1,
                "loc": {"approx_offset": 12},
            },
        },
        context=None,
    )

    assert isinstance(out, dict)
    assert out["meta"]["loc"]["chunk_index"] == 1
    body = out["content"]
    # Greedy expansion adds left(0) then right(2) or vice versa depending on order; our code checks left then right
    # Anchor chunk_index 1 → chunks 1 and 0 can fit within 25 tokens (20 total); third chunk would exceed.
    assert body in ("B" * 10 + "\n\n" + "A" * 10, "A" * 10 + "\n\n" + "B" * 10)
    # Ensure total chars <= 25
    assert len(body.replace("\n", "")) <= 25


class RecordingDB:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def search_media_db(
        self,
        search_query: Any = None,
        search_fields: Any = None,
        media_types: Any = None,
        date_range: Any = None,
        must_have_keywords: Any = None,
        must_not_have_keywords: Any = None,
        sort_by: Any = None,
        media_ids_filter: Any = None,
        page: int = 1,
        results_per_page: int = 20,
        include_trash: bool = False,
        include_deleted: bool = False,
    ):
        self.calls.append(
            {
                "search_query": search_query,
                "media_types": media_types,
                "sort_by": sort_by,
                "page": page,
                "results_per_page": results_per_page,
                "include_trash": include_trash,
                "include_deleted": include_deleted,
            }
        )
        row = {
            "id": len(self.calls),
            "title": f"T{len(self.calls)}",
            "type": "video",
            "ingestion_date": None,
            "last_modified": None,
            "url": None,
        }
        return [row], 5

    def get_distinct_media_types(self):
        return ["video", "pdf"]


@pytest.mark.asyncio
async def test_search_media_cache_respects_filters():
    mod = MediaModule(ModuleConfig(name="media"))
    mod.db = RecordingDB()
    mod._media_cache = {}
    mod._cache_ttl = 300

    await mod._search_media(query="foo", search_type="keyword", limit=5, offset=0, media_types=["video"])
    assert len(mod.db.calls) == 1

    await mod._search_media(query="foo", search_type="keyword", limit=5, offset=0, media_types=["audio"])
    assert len(mod.db.calls) == 2  # different filter should bypass cache

    await mod._search_media(query="foo", search_type="keyword", limit=5, offset=0, media_types=["audio"])
    assert len(mod.db.calls) == 2  # cached response reused


def test_clear_media_cache_flushes_all_entries():
    mod = MediaModule(ModuleConfig(name="media"))
    mod._media_cache = {"k": {"time": datetime.utcnow(), "data": {}}}
    mod._clear_media_cache(1)
    assert mod._media_cache == {}


@pytest.mark.asyncio
async def test_media_resources_use_search_api():
    mod = MediaModule(ModuleConfig(name="media"))
    mod.db = RecordingDB()

    recent = await mod.read_resource("media://recent")
    popular = await mod.read_resource("media://popular")
    assert len(mod.db.calls) == 2
    assert mod.db.calls[0]["sort_by"] == "last_modified_desc"
    assert mod.db.calls[1]["sort_by"] == "date_desc"
    assert recent["items"][0]["title"].startswith("T")
    types_resource = await mod.read_resource("media://types")
    assert "video" in types_resource["items"]
    assert "pdf" in types_resource["items"]


@pytest.mark.asyncio
async def test_search_media_semantic_path(monkeypatch):
    mod = MediaModule(ModuleConfig(name="media"))
    mod.db = RecordingDB()
    mod._media_cache = {}
    mod._semantic_retrievers = {}
    mod._cache_ttl = 300

    class StubRetriever:
        def __init__(self) -> None:
            self.config = SimpleNamespace(max_results=0)

        async def _retrieve_vector(self, query: str, **_kwargs):
            return [
                SimpleNamespace(
                    id="42",
                    content="hello world",
                    metadata={"title": "Doc", "media_type": "text", "url": "u"},
                    score=0.9,
                )
            ]

    mod._get_semantic_retriever = MethodType(lambda self, db, ctx: StubRetriever(), mod)  # type: ignore
    result = await mod._search_media(query="hello", search_type="semantic", limit=5, offset=0)
    assert result["count"] == 1
    assert result["results"][0]["id"] == 42
    assert result["results"][0]["semantic_score"] == pytest.approx(0.9)
