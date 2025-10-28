import os
import sys
import types
import asyncio
import pytest
from pathlib import Path

# Avoid Matplotlib writing to user home or outside the repo.
# Anchor cache under the package root regardless of current working directory.
_pkg_root = Path(__file__).resolve().parents[2]  # .../tldw_Server_API
_cache_dir = str(_pkg_root / '.mplcache')
os.makedirs(_cache_dir, exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', _cache_dir)

# Stub heavy config module before importing the compactor
class _StubSettings:
    def get(self, k, default=None):
        return default

_stub_config_mod = types.ModuleType("config_stub")
setattr(_stub_config_mod, "settings", _StubSettings())
sys.modules.setdefault('tldw_Server_API.app.core.config', _stub_config_mod)

from tldw_Server_API.app.core.Embeddings.services import vector_compactor as vc


class _FakeCollection:
    def __init__(self, name):
        self.name = name
        self.deleted = []

    def delete(self, where=None, ids=None):
        if where:
            self.deleted.append(where)


_created_mgrs = []


class _FakeMgr:
    def __init__(self, user_id: str, user_embedding_config):
        self.user_id = user_id
        self._collections = {}
        _created_mgrs.append(self)

    def get_or_create_collection(self, name: str):
        if name not in self._collections:
            self._collections[name] = _FakeCollection(name)
        return self._collections[name]

    def close(self):
        return None


@pytest.mark.unit
def test_compact_once_deletes_vectors(monkeypatch):
    # Fake list of soft-deleted media ids
    async def _fake_ids(dbp):
        return [5, 7]
    monkeypatch.setattr(vc, "_get_media_ids_marked_deleted", _fake_ids, raising=True)

    # Patch ChromaDB_Library import to avoid heavy imports
    import types as _types
    # Insert a proper module object into sys.modules for import compatibility
    _stub_mod = _types.ModuleType("ChromaDB_Library_stub")
    setattr(_stub_mod, "ChromaDBManager", _FakeMgr)
    sys.modules['tldw_Server_API.app.core.Embeddings.ChromaDB_Library'] = _stub_mod

    touched = asyncio.run(vc.compact_once("u"))
    assert touched == 2

    # Validate that deletes were called with media_id where filters on any created manager
    assert len(_created_mgrs) >= 1
    seen = []
    for mgr in _created_mgrs:
        c1 = mgr.get_or_create_collection("user_u_media_5")
        c2 = mgr.get_or_create_collection("user_u_media_7")
        if {"media_id": "5"} in getattr(c1, "deleted", []):
            seen.append(5)
        if {"media_id": "7"} in getattr(c2, "deleted", []):
            seen.append(7)
    assert 5 in seen and 7 in seen
