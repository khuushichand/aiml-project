import configparser
import importlib

import pytest

from tldw_Server_API.app.core.DB_Management import DB_Manager
from tldw_Server_API.app.core.DB_Management import Users_DB
from tldw_Server_API.app.core.DB_Management import Media_DB_v2 as legacy_media_db
from tldw_Server_API.app.api.v1.endpoints import research
from tldw_Server_API.app.api.v1.API_Deps import DB_Deps as media_db_deps
from tldw_Server_API.app.api.v1.endpoints.media import document_insights
from tldw_Server_API.app.api.v1.endpoints.media import document_references
from tldw_Server_API.app.api.v1.endpoints.media import item as media_item
from tldw_Server_API.app.api.v1.endpoints.media import navigation as media_navigation
from tldw_Server_API.app.api.v1.utils import http_errors
from tldw_Server_API.app.core.Claims_Extraction import (
    claims_notifications,
    claims_rebuild_service,
    claims_service,
    claims_utils,
)
from tldw_Server_API.app.core.Evaluations import embeddings_abtest_jobs_worker
from tldw_Server_API.app.core.Embeddings.services import (
    jobs_worker as embeddings_jobs_worker,
    vector_compactor,
)
from tldw_Server_API.app.core.Embeddings import ChromaDB_Library
from tldw_Server_API.app.core.Chunking import template_initialization
from tldw_Server_API.app.core.Ingestion_Media_Processing import visual_ingestion
from tldw_Server_API.app.core.TTS import tts_jobs_worker
from tldw_Server_API.app.core.Workflows.adapters.knowledge import crud as knowledge_crud
from tldw_Server_API.app.core.Workflows.adapters.media import ingest as workflow_media_ingest
from tldw_Server_API.app.core.Ingestion_Media_Processing.Books import Book_Processing_Lib
from tldw_Server_API.app.core.Ingestion_Media_Processing import XML_Ingestion_Lib
from tldw_Server_API.app.core.Ingestion_Media_Processing.MediaWiki import Media_Wiki
from tldw_Server_API.app.core.Data_Tables import jobs_worker as data_tables_jobs_worker
from tldw_Server_API.app.core.RAG.rag_service import unified_pipeline
from tldw_Server_API.app.services import ingestion_sources_worker
from tldw_Server_API.app.core.MCP_unified.modules.implementations import quizzes_module
from tldw_Server_API.app.core.MCP_unified.modules.implementations import slides_module
from tldw_Server_API.app.core.Web_Scraping import Article_Extractor_Lib
from tldw_Server_API.app.core.Watchlists import pipeline as watchlists_pipeline
from tldw_Server_API.app.core.DB_Management.media_db import api as media_db_api
from tldw_Server_API.app.core.DB_Management.media_db import errors as media_db_errors
from tldw_Server_API.app.services import media_files_cleanup_service
from tldw_Server_API.app.services import document_processing_service
from tldw_Server_API.app.services import claims_alerts_scheduler
from tldw_Server_API.app.services import claims_review_metrics_scheduler
from tldw_Server_API.app.services import connectors_worker
from tldw_Server_API.app.services import audiobook_jobs_worker
from tldw_Server_API.app.services import enhanced_web_scraping_service
from tldw_Server_API.app.services import media_ingest_jobs_worker
from tldw_Server_API.app.services import outputs_purge_scheduler
from tldw_Server_API.app.services import storage_cleanup_service
from tldw_Server_API.app.services import tts_history_cleanup_service
from tldw_Server_API.app.services import web_scraping_service


def test_media_db_api_create_media_database_uses_runtime_factory(monkeypatch):
    captured = {}

    def _fake_runtime_create_media_database(client_id, **kwargs):
        captured["client_id"] = client_id
        captured.update(kwargs)
        return "db-instance"

    cfg = configparser.ConfigParser()
    monkeypatch.setattr(
        media_db_api,
        "runtime_create_media_database",
        _fake_runtime_create_media_database,
        raising=False,
    )
    monkeypatch.setattr(DB_Manager, "single_user_db_path", "/tmp/api-media.db", raising=False)
    monkeypatch.setattr(DB_Manager, "single_user_config", cfg, raising=False)
    monkeypatch.setattr(DB_Manager, "_POSTGRES_CONTENT_MODE", True, raising=False)
    monkeypatch.setattr(DB_Manager, "_ensure_content_backend_loaded", lambda: "backend-sentinel", raising=False)

    result = media_db_api.create_media_database(
        "client-api",
        db_path="/tmp/override.db",
    )

    assert result == "db-instance"
    assert captured["client_id"] == "client-api"
    assert captured["db_path"] == "/tmp/override.db"
    assert captured["runtime"].default_db_path == "/tmp/api-media.db"
    assert captured["runtime"].default_config is cfg
    assert captured["runtime"].postgres_content_mode is True


def test_db_deps_imports_errors_from_media_db_errors_and_not_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "DatabaseError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "SchemaError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_db_deps)

    assert module.DatabaseError is media_db_errors.DatabaseError
    assert module.SchemaError is media_db_errors.SchemaError
    assert module.MediaDatabase is not legacy_media_db.MediaDatabase


def test_http_errors_imports_db_errors_from_media_db_errors(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "ConflictError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "DatabaseError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "InputError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "SchemaError", object(), raising=False)

    module = importlib.reload(http_errors)

    assert module.ConflictError is media_db_errors.ConflictError
    assert module.DatabaseError is media_db_errors.DatabaseError
    assert module.InputError is media_db_errors.InputError
    assert module.SchemaError is media_db_errors.SchemaError


def test_document_references_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(document_references)

    assert "MediaDatabase" not in module.__dict__


def test_document_insights_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(document_insights)

    assert "MediaDatabase" not in module.__dict__


def test_navigation_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_navigation)

    assert "MediaDatabase" not in module.__dict__


