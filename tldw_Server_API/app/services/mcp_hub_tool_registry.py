from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.MCP_unified.modules.registry import ModuleRegistry, get_module_registry

_KNOWN_RISK_CLASSES = ("low", "medium", "high", "unclassified")
_KNOWN_METADATA_SOURCES = ("explicit", "heuristic", "fallback")
_CATEGORY_DEFAULTS: dict[str, dict[str, Any]] = {
    "execution": {
        "risk_class": "high",
        "capabilities": ["process.execute"],
        "mutates_state": True,
        "uses_filesystem": True,
        "uses_processes": True,
        "uses_network": False,
        "uses_credentials": False,
        "path_boundable": False,
    },
    "governance": {
        "risk_class": "medium",
        "capabilities": [],
        "mutates_state": False,
        "uses_filesystem": False,
        "uses_processes": False,
        "uses_network": False,
        "uses_credentials": False,
        "path_boundable": False,
    },
    "ingestion": {
        "risk_class": "high",
        "capabilities": ["filesystem.write"],
        "mutates_state": True,
        "uses_filesystem": True,
        "uses_processes": False,
        "uses_network": False,
        "uses_credentials": False,
        "path_boundable": True,
    },
    "management": {
        "risk_class": "high",
        "capabilities": ["filesystem.write"],
        "mutates_state": True,
        "uses_filesystem": True,
        "uses_processes": False,
        "uses_network": False,
        "uses_credentials": False,
        "path_boundable": True,
    },
    "retrieval": {
        "risk_class": "low",
        "capabilities": ["filesystem.read"],
        "mutates_state": False,
        "uses_filesystem": False,
        "uses_processes": False,
        "uses_network": False,
        "uses_credentials": False,
        "path_boundable": False,
    },
    "search": {
        "risk_class": "low",
        "capabilities": ["filesystem.read"],
        "mutates_state": False,
        "uses_filesystem": False,
        "uses_processes": False,
        "uses_network": False,
        "uses_credentials": False,
        "path_boundable": False,
    },
    "unclassified": {
        "risk_class": "unclassified",
        "capabilities": [],
        "mutates_state": False,
        "uses_filesystem": False,
        "uses_processes": False,
        "uses_network": False,
        "uses_credentials": False,
        "path_boundable": False,
    },
}
_STRONG_EXPLICIT_KEYS = frozenset(
    {
        "capabilities",
        "mutates_state",
        "path_boundable",
        "risk_class",
        "supports_arguments_preview",
        "uses_credentials",
        "uses_filesystem",
        "uses_network",
        "uses_processes",
    }
)
_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("execution", ("bash", "command", "execute", "exec", "process", "run", "sandbox", "shell")),
    ("management", ("create", "delete", "import", "remove", "update", "write")),
    ("ingestion", ("ingest", "upload")),
    ("search", ("find", "list", "query", "search")),
    ("retrieval", ("fetch", "get", "read", "retrieve", "view")),
)


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return None


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    if not isinstance(value, (list, tuple, set)):
        return []
    out: list[str] = []
    for entry in value:
        cleaned = str(entry or "").strip()
        if cleaned:
            out.append(cleaned)
    return out


def _unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _default_risk_summary() -> dict[str, int]:
    return {risk_class: 0 for risk_class in _KNOWN_RISK_CLASSES}


