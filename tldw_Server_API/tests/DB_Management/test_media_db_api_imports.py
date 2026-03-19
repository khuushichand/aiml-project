import configparser
import inspect
import importlib
import sys

import pytest

from tldw_Server_API.app.core.DB_Management import DB_Manager
from tldw_Server_API.app.core.DB_Management import Users_DB
from tldw_Server_API.app.core.DB_Management import Media_DB_v2 as legacy_media_db
from tldw_Server_API.app.core.DB_Management import Prompts_DB as prompts_db_module
from tldw_Server_API.app.core.DB_Management import db_path_utils
from tldw_Server_API.app.core.AuthNZ import migrate_to_multiuser
from tldw_Server_API.app.api.v1.endpoints import rag_unified as rag_unified_endpoint
from tldw_Server_API.app.api.v1.endpoints import research
from tldw_Server_API.app.api.v1.endpoints import claims as claims_endpoint
from tldw_Server_API.app.api.v1.endpoints import chunking as chunking_endpoint
from tldw_Server_API.app.api.v1.endpoints import chunking_templates as chunking_templates_endpoint
from tldw_Server_API.app.api.v1.endpoints import embeddings_v5_production_enhanced as embeddings_v5_endpoint
from tldw_Server_API.app.api.v1.endpoints import paper_search as paper_search_endpoint
from tldw_Server_API.app.api.v1.endpoints.audio import audiobooks as audiobooks_endpoint
from tldw_Server_API.app.api.v1.endpoints import slides as slides_endpoint
from tldw_Server_API.app.api.v1.endpoints import text2sql as text2sql_endpoint
from tldw_Server_API.app.api.v1.endpoints import media_embeddings as media_embeddings_endpoint
from tldw_Server_API.app.api.v1.endpoints import email as email_endpoint
from tldw_Server_API.app.api.v1.endpoints import data_tables
from tldw_Server_API.app.api.v1.endpoints import items
from tldw_Server_API.app.api.v1.endpoints import quizzes as quizzes_endpoint
from tldw_Server_API.app.api.v1.endpoints import vector_stores_openai as vector_stores_endpoint
from tldw_Server_API.app.api.v1.endpoints import sync
from tldw_Server_API.app.api.v1.API_Deps import DB_Deps as media_db_deps
from tldw_Server_API.app.api.v1.endpoints.media import document_outline
from tldw_Server_API.app.api.v1.endpoints.media import document_insights
from tldw_Server_API.app.api.v1.endpoints.media import document_references
from tldw_Server_API.app.api.v1.endpoints.media import add as media_add_endpoint
from tldw_Server_API.app.api.v1.endpoints.media import document_annotations as media_document_annotations_endpoint
from tldw_Server_API.app.api.v1.endpoints.media import debug as media_debug_endpoint
from tldw_Server_API.app.api.v1.endpoints.media import document_figures as media_document_figures_endpoint
from tldw_Server_API.app.api.v1.endpoints.media import file as media_file_endpoint
from tldw_Server_API.app.api.v1.endpoints.media import ingest_web_content as media_ingest_web_content_endpoint
from tldw_Server_API.app.api.v1.endpoints.media import item as media_item
from tldw_Server_API.app.api.v1.endpoints.media import listing as media_listing_endpoint
from tldw_Server_API.app.api.v1.endpoints.media import navigation as media_navigation
from tldw_Server_API.app.api.v1.endpoints.media import process_audios as media_process_audios_endpoint
from tldw_Server_API.app.api.v1.endpoints.media import process_code as media_process_code_endpoint
from tldw_Server_API.app.api.v1.endpoints.media import process_ebooks as media_process_ebooks_endpoint
from tldw_Server_API.app.api.v1.endpoints.media import process_documents
from tldw_Server_API.app.api.v1.endpoints.media import process_emails as media_process_emails_endpoint
from tldw_Server_API.app.api.v1.endpoints.media import process_pdfs
from tldw_Server_API.app.api.v1.endpoints.media import process_videos as media_process_videos_endpoint
from tldw_Server_API.app.api.v1.endpoints.media import process_web_scraping as media_process_web_scraping_endpoint
from tldw_Server_API.app.api.v1.endpoints.media import reprocess as media_reprocess_endpoint
from tldw_Server_API.app.api.v1.endpoints.audio import audio_history as audio_history_endpoint
from tldw_Server_API.app.api.v1.endpoints.audio import audio_tts as audio_tts_endpoint
from tldw_Server_API.app.api.v1.utils import http_errors
from tldw_Server_API.app.api.v1.endpoints.media import versions as media_versions
from tldw_Server_API.app.core.Claims_Extraction import (
    claims_clustering,
    ingestion_claims,
    claims_notifications,
    claims_rebuild_service,
    claims_service,
    claims_utils,
    review_assignment,
)
from tldw_Server_API.app.core.Evaluations import embeddings_abtest_service
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
from tldw_Server_API.app.core.Ingestion_Media_Processing import persistence as ingestion_persistence
from tldw_Server_API.app.core.Ingestion_Media_Processing import XML_Ingestion_Lib
from tldw_Server_API.app.core.Ingestion_Media_Processing.MediaWiki import Media_Wiki
from tldw_Server_API.app.core.Data_Tables import jobs_worker as data_tables_jobs_worker
from tldw_Server_API.app.core.External_Sources import sync_coordinator
from tldw_Server_API.app.core.RAG.rag_service import agentic_chunker
from tldw_Server_API.app.core.RAG.rag_service import database_retrievers
from tldw_Server_API.app.core.RAG.rag_service import unified_pipeline
from tldw_Server_API.app.core.Chatbooks import chatbook_service
from tldw_Server_API.app.core.MCP_unified.modules.implementations import media_module as media_module_impl
from tldw_Server_API.app.core.Sync import Sync_Client as sync_client_module
from tldw_Server_API.app.services import ingestion_sources_worker
from tldw_Server_API.app.core.MCP_unified.modules.implementations import quizzes_module
from tldw_Server_API.app.core.MCP_unified.modules.implementations import slides_module
from tldw_Server_API.app.core.Utils import metadata_utils
from tldw_Server_API.app.core.Web_Scraping import Article_Extractor_Lib
from tldw_Server_API.app.core.Watchlists import pipeline as watchlists_pipeline
from tldw_Server_API.app.core.DB_Management.media_db import api as media_db_api
from tldw_Server_API.app.core.DB_Management import media_db as media_db_package
from tldw_Server_API.app.core.DB_Management.media_db import legacy_backup as media_db_legacy_backup
from tldw_Server_API.app.core.DB_Management.media_db import errors as media_db_errors
from tldw_Server_API.app.core.DB_Management.media_db import legacy_identifiers as media_db_legacy_identifiers
from tldw_Server_API.app.core.DB_Management.media_db import legacy_document_artifacts
from tldw_Server_API.app.core.DB_Management.media_db import legacy_content_queries
from tldw_Server_API.app.core.DB_Management.media_db import legacy_maintenance
from tldw_Server_API.app.core.DB_Management.media_db import legacy_reads as media_db_legacy_reads
from tldw_Server_API.app.core.DB_Management.media_db import legacy_media_details
from tldw_Server_API.app.core.DB_Management.media_db import legacy_state as media_db_state
from tldw_Server_API.app.core.DB_Management.media_db import legacy_transcripts
from tldw_Server_API.app.core.DB_Management.media_db import legacy_wrappers
from tldw_Server_API.app.core.DB_Management.media_db.repositories import chunks_repository
from tldw_Server_API.app.core.DB_Management.media_db.repositories import document_versions_repository
from tldw_Server_API.app.core.DB_Management.media_db.repositories import keywords_repository
from tldw_Server_API.app.core.DB_Management.media_db.repositories import media_files_repository
from tldw_Server_API.app.core.DB_Management.media_db.repositories import media_repository
from tldw_Server_API.app.core.DB_Management.media_db.runtime import factory as media_db_runtime_factory
from tldw_Server_API.app.core.DB_Management.media_db.runtime import execution as media_db_runtime_execution
from tldw_Server_API.app.core.DB_Management.media_db.runtime import media_class as media_db_runtime_media_class
from tldw_Server_API.app.core.DB_Management.media_db.runtime import rows as media_db_runtime_rows
from tldw_Server_API.app.services import admin_bundle_service
from tldw_Server_API.app.services import media_files_cleanup_service
from tldw_Server_API.app.services import document_processing_service
from tldw_Server_API.app.services import claims_alerts_scheduler
from tldw_Server_API.app.services import claims_review_metrics_scheduler
from tldw_Server_API.app.services import connectors_worker
from tldw_Server_API.app.services import meetings_webhook_dlq_service
from tldw_Server_API.app.services import quiz_generator
from tldw_Server_API.app.services import quiz_source_resolver
from tldw_Server_API.app.services import audiobook_jobs_worker
from tldw_Server_API.app.services import enhanced_web_scraping_service
from tldw_Server_API.app.services import media_ingest_jobs_worker
from tldw_Server_API.app.services import outputs_purge_scheduler
from tldw_Server_API.app.services import storage_cleanup_service
from tldw_Server_API.app.services import tts_history_cleanup_service
from tldw_Server_API.app.services import web_scraping_service


