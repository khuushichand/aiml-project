import importlib

from tldw_Server_API.app.core.DB_Management.media_db import legacy_reads


def test_document_references_imports_latest_transcription_from_legacy_reads(
    monkeypatch,
) -> None:
    media_db_v2 = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )
    document_references = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.media.document_references"
    )

    def _shim_should_not_be_bound(*args, **kwargs):
        raise AssertionError(
            "document_references should not bind get_latest_transcription from Media_DB_v2"
        )

    monkeypatch.setattr(
        media_db_v2,
        "get_latest_transcription",
        _shim_should_not_be_bound,
    )

    reloaded = importlib.reload(document_references)
    assert reloaded.get_latest_transcription is legacy_reads.get_latest_transcription


def test_document_insights_imports_latest_transcription_from_legacy_reads(
    monkeypatch,
) -> None:
    media_db_v2 = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )
    document_insights = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.media.document_insights"
    )

    def _shim_should_not_be_bound(*args, **kwargs):
        raise AssertionError(
            "document_insights should not bind get_latest_transcription from Media_DB_v2"
        )

    monkeypatch.setattr(
        media_db_v2,
        "get_latest_transcription",
        _shim_should_not_be_bound,
    )

    reloaded = importlib.reload(document_insights)
    assert reloaded.get_latest_transcription is legacy_reads.get_latest_transcription


def test_quiz_source_resolver_imports_latest_transcription_from_legacy_reads(
    monkeypatch,
) -> None:
    media_db_v2 = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )
    quiz_source_resolver = importlib.import_module(
        "tldw_Server_API.app.services.quiz_source_resolver"
    )

    def _shim_should_not_be_bound(*args, **kwargs):
        raise AssertionError(
            "quiz_source_resolver should not bind get_latest_transcription from Media_DB_v2"
        )

    monkeypatch.setattr(
        media_db_v2,
        "get_latest_transcription",
        _shim_should_not_be_bound,
    )

    reloaded = importlib.reload(quiz_source_resolver)
    assert reloaded.get_latest_transcription is legacy_reads.get_latest_transcription


def test_slides_endpoint_imports_latest_transcription_from_legacy_reads(
    monkeypatch,
) -> None:
    media_db_v2 = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )
    slides_endpoint = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.slides"
    )

    def _shim_should_not_be_bound(*args, **kwargs):
        raise AssertionError(
            "slides endpoint should not bind get_latest_transcription from Media_DB_v2"
        )

    monkeypatch.setattr(
        media_db_v2,
        "get_latest_transcription",
        _shim_should_not_be_bound,
    )

    reloaded = importlib.reload(slides_endpoint)
    assert reloaded.get_latest_transcription is legacy_reads.get_latest_transcription


def test_data_tables_jobs_worker_imports_latest_transcription_from_legacy_reads(
    monkeypatch,
) -> None:
    media_db_v2 = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )
    data_tables_jobs_worker = importlib.import_module(
        "tldw_Server_API.app.core.Data_Tables.jobs_worker"
    )

    def _shim_should_not_be_bound(*args, **kwargs):
        raise AssertionError(
            "data_tables.jobs_worker should not bind get_latest_transcription from Media_DB_v2"
        )

    monkeypatch.setattr(
        media_db_v2,
        "get_latest_transcription",
        _shim_should_not_be_bound,
    )

    reloaded = importlib.reload(data_tables_jobs_worker)
    assert reloaded.get_latest_transcription is legacy_reads.get_latest_transcription
