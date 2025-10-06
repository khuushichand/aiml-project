import os
import importlib.machinery
import pytest
from httpx import AsyncClient, ASGITransport
import sys, types

# Stub heavy modules before importing the full app
if 'torch' not in sys.modules:
    _fake_torch = types.ModuleType('torch')
    _fake_torch.__spec__ = importlib.machinery.ModuleSpec('torch', loader=None)
    _fake_torch.Tensor = object  # Minimal attribute used by safetensors
    _fake_torch.nn = types.SimpleNamespace(Module=object)
    sys.modules['torch'] = _fake_torch
if 'dill' not in sys.modules:
    _fake_dill = types.ModuleType('dill')
    _fake_dill.__spec__ = importlib.machinery.ModuleSpec('dill', loader=None)
    sys.modules['dill'] = _fake_dill
if 'faster_whisper' not in sys.modules:
    _fake_fw = types.ModuleType('faster_whisper')
    _fake_fw.__spec__ = importlib.machinery.ModuleSpec('faster_whisper', loader=None)

    class _StubWhisperModel:  # Minimal stub used in tests
        def __init__(self, *args, **kwargs):
            pass

    _fake_fw.WhisperModel = _StubWhisperModel
    _fake_fw.BatchedInferencePipeline = _StubWhisperModel
    sys.modules['faster_whisper'] = _fake_fw
if 'transformers' not in sys.modules:
    _fake_tf = types.ModuleType('transformers')
    _fake_tf.__spec__ = importlib.machinery.ModuleSpec('transformers', loader=None)

    class _StubProcessor:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

    class _StubModel:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

    _fake_tf.AutoProcessor = _StubProcessor
    _fake_tf.Qwen2AudioForConditionalGeneration = _StubModel
    sys.modules['transformers'] = _fake_tf
if 'safetensors' not in sys.modules:
    _fake_st = types.ModuleType('safetensors')
    _fake_st.__spec__ = importlib.machinery.ModuleSpec('safetensors', loader=None)
    sys.modules['safetensors'] = _fake_st
if 'safetensors.torch' not in sys.modules:
    _fake_st_torch = types.ModuleType('safetensors.torch')
    _fake_st_torch.__spec__ = importlib.machinery.ModuleSpec('safetensors.torch', loader=None)

    def _noop(*args, **kwargs):
        return None

    _fake_st_torch.save_file = _noop
    sys.modules['safetensors.torch'] = _fake_st_torch


def _auth_headers():
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings

    key = get_settings().SINGLE_USER_API_KEY or os.getenv("SINGLE_USER_API_KEY", "test-api-key-12345")
    return {"X-API-KEY": key}


class _FakeConn:
    def execute(self, *args, **kwargs):
        return None

    def commit(self):
        return None


class _FakeDB:
    def __init__(self):
        self.last_filters = None
        self.created_versions = []
        self.add_calls = []

    # Context manager for transaction()
    def transaction(self):
        class _Tx:
            def __enter__(self_inner):
                return _FakeConn()

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        return _Tx()

    def get_connection(self):
        return _FakeConn()

    def search_by_safe_metadata(self, filters=None, match_all=True, page=1, per_page=20, group_by_media=True):
        self.last_filters = filters
        return [], 0

    def create_document_version(self, media_id, content, prompt, analysis_content, safe_metadata):
        self.created_versions.append({
            "media_id": media_id,
            "content": content,
            "prompt": prompt,
            "analysis_content": analysis_content,
            "safe_metadata": safe_metadata,
        })
        return {"version_number": 2, "uuid": "test-uuid"}

    def add_media_with_keywords(self, **kwargs):
        self.add_calls.append(kwargs)
        return 42, "uuid-42", "ok"


@pytest.mark.asyncio
async def test_metadata_search_normalizes_pmcid(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import (
        get_media_db_for_user,
        try_get_media_db_for_user,
    )

    fake_db = _FakeDB()
    async def _override_db():
        return fake_db

    async def _override_db_optional():
        return fake_db

    app.dependency_overrides[get_media_db_for_user] = _override_db
    app.dependency_overrides[try_get_media_db_for_user] = _override_db_optional

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=_auth_headers()) as client:
        r = await client.get(
            "/api/v1/media/metadata-search",
            params={"field": "pmcid", "op": "eq", "value": "PMC12345"},
        )
        assert r.status_code == 200
        # Ensure normalization stripped PMC prefix
        assert fake_db.last_filters and fake_db.last_filters[0]["value"] == "12345"

    app.dependency_overrides.pop(get_media_db_for_user, None)
    app.dependency_overrides.pop(try_get_media_db_for_user, None)


@pytest.mark.asyncio
async def test_by_identifier_normalizes_pmcid(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import (
        get_media_db_for_user,
        try_get_media_db_for_user,
    )

    fake_db = _FakeDB()
    async def _override_db():
        return fake_db

    async def _override_db_optional():
        return fake_db

    app.dependency_overrides[get_media_db_for_user] = _override_db
    app.dependency_overrides[try_get_media_db_for_user] = _override_db_optional

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=_auth_headers()) as client:
        r = await client.get(
            "/api/v1/media/by-identifier",
            params={"pmcid": "PMC9999"},
        )
        assert r.status_code == 200
        assert fake_db.last_filters and fake_db.last_filters[0]["value"] == "9999"

    app.dependency_overrides.pop(get_media_db_for_user, None)
    app.dependency_overrides.pop(try_get_media_db_for_user, None)