def test_media_db_api_create_media_database_uses_runtime_factory(monkeypatch, tmp_path):
    captured = {}
    default_db_path = str(tmp_path / "api-media.db")
    override_db_path = str(tmp_path / "override.db")

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
    monkeypatch.setattr(DB_Manager, "single_user_db_path", default_db_path, raising=False)
    monkeypatch.setattr(DB_Manager, "single_user_config", cfg, raising=False)
    monkeypatch.setattr(DB_Manager, "_POSTGRES_CONTENT_MODE", True, raising=False)
    monkeypatch.setattr(DB_Manager, "_ensure_content_backend_loaded", lambda: "backend-sentinel", raising=False)

    result = media_db_api.create_media_database(
        "client-api",
        db_path=override_db_path,
    )

    assert result == "db-instance"
    assert captured["client_id"] == "client-api"
    assert captured["db_path"] == override_db_path
    assert captured["runtime"].default_db_path == default_db_path
    assert captured["runtime"].default_config is cfg
    assert captured["runtime"].postgres_content_mode is True


def test_media_db_api_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(media_db_api)


def test_media_repository_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(media_repository)


def test_legacy_media_db_module_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(legacy_media_db)


def test_chunking_templates_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(chunking_templates_endpoint)


def test_embeddings_v5_endpoint_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(embeddings_v5_endpoint)


