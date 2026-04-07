import sys
from pathlib import Path
from types import ModuleType


_LEGACY_MODULE_NAME = "tldw_Server_API.app.core.DB_Management.Media_DB_v2"


class _LazyLegacyMediaDBProxy(ModuleType):
    """Module-like proxy used by compatibility tests after deleting Media_DB_v2.py."""

    _STUB_ATTRS = {
        "ConflictError": object(),
        "DatabaseError": object(),
        "InputError": object(),
        "SchemaError": object(),
        "MediaDatabase": object(),
        "check_media_exists": object(),
        "get_document_version": object(),
        "get_full_media_details": object(),
        "get_full_media_details_rich": object(),
        "create_automated_backup": object(),
        "get_latest_transcription": object(),
        "get_media_prompts": object(),
        "get_media_transcripts": object(),
    }

    def __init__(self) -> None:
        legacy_module_path = (
            Path(__file__).resolve().parents[2]
            / "app/core/DB_Management/Media_DB_v2.py"
        )
        super().__init__(_LEGACY_MODULE_NAME)
        object.__setattr__(self, "__file__", str(legacy_module_path))
        object.__setattr__(self, "__package__", "tldw_Server_API.app.core.DB_Management")
        for name, value in self._STUB_ATTRS.items():
            object.__setattr__(self, name, value)

def install_legacy_media_db_stub(monkeypatch) -> ModuleType:
    module = _LazyLegacyMediaDBProxy()
    monkeypatch.setitem(sys.modules, _LEGACY_MODULE_NAME, module)
    return module
