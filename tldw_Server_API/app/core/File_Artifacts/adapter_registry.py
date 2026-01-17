from __future__ import annotations

import importlib
from typing import Any, ClassVar, Dict, Optional, Type

from loguru import logger

from tldw_Server_API.app.core.File_Artifacts.adapters.base import FileAdapter


class AdapterInitializationError(RuntimeError):
    """Raised when a file adapter fails to initialize."""

    def __init__(self, name: str, spec: Any, exc: Exception) -> None:
        message = f"Failed to initialize adapter '{name}' (spec={spec!r}): {exc}"
        super().__init__(message)
        self.adapter_name = name
        self.spec = spec
        self.original_exception = exc


class FileAdapterRegistry:
    """Registry for structured file adapters."""

    DEFAULT_ADAPTERS: ClassVar[Dict[str, str]] = {
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
        except AttributeError:
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
            logger.error("Failed to initialize adapter for '%s' (spec=%r): %s", name, spec, exc)
            raise AdapterInitializationError(name, spec, exc) from exc

    def list_types(self) -> list[str]:
        return sorted(self._adapter_specs.keys())


def get_registry() -> FileAdapterRegistry:
    return FileAdapterRegistry()