def test_prompts_db_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(prompts_db_module)


def test_migrate_to_multiuser_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(migrate_to_multiuser)


def test_db_path_utils_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(db_path_utils)


def test_media_db_errors_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(media_db_errors)


def test_media_db_package_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(media_db_package)


def test_media_db_runtime_rows_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(media_db_runtime_rows)


def test_media_db_runtime_execution_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(media_db_runtime_execution)


def test_media_db_runtime_media_class_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(media_db_runtime_media_class)


def test_media_db_legacy_identifiers_owns_media_db_v2_reference() -> None:
    assert "Media_DB_v2" in inspect.getsource(media_db_legacy_identifiers)


def test_meetings_webhook_dlq_service_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(meetings_webhook_dlq_service)


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


def test_document_outline_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(document_outline)

    assert "MediaDatabase" not in module.__dict__


def test_process_documents_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(process_documents)

    assert "MediaDatabase" not in module.__dict__


def test_process_pdfs_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(process_pdfs)

    assert "MediaDatabase" not in module.__dict__


def test_reading_progress_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    module_name = "tldw_Server_API.app.api.v1.endpoints.media.reading_progress"
    sys.modules.pop(module_name, None)

    module = importlib.import_module(module_name)

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


def test_media_versions_imports_errors_and_state_helpers_outside_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "ConflictError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "DatabaseError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "InputError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "check_media_exists", object(), raising=False)

    module = importlib.reload(media_versions)

    assert module.ConflictError is media_db_errors.ConflictError
    assert module.DatabaseError is media_db_errors.DatabaseError
    assert module.InputError is media_db_errors.InputError
    assert module.check_media_exists is media_db_state.check_media_exists
    assert "MediaDatabase" not in module.__dict__


