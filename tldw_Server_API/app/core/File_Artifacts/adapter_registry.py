from __future__ import annotations

from typing import Any, Dict, Optional, Type
import importlib

from loguru import logger

from tldw_Server_API.app.core.File_Artifacts.adapters.base import FileAdapter


class FileAdapterRegistry:
    """Registry for structured file adapters."""

    DEFAULT_ADAPTERS: Dict[str, str] = {
        "ical": "tldw_Server_API.app.core.File_Artifacts.adapters.ical_adapter.IcalAdapter",
        "markdown_table": "tldw_Server_API.app.core.File_Artifacts.adapters.markdown_table_adapter.MarkdownTableAdapter",
        "html_table": "tldw_Server_API.app.core.File_Artifacts.adapters.html_table_adapter.HtmlTableAdapter",
        "xlsx": "tldw_Server_API.app.core.File_Artifacts.adapters.xlsx_adapter.XlsxAdapter",
        "data_table": "tldw_Server_API.app.core.File_Artifacts.adapters.data_table_adapter.DataTableAdapter",
    }

    def __init__(self) -> None:
        self._adapters: Dict[str, FileAdapter] = {}
        self._adapter_specs: Dict[str, Any] = self.DEFAULT_ADAPTERS.copy()

    def register_adapter(self, name: str, adapter: Any) -> None:
        self._adapter_specs[name] = adapter
        try:
            adapter_name = adapter.__name__  # type: ignore[attr-defined]
        except Exception:
            adapter_name = str(adapter)
        logger.info("Registered file adapter %s for file_type '%s'", adapter_name, name)

    def _resolve_adapter_class(self, spec: Any) -> Type[FileAdapter]:
        if isinstance(spec, str):
            module_path, _, class_name = spec.rpartition(".")
            if not module_path:
                raise ImportError(f"Invalid adapter spec '{spec}'")
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        return spec

    def get_adapter(self, name: str) -> Optional[FileAdapter]:
        if name in self._adapters:
            return self._adapters[name]

        spec = self._adapter_specs.get(name)
        if not spec:
            logger.debug("No adapter spec registered for file_type '%s'", name)
            return None

        try:
            adapter_cls = self._resolve_adapter_class(spec)
            adapter = adapter_cls()  # type: ignore[call-arg]
            self._adapters[name] = adapter
            return adapter
        except Exception as exc:
            logger.error("Failed to initialize adapter for '%s': %s", name, exc)
            return None

    def list_types(self) -> list[str]:
        return sorted(self._adapter_specs.keys())


_registry: Optional[FileAdapterRegistry] = None


def get_registry() -> FileAdapterRegistry:
    global _registry
    if _registry is None:
        _registry = FileAdapterRegistry()
    return _registry