def test_media_item_imports_db_errors_from_media_db_errors_and_not_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "ConflictError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "DatabaseError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "InputError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_item)

    assert module.ConflictError is media_db_errors.ConflictError
    assert module.DatabaseError is media_db_errors.DatabaseError
    assert module.InputError is media_db_errors.InputError
    assert "MediaDatabase" not in module.__dict__


def test_document_processing_service_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(document_processing_service)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_media_ingest_jobs_worker_imports_create_media_database_from_media_db_api():
    module = importlib.reload(media_ingest_jobs_worker)
    assert module.create_media_database is media_db_api.create_media_database


def test_enhanced_web_scraping_service_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(enhanced_web_scraping_service)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_research_endpoint_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(research)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_connectors_worker_imports_create_media_database_from_media_db_api():
    module = importlib.reload(connectors_worker)
    assert module.create_media_database is media_db_api.create_media_database


def test_xml_ingestion_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(XML_Ingestion_Lib)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_ingestion_sources_worker_imports_create_media_database_from_media_db_api():
    module = importlib.reload(ingestion_sources_worker)
    assert module.create_media_database is media_db_api.create_media_database


def test_mediawiki_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(Media_Wiki)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_article_extractor_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(Article_Extractor_Lib)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_book_processing_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(Book_Processing_Lib)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_web_scraping_service_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(web_scraping_service)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_media_files_cleanup_service_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(media_files_cleanup_service)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_storage_cleanup_service_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(storage_cleanup_service)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_outputs_purge_scheduler_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(outputs_purge_scheduler)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_tts_history_cleanup_service_imports_create_media_database_from_media_db_api():
    module = importlib.reload(tts_history_cleanup_service)
    assert module.create_media_database is media_db_api.create_media_database


def test_audiobook_jobs_worker_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(audiobook_jobs_worker)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_slides_module_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(slides_module)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_quizzes_module_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(quizzes_module)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_data_tables_jobs_worker_imports_create_media_database_from_media_db_api():
    module = importlib.reload(data_tables_jobs_worker)
    assert module.create_media_database is media_db_api.create_media_database


def test_claims_notifications_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(claims_notifications)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_claims_service_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(claims_service)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_claims_rebuild_service_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(claims_rebuild_service)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_embeddings_jobs_worker_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(embeddings_jobs_worker)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_vector_compactor_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(vector_compactor)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_chromadb_library_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(ChromaDB_Library)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_template_initialization_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(template_initialization)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_watchlists_pipeline_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(watchlists_pipeline)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_workflow_knowledge_crud_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(knowledge_crud)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_unified_pipeline_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(unified_pipeline)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_workflow_media_ingest_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(workflow_media_ingest)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_visual_ingestion_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(visual_ingestion)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_claims_utils_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(claims_utils)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_claims_alerts_scheduler_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(claims_alerts_scheduler)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_claims_review_metrics_scheduler_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(claims_review_metrics_scheduler)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_embeddings_abtest_jobs_worker_imports_create_media_database_from_media_db_api():
    module = importlib.reload(embeddings_abtest_jobs_worker)
    assert module.create_media_database is media_db_api.create_media_database


def test_tts_jobs_worker_imports_create_media_database_from_media_db_api():
    module = importlib.reload(tts_jobs_worker)
    assert module.create_media_database is media_db_api.create_media_database


def test_media_db_api_managed_media_database_initializes_and_closes(monkeypatch):
    events = []

    class _FakeDb:
        def initialize_db(self):
            events.append("initialize")

        def close_connection(self):
            events.append("close")

    fake_db = _FakeDb()

    def _fake_create_media_database(client_id, **kwargs):
        events.append(("create", client_id, kwargs.get("db_path")))
        return fake_db

    monkeypatch.setattr(media_db_api, "create_media_database", _fake_create_media_database)

    with media_db_api.managed_media_database("managed-client", db_path="/tmp/managed.db") as db:
        assert db is fake_db
        events.append("body")

    assert events == [
        ("create", "managed-client", "/tmp/managed.db"),
        "initialize",
        "body",
        "close",
    ]


def test_media_db_api_managed_media_database_suppresses_selected_lifecycle_errors(monkeypatch):
    events = []

    class _FakeDb:
        def initialize_db(self):
            events.append("initialize")
            raise RuntimeError("init failed")

        def close_connection(self):
            events.append("close")
            raise ValueError("close failed")

    fake_db = _FakeDb()

    monkeypatch.setattr(media_db_api, "create_media_database", lambda *_args, **_kwargs: fake_db)

    with media_db_api.managed_media_database(
        "managed-client",
        suppress_init_exceptions=(RuntimeError,),
        suppress_close_exceptions=(ValueError,),
    ) as db:
        assert db is fake_db
        events.append("body")

    assert events == ["initialize", "body", "close"]


@pytest.mark.asyncio
async def test_users_db_get_user_media_db_uses_media_db_api_factory(monkeypatch):
    captured = {}
    sentinel = object()

    def _fake_create_media_database(client_id, **kwargs):
        captured["client_id"] = client_id
        captured.update(kwargs)
        return sentinel

    def _raise_legacy_factory(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("legacy DB_Manager factory should not be used")

    monkeypatch.setattr(Users_DB, "get_user_db_path", lambda *_args, **_kwargs: "/tmp/users-media.db")
    monkeypatch.setattr(media_db_api, "create_media_database", _fake_create_media_database)
    monkeypatch.setattr(DB_Manager, "create_media_database", _raise_legacy_factory)

    result = await Users_DB.get_user_media_db(42)

    assert result is sentinel
    assert captured["client_id"] == "42"
    assert captured["db_path"] == "/tmp/users-media.db"