def test_items_imports_db_errors_from_media_db_errors(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "DatabaseError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "InputError", object(), raising=False)

    module = importlib.reload(items)

    assert module.DatabaseError is media_db_errors.DatabaseError
    assert module.InputError is media_db_errors.InputError


def test_data_tables_imports_input_error_from_media_db_errors_and_not_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "InputError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(data_tables)

    assert module.InputError is media_db_errors.InputError
    assert "MediaDatabase" not in module.__dict__


def test_sync_imports_db_errors_from_media_db_errors_and_not_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "ConflictError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "DatabaseError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "InputError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(sync)

    assert module.ConflictError is media_db_errors.ConflictError
    assert module.DatabaseError is media_db_errors.DatabaseError
    assert module.InputError is media_db_errors.InputError
    assert "MediaDatabase" not in module.__dict__


def test_db_manager_does_not_bind_detail_helpers_from_media_db_v2(monkeypatch):
    sentinel_details = object()
    sentinel_rich = object()
    sentinel_backup = object()

    monkeypatch.setattr(legacy_media_db, "get_full_media_details", sentinel_details, raising=False)
    monkeypatch.setattr(legacy_media_db, "get_full_media_details_rich", sentinel_rich, raising=False)
    monkeypatch.setattr(legacy_media_db, "create_automated_backup", sentinel_backup, raising=False)

    module = importlib.reload(DB_Manager)

    assert module.sqlite_get_full_media_details is legacy_media_details.get_full_media_details
    assert module.sqlite_get_full_media_details_rich is legacy_media_details.get_full_media_details_rich
    assert module.sqlite_create_automated_backup is media_db_legacy_backup.create_automated_backup


def test_db_manager_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(DB_Manager)

    assert "MediaDatabase" not in module.__dict__


def test_db_manager_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(DB_Manager)


def test_claim_review_assignment_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(review_assignment)

    assert "MediaDatabase" not in module.__dict__


def test_sync_coordinator_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(sync_coordinator)

    assert "MediaDatabase" not in module.__dict__


def test_quiz_generator_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(quiz_generator)

    assert "MediaDatabase" not in module.__dict__


def test_quiz_source_resolver_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(quiz_source_resolver)

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


def test_research_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(research)

    assert "MediaDatabase" not in module.__dict__


def test_rag_unified_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(rag_unified_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_slides_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(slides_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_quizzes_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(quizzes_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_claims_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(claims_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_chunking_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(chunking_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_vector_stores_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(vector_stores_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_text2sql_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(text2sql_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_audio_history_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(audio_history_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_audio_tts_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(audio_tts_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_media_embeddings_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_embeddings_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_media_debug_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_debug_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_media_add_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_add_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_media_file_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_file_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_media_ingest_web_content_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_ingest_web_content_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_media_process_ebooks_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_process_ebooks_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_media_process_web_scraping_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_process_web_scraping_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_media_process_videos_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_process_videos_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_media_process_audios_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_process_audios_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_media_process_emails_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_process_emails_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_media_process_code_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_process_code_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_media_reprocess_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_reprocess_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_media_reprocess_endpoint_imports_db_errors_from_media_db_errors(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "ConflictError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "DatabaseError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "InputError", object(), raising=False)

    module = importlib.reload(media_reprocess_endpoint)

    assert module.ConflictError is media_db_errors.ConflictError
    assert module.DatabaseError is media_db_errors.DatabaseError
    assert module.InputError is media_db_errors.InputError


def test_media_document_figures_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_document_figures_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_audiobooks_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(audiobooks_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_email_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(email_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_email_endpoint_imports_db_errors_from_media_db_errors(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "DatabaseError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "InputError", object(), raising=False)

    module = importlib.reload(email_endpoint)

    assert module.DatabaseError is media_db_errors.DatabaseError
    assert module.InputError is media_db_errors.InputError


def test_media_listing_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_listing_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_media_listing_endpoint_imports_db_errors_from_media_db_errors(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "DatabaseError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "InputError", object(), raising=False)

    module = importlib.reload(media_listing_endpoint)

    assert module.DatabaseError is media_db_errors.DatabaseError
    assert module.InputError is media_db_errors.InputError


def test_chunking_templates_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(chunking_templates_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_document_annotations_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(media_document_annotations_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_paper_search_endpoint_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(paper_search_endpoint)

    assert "MediaDatabase" not in module.__dict__


def test_connectors_worker_imports_create_media_database_from_media_db_api():
    module = importlib.reload(connectors_worker)
    assert module.create_media_database is media_db_api.create_media_database


def test_xml_ingestion_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(XML_Ingestion_Lib)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_ingestion_sources_worker_imports_create_media_database_from_media_db_api():
    module = importlib.reload(ingestion_sources_worker)
    assert module.create_media_database is media_db_api.create_media_database


def test_ingestion_sources_worker_imports_media_db_error_from_media_db_errors(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "DatabaseError", object(), raising=False)

    module = importlib.reload(ingestion_sources_worker)

    assert module.MediaDatabaseError is media_db_errors.DatabaseError


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
    assert "Media_DB_v2" not in inspect.getsource(module)


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


def test_data_tables_jobs_worker_does_not_bind_media_database_from_media_db_v2(
    monkeypatch,
):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(data_tables_jobs_worker)

    assert "MediaDatabase" not in module.__dict__


def test_claims_notifications_imports_managed_media_database_from_media_db_api(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    module = importlib.reload(claims_notifications)
    assert module.managed_media_database is media_db_api.managed_media_database
    assert "MediaDatabase" not in module.__dict__


def test_claims_service_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(claims_service)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_ingestion_claims_does_not_bind_media_database_from_media_db_v2(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)

    module = importlib.reload(ingestion_claims)

    assert "MediaDatabase" not in module.__dict__


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


def test_template_initialization_imports_managed_media_database_from_media_db_api(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    module = importlib.reload(template_initialization)
    assert module.managed_media_database is media_db_api.managed_media_database
    assert "MediaDatabase" not in module.__dict__


def test_watchlists_pipeline_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(watchlists_pipeline)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_workflow_knowledge_crud_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(knowledge_crud)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_unified_pipeline_imports_managed_media_database_from_media_db_api():
    module = importlib.reload(unified_pipeline)
    assert module.managed_media_database is media_db_api.managed_media_database


def test_agentic_chunker_imports_create_media_database_from_media_db_api(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    module = importlib.reload(agentic_chunker)
    assert module.create_media_database is media_db_api.create_media_database


def test_database_retrievers_import_media_db_factory_and_errors_outside_shim(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "DatabaseError", object(), raising=False)

    module = importlib.reload(database_retrievers)

    assert module.create_media_database is media_db_api.create_media_database
    assert module.MediaDatabaseError is media_db_errors.DatabaseError


def test_metadata_utils_imports_database_error_from_media_db_errors():
    source = inspect.getsource(metadata_utils)

    assert "core.DB_Management.Media_DB_v2" not in source
    assert "core.DB_Management.media_db.errors" in source


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


def test_claims_review_metrics_scheduler_imports_managed_media_database_from_media_db_api(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    module = importlib.reload(claims_review_metrics_scheduler)
    assert module.managed_media_database is media_db_api.managed_media_database
    assert "MediaDatabase" not in module.__dict__


def test_media_endpoint_package_does_not_bind_media_database_from_shim(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    module = importlib.reload(
        importlib.import_module("tldw_Server_API.app.api.v1.endpoints.media")
    )
    assert "MediaDatabase" not in module.__dict__


def test_chatbook_service_imports_media_factory_and_legacy_reads(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    module = importlib.reload(chatbook_service)
    assert module.create_media_database is media_db_api.create_media_database
    assert module.get_media_prompts is media_db_legacy_reads.get_media_prompts
    assert module.get_media_transcripts is media_db_legacy_reads.get_media_transcripts
    assert "MediaDatabase" not in module.__dict__


def test_sync_client_imports_factory_and_db_errors_outside_shim(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "ConflictError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "DatabaseError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "InputError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    module = importlib.reload(sync_client_module)
    assert module.create_media_database is media_db_api.create_media_database
    assert module.ConflictError is media_db_errors.ConflictError
    assert module.DatabaseError is media_db_errors.DatabaseError
    assert module.InputError is media_db_errors.InputError
    assert "MediaDatabase" not in module.__dict__
    assert "Media_DB_v2" not in inspect.getsource(module)


def test_claims_service_does_not_bind_media_database_from_shim(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    module = importlib.reload(claims_service)
    assert module.managed_media_database is media_db_api.managed_media_database
    assert "MediaDatabase" not in module.__dict__


def test_media_module_imports_create_media_database_from_media_db_api(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    module = importlib.reload(media_module_impl)
    assert module.create_media_database is media_db_api.create_media_database
    assert "MediaDatabase" not in module.__dict__
    assert "Media_DB_v2" not in inspect.getsource(module)


def test_persistence_imports_factory_and_db_errors_outside_shim(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "ConflictError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "DatabaseError", object(), raising=False)
    monkeypatch.setattr(legacy_media_db, "InputError", object(), raising=False)

    module = importlib.reload(ingestion_persistence)

    assert module.create_media_database is media_db_api.create_media_database
    assert module.ConflictError is media_db_errors.ConflictError
    assert module.DatabaseError is media_db_errors.DatabaseError
    assert module.InputError is media_db_errors.InputError
    assert "MediaDatabase" not in module.__dict__
    assert "Media_DB_v2" not in inspect.getsource(module)


def test_legacy_state_uses_runtime_validation_without_shim_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(media_db_state)


def test_legacy_reads_uses_runtime_validation_without_shim_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(media_db_legacy_reads)


def test_legacy_wrappers_uses_runtime_validation_without_shim_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(legacy_wrappers)


def test_legacy_document_artifacts_uses_runtime_validation_without_shim_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(legacy_document_artifacts)


def test_legacy_content_queries_uses_runtime_validation_without_shim_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(legacy_content_queries)


def test_legacy_media_details_uses_runtime_validation_without_shim_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(legacy_media_details)


def test_legacy_transcripts_uses_runtime_validation_without_shim_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(legacy_transcripts)


def test_legacy_maintenance_uses_runtime_validation_without_shim_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(legacy_maintenance)


def test_legacy_backup_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(media_db_legacy_backup)


def test_chunks_repository_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(chunks_repository)


def test_document_versions_repository_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(document_versions_repository)


def test_keywords_repository_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(keywords_repository)


def test_media_files_repository_no_longer_mentions_media_db_v2_in_source() -> None:
    assert "Media_DB_v2" not in inspect.getsource(media_files_repository)


def test_admin_bundle_service_imports_media_schema_helper_from_runtime_factory():
    module = importlib.reload(admin_bundle_service)
    assert module.get_current_media_schema_version is media_db_runtime_factory.get_current_media_schema_version


def test_embeddings_abtest_jobs_worker_imports_create_media_database_from_media_db_api():
    module = importlib.reload(embeddings_abtest_jobs_worker)
    assert module.create_media_database is media_db_api.create_media_database


def test_embeddings_abtest_service_does_not_bind_media_database_from_shim(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    module = importlib.reload(embeddings_abtest_service)
    assert "MediaDatabase" not in module.__dict__


def test_claims_clustering_does_not_bind_media_database_from_shim(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    module = importlib.reload(claims_clustering)
    assert "MediaDatabase" not in module.__dict__


def test_tts_jobs_worker_imports_create_media_database_from_media_db_api(monkeypatch):
    monkeypatch.setattr(legacy_media_db, "MediaDatabase", object(), raising=False)
    module = importlib.reload(tts_jobs_worker)
    assert module.create_media_database is media_db_api.create_media_database
    assert "MediaDatabase" not in module.__dict__


def test_media_db_api_managed_media_database_initializes_and_closes(monkeypatch, tmp_path):
    events = []
    db_path = str(tmp_path / "managed.db")

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

    with media_db_api.managed_media_database("managed-client", db_path=db_path) as db:
        assert db is fake_db
        events.append("body")

    assert events == [
        ("create", "managed-client", db_path),
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
    db_path = "users-media.db"

    def _fake_create_media_database(client_id, **kwargs):
        captured["client_id"] = client_id
        captured.update(kwargs)
        return sentinel

    def _raise_legacy_factory(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("legacy DB_Manager factory should not be used")

    monkeypatch.setattr(Users_DB, "get_user_db_path", lambda *_args, **_kwargs: db_path)
    monkeypatch.setattr(media_db_api, "create_media_database", _fake_create_media_database)
    monkeypatch.setattr(DB_Manager, "create_media_database", _raise_legacy_factory)

    result = await Users_DB.get_user_media_db(42)

    assert result is sentinel
    assert captured["client_id"] == "42"
    assert captured["db_path"] == db_path
