import configparser
import importlib

from tldw_Server_API.app.core.DB_Management import DB_Manager
from tldw_Server_API.app.api.v1.endpoints import research
from tldw_Server_API.app.core.Ingestion_Media_Processing import XML_Ingestion_Lib
from tldw_Server_API.app.core.Ingestion_Media_Processing.MediaWiki import Media_Wiki
from tldw_Server_API.app.core.DB_Management.media_db import api as media_db_api
from tldw_Server_API.app.services import document_processing_service
from tldw_Server_API.app.services import enhanced_web_scraping_service
from tldw_Server_API.app.services import media_ingest_jobs_worker


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


def test_document_processing_service_imports_create_media_database_from_media_db_api():
    module = importlib.reload(document_processing_service)
    assert module.create_media_database is media_db_api.create_media_database


def test_media_ingest_jobs_worker_imports_create_media_database_from_media_db_api():
    module = importlib.reload(media_ingest_jobs_worker)
    assert module.create_media_database is media_db_api.create_media_database


def test_enhanced_web_scraping_service_imports_create_media_database_from_media_db_api():
    module = importlib.reload(enhanced_web_scraping_service)
    assert module.create_media_database is media_db_api.create_media_database


def test_research_endpoint_imports_create_media_database_from_media_db_api():
    module = importlib.reload(research)
    assert module.create_media_database is media_db_api.create_media_database


def test_xml_ingestion_imports_create_media_database_from_media_db_api():
    module = importlib.reload(XML_Ingestion_Lib)
    assert module.create_media_database is media_db_api.create_media_database


def test_mediawiki_imports_create_media_database_from_media_db_api():
    module = importlib.reload(Media_Wiki)
    assert module.create_media_database is media_db_api.create_media_database