@pytest.mark.asyncio
async def test_patch_metadata_invalid_doi_returns_400(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import (
        get_media_db_for_user,
        try_get_media_db_for_user,
    )

    # Stub get_document_version to avoid DB lookups and ensure early validation is exercised
    import tldw_Server_API.app.api.v1.endpoints.media as media_ep

    def _fake_get_document_version(db_instance, media_id, version_number=None, include_content=True):
        return {"id": 1, "media_id": media_id, "version_number": 1, "content": "x", "prompt": None, "analysis_content": None, "safe_metadata": "{}"}

    monkeypatch.setattr(media_ep, "get_document_version", _fake_get_document_version)

    fake_db = _FakeDB()
    async def _override_db():
        return fake_db

    async def _override_db_optional():
        return fake_db

    app.dependency_overrides[get_media_db_for_user] = _override_db
    app.dependency_overrides[try_get_media_db_for_user] = _override_db_optional

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=_auth_headers()) as client:
        r = await client.patch(
            "/api/v1/media/123/metadata",
            json={"safe_metadata": {"doi": "not-a-doi"}, "merge": True, "new_version": False},
        )
        assert r.status_code == 400

    app.dependency_overrides.pop(get_media_db_for_user, None)
    app.dependency_overrides.pop(try_get_media_db_for_user, None)


@pytest.mark.asyncio
async def test_put_version_metadata_invalid_pmcid_returns_400(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import (
        get_media_db_for_user,
        try_get_media_db_for_user,
    )

    import tldw_Server_API.app.api.v1.endpoints.media as media_ep

    def _fake_get_document_version(db_instance, media_id, version_number=None, include_content=True):
        return {"id": 2, "media_id": media_id, "version_number": 2, "safe_metadata": "{}"}

    monkeypatch.setattr(media_ep, "get_document_version", _fake_get_document_version)

    fake_db = _FakeDB()
    async def _override_db():
        return fake_db

    async def _override_db_optional():
        return fake_db

    app.dependency_overrides[get_media_db_for_user] = _override_db
    app.dependency_overrides[try_get_media_db_for_user] = _override_db_optional

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=_auth_headers()) as client:
        r = await client.put(
            "/api/v1/media/123/versions/2/metadata",
            json={"safe_metadata": {"pmcid": "PMCX123"}, "merge": True},
        )
        assert r.status_code == 400

    app.dependency_overrides.pop(get_media_db_for_user, None)
    app.dependency_overrides.pop(try_get_media_db_for_user, None)


@pytest.mark.asyncio
async def test_advanced_version_upsert_invalid_pmid_returns_400(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import (
        get_media_db_for_user,
        try_get_media_db_for_user,
    )

    import tldw_Server_API.app.api.v1.endpoints.media as media_ep

    def _fake_get_document_version(db_instance, media_id, version_number=None, include_content=True):
        return {"id": 1, "media_id": media_id, "version_number": 1, "content": "x", "prompt": None, "analysis_content": None, "safe_metadata": "{}"}

    monkeypatch.setattr(media_ep, "get_document_version", _fake_get_document_version)

    fake_db = _FakeDB()
    async def _override_db():
        return fake_db

    async def _override_db_optional():
        return fake_db

    app.dependency_overrides[get_media_db_for_user] = _override_db
    app.dependency_overrides[try_get_media_db_for_user] = _override_db_optional

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=_auth_headers()) as client:
        r = await client.post(
            "/api/v1/media/123/versions/advanced",
            json={"safe_metadata": {"pmid": "abc"}, "new_version": True},
        )
        assert r.status_code == 400

    app.dependency_overrides.pop(get_media_db_for_user, None)
    app.dependency_overrides.pop(try_get_media_db_for_user, None)


@pytest.mark.asyncio
async def test_pubmed_ingest_normalizes_pmcid_in_saved_metadata(monkeypatch):
    from tldw_Server_API.app.main import app
    from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import (
        get_media_db_for_user,
        try_get_media_db_for_user,
    )

    fake_db = _FakeDB()
    async def _override_db():
        return fake_db

    async def _override_db_optional():
        return fake_db

    app.dependency_overrides[get_media_db_for_user] = _override_db
    app.dependency_overrides[try_get_media_db_for_user] = _override_db_optional

    # Stub PubMed meta and PMC PDF download
    from tldw_Server_API.app.core.Third_Party import PubMed as _Pub
    from tldw_Server_API.app.core.Third_Party import PMC_OA as _OA

    def _fake_pubmed_by_id(pmid):
        return {
            "pmid": pmid,
            "pmcid": "PMC123",
            "title": "Test",
            "authors": [{"name": "A"}],
            "journal": "J",
            "pub_date": "2020",
            "externalIds": {"DOI": "10.1000/xyz"},
            "pdf_url": None,
            "pmc_url": None,
        }, None

    def _fake_download_pmc_pdf(pmcid):
        return b"%PDF-1.5\n...", "paper.pdf", None

    async def _fake_process_pdf_task(**kwargs):
        return {"status": "Success", "content": "text", "summary": "s"}

    monkeypatch.setattr(_Pub, "get_pubmed_by_id", _fake_pubmed_by_id)
    monkeypatch.setattr(_OA, "download_pmc_pdf", _fake_download_pmc_pdf)

    import tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib as _PDF
    monkeypatch.setattr(_PDF, "process_pdf_task", _fake_process_pdf_task)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=_auth_headers()) as client:
        r = await client.post(
            "/api/v1/paper-search/pubmed/ingest",
            params={"pmid": "123456"},
        )
        assert r.status_code == 200
        # Ensure saved safe_metadata JSON has normalized pmcid without prefix
        assert fake_db.add_calls, "DB add not invoked"
        smj = fake_db.add_calls[0].get("safe_metadata")
        assert smj and '"pmcid": "123"' in smj

    app.dependency_overrides.pop(get_media_db_for_user, None)
    app.dependency_overrides.pop(try_get_media_db_for_user, None)