class McpHubToolRegistryService:
    """Derive MCP Hub tool metadata from the live module registry."""

    def __init__(self, module_registry: ModuleRegistry | None = None):
        self._module_registry = module_registry or get_module_registry()

    async def list_entries(self) -> list[dict[str, Any]]:
        modules = await self._module_registry.get_all_modules()
        entries: list[dict[str, Any]] = []

        for module_id, module in sorted(modules.items(), key=lambda item: item[0]):
            try:
                tools = await module.get_tools()
            except Exception as exc:  # noqa: BLE001 - derived registry should fail open
                logger.warning("Skipping MCP Hub tool registry load for module {}: {}", module_id, exc)
                continue

            for tool_def in tools or []:
                entries.append(self._normalize_tool_entry(module_id=module_id, module=module, tool_def=tool_def))

        entries.sort(key=lambda entry: (entry["module"], entry["tool_name"]))
        return entries

    async def list_modules(self) -> list[dict[str, Any]]:
        module_rows: dict[str, dict[str, Any]] = {}

        for entry in await self.list_entries():
            module_key = entry["module"]
            row = module_rows.setdefault(
                module_key,
                {
                    "module": module_key,
                    "display_name": entry.get("module_display_name") or module_key,
                    "tool_count": 0,
                    "risk_summary": _default_risk_summary(),
                    "metadata_warnings": [],
                },
            )
            row["tool_count"] += 1
            risk_class = str(entry.get("risk_class") or "unclassified")
            if risk_class not in row["risk_summary"]:
                row["risk_summary"][risk_class] = 0
            row["risk_summary"][risk_class] += 1
            row["metadata_warnings"] = _unique(
                list(row["metadata_warnings"]) + _as_str_list(entry.get("metadata_warnings"))
            )

        return [module_rows[module_key] for module_key in sorted(module_rows)]

    def _normalize_tool_entry(
        self,
        *,
        module_id: str,
        module: Any,
        tool_def: dict[str, Any],
    ) -> dict[str, Any]:
        metadata = _as_dict(tool_def.get("metadata"))
        tool_name = str(tool_def.get("name") or "").strip()
        display_name = str(metadata.get("display_name") or tool_name or module_id)
        category, category_source = self._resolve_category(tool_name=tool_name, metadata=metadata)
        defaults = dict(_CATEGORY_DEFAULTS.get(category, _CATEGORY_DEFAULTS["unclassified"]))

        risk_class = str(metadata.get("risk_class") or defaults["risk_class"]).strip().lower() or "unclassified"
        if risk_class not in _KNOWN_RISK_CLASSES:
            risk_class = "unclassified"

        capabilities = _unique(
            _as_str_list(metadata.get("capabilities")) or list(defaults.get("capabilities") or [])
        )
        mutates_state = self._resolve_bool(metadata, "mutates_state", defaults["mutates_state"])
        uses_filesystem = self._resolve_bool(metadata, "uses_filesystem", defaults["uses_filesystem"])
        uses_processes = self._resolve_bool(metadata, "uses_processes", defaults["uses_processes"])
        uses_network = self._resolve_bool(metadata, "uses_network", defaults["uses_network"])
        uses_credentials = self._resolve_bool(metadata, "uses_credentials", defaults["uses_credentials"])
        path_boundable = self._resolve_bool(metadata, "path_boundable", defaults["path_boundable"])
        supports_arguments_preview = self._resolve_bool(
            metadata,
            "supports_arguments_preview",
            bool(_as_dict(tool_def.get("inputSchema"))),
        )

        if metadata.get("readOnlyHint") is True and "filesystem.read" not in capabilities:
            capabilities = _unique(capabilities + ["filesystem.read"])

        metadata_source = self._resolve_metadata_source(metadata=metadata, category_source=category_source)
        metadata_warnings = self._metadata_warnings(
            metadata_source=metadata_source,
            category_source=category_source,
            risk_class=risk_class,
        )

        return {
            "tool_name": tool_name,
            "display_name": display_name,
            "description": str(tool_def.get("description") or ""),
            "module": module_id,
            "module_display_name": str(getattr(module, "name", None) or module_id),
            "category": category,
            "risk_class": risk_class,
            "capabilities": capabilities,
            "mutates_state": mutates_state,
            "uses_filesystem": uses_filesystem,
            "uses_processes": uses_processes,
            "uses_network": uses_network,
            "uses_credentials": uses_credentials,
            "supports_arguments_preview": supports_arguments_preview,
            "path_boundable": path_boundable,
            "metadata_source": metadata_source,
            "metadata_warnings": metadata_warnings,
        }

    @staticmethod
    def _resolve_bool(metadata: dict[str, Any], key: str, default: bool) -> bool:
        value = _as_bool(metadata.get(key))
        return default if value is None else value

    def _resolve_category(self, *, tool_name: str, metadata: dict[str, Any]) -> tuple[str, str]:
        category = str(metadata.get("category") or "").strip().lower()
        if category:
            if category in _CATEGORY_DEFAULTS:
                return category, "metadata"
            return "unclassified", "metadata"

        lowered = tool_name.lower()
        for inferred_category, keywords in _CATEGORY_KEYWORDS:
            if any(keyword in lowered for keyword in keywords):
                return inferred_category, "heuristic"
        return "unclassified", "fallback"

    def _resolve_metadata_source(self, *, metadata: dict[str, Any], category_source: str) -> str:
        if any(key in metadata for key in _STRONG_EXPLICIT_KEYS):
            return "explicit"
        if metadata or category_source == "heuristic":
            return "heuristic"
        return "fallback"

    @staticmethod
    def _metadata_warnings(
        *,
        metadata_source: str,
        category_source: str,
        risk_class: str,
    ) -> list[str]:
        warnings: list[str] = []
        if metadata_source == "heuristic" and category_source in {"metadata", "heuristic"}:
            warnings.append("Derived metadata from tool category")
        if metadata_source == "fallback":
            warnings.append("Tool metadata missing; classified conservatively")
        if risk_class == "unclassified":
            warnings.append("Tool risk class requires manual review")
        return _unique(warnings)

