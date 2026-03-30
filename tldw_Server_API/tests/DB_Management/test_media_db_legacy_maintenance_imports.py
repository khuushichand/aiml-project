import importlib

from tldw_Server_API.app.core.DB_Management.media_db import api as media_db_api
from tldw_Server_API.app.core.DB_Management.media_db.legacy_maintenance import (
    permanently_delete_item,
)
from tldw_Server_API.tests.DB_Management._media_db_legacy_stub import (
    install_legacy_media_db_stub,
)


def test_legacy_maintenance_callers_no_longer_depend_on_media_db_v2_exports(monkeypatch) -> None:
    media_db_v2 = install_legacy_media_db_stub(monkeypatch)

    assert not hasattr(media_db_v2, "permanently_delete_item")
    assert not hasattr(media_db_v2, "empty_trash")
    assert not hasattr(media_db_v2, "check_media_and_whisper_model")

    media_item = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.media.item"
    )
    media_listing = importlib.import_module(
        "tldw_Server_API.app.api.v1.endpoints.media.listing"
    )
    media_module_impl = importlib.import_module(
        "tldw_Server_API.app.core.MCP_unified.modules.implementations.media_module"
    )

    assert media_item.permanently_delete_item is permanently_delete_item
    assert media_listing.permanently_delete_item is permanently_delete_item
    assert media_module_impl.permanently_delete_item is media_db_api.permanently_delete_item
