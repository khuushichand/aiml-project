import importlib

import pytest

from tldw_Server_API.app.core.DB_Management.media_db import legacy_state
from tldw_Server_API.app.core.DB_Management.media_db import legacy_wrappers

pytestmark = pytest.mark.unit


def test_media_update_lib_imports_check_media_exists_from_legacy_state(
    monkeypatch,
) -> None:
    media_db_v2 = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )
    media_update_lib = importlib.import_module(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Media_Update_lib"
    )

    def _shim_should_not_be_bound(*args, **kwargs):
        raise AssertionError(
            "Media_Update_lib should not bind check_media_exists from Media_DB_v2"
        )

    monkeypatch.setattr(
        media_db_v2,
        "check_media_exists",
        _shim_should_not_be_bound,
    )

    reloaded = importlib.reload(media_update_lib)
    assert reloaded._check_media_exists is legacy_state.check_media_exists


def test_media_update_lib_imports_document_version_from_legacy_wrappers(
    monkeypatch,
) -> None:
    media_db_v2 = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )
    media_update_lib = importlib.import_module(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Media_Update_lib"
    )

    def _shim_should_not_be_bound(*args, **kwargs):
        raise AssertionError(
            "Media_Update_lib should not bind get_document_version from Media_DB_v2"
        )

    monkeypatch.setattr(
        media_db_v2,
        "get_document_version",
        _shim_should_not_be_bound,
    )

    reloaded = importlib.reload(media_update_lib)
    assert reloaded._get_document_version is legacy_wrappers.get_document_version


def test_media_update_lib_does_not_bind_media_database_from_media_db_v2(
    monkeypatch,
) -> None:
    media_db_v2 = importlib.import_module(
        "tldw_Server_API.app.core.DB_Management.Media_DB_v2"
    )
    media_update_lib = importlib.import_module(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Media_Update_lib"
    )

    monkeypatch.setattr(
        media_db_v2,
        "MediaDatabase",
        object(),
    )

    reloaded = importlib.reload(media_update_lib)
    assert "MediaDatabase" not in reloaded.__dict__
