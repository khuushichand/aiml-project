import pytest

from tldw_Server_API.app.core.File_Artifacts.adapter_registry import (
    AdapterInitializationError,
    FileAdapterRegistry,
)


class BoomAdapter:
    file_type = "boom"
    export_formats: set[str] = set()

    def __init__(self) -> None:
        raise RuntimeError("boom")


def test_get_adapter_missing_returns_none():
    registry = FileAdapterRegistry()
    assert registry.get_adapter("missing_adapter") is None


def test_get_adapter_init_failure_raises():
    registry = FileAdapterRegistry()
    registry.register_adapter("boom", BoomAdapter)
    with pytest.raises(AdapterInitializationError) as excinfo:
        registry.get_adapter("boom")
    assert excinfo.value.adapter_name == "boom"
    assert "boom" not in registry._adapters
