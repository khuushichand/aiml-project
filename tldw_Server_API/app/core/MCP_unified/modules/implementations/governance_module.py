"""Governance tools for Unified MCP."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping

from loguru import logger

from tldw_Server_API.app.core.Governance.service import GovernanceService
from tldw_Server_API.app.core.Governance.store import GovernanceStore

from ..base import BaseModule, ModuleConfig, create_tool_definition


class GovernanceModule(BaseModule):
    """Expose shared governance query/validation/gap tools."""

    def __init__(
        self,
        config: ModuleConfig,
        governance_service: GovernanceService | None = None,
    ) -> None:
        super().__init__(config)
        self._governance_service = governance_service
        self._store: GovernanceStore | None = None
        self._service_lock = asyncio.Lock()

    async def on_initialize(self) -> None:
        await self._ensure_service()
        logger.info(f"Initializing Governance module: {self.name}")

    async def on_shutdown(self) -> None:
        logger.info(f"Shutting down Governance module: {self.name}")

    async def check_health(self) -> dict[str, bool]:
        return {
            "initialized": True,
            "service_ready": self._governance_service is not None,
        }

    async def get_tools(self) -> list[dict[str, Any]]:
        return [
            create_tool_definition(
                name="governance.query_knowledge",
                description="Query governance guidance and resolved category source.",
                parameters={
                    "properties": {
                        "query": {"type": "string", "minLength": 1, "maxLength": 4000},
                        "category": {"type": "string"},
                        "metadata": {"type": "object"},
                    },
                    "required": ["query"],
                },
                metadata={"category": "governance", "readOnlyHint": True},
            ),
            create_tool_definition(
                name="governance.validate_change",
                description="Validate a proposed change against governance policy actions.",
                parameters={
                    "properties": {
                        "surface": {"type": "string", "minLength": 1, "maxLength": 256},
                        "summary": {"type": "string", "minLength": 1, "maxLength": 4000},
                        "category": {"type": "string"},
                        "metadata": {"type": "object"},
                        "fallback_mode": {"type": "string"},
                    },
                    "required": ["surface", "summary"],
                },
                metadata={"category": "governance"},
            ),
            create_tool_definition(
                name="governance.resolve_gap",
                description="Open or deduplicate a governance gap for a policy question.",
                parameters={
                    "properties": {
                        "question": {"type": "string", "minLength": 1, "maxLength": 4000},
                        "category": {"type": "string"},
                        "metadata": {"type": "object"},
                        "org_id": {"type": "integer"},
                        "team_id": {"type": "integer"},
                        "persona_id": {"type": "string"},
                        "workspace_id": {"type": "string"},
                        "resolution_mode": {"type": "string"},
                    },
                    "required": ["question"],
                },
                metadata={"category": "governance"},
            ),
        ]

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any], context: Any | None = None) -> Any:
        args = self.sanitize_input(arguments or {})
        service = await self._ensure_service()
        metadata = self._merged_metadata(args, context)

        if tool_name == "governance.query_knowledge":
            result = await service.query_knowledge(
                query=str(args.get("query") or ""),
                category=self._optional_str(args.get("category")),
                metadata=metadata,
            )
            return self._to_jsonable(result)

        if tool_name == "governance.validate_change":
            scope = self._verified_scope(args, metadata)
            result = await service.validate_change(
                surface=str(args.get("surface") or ""),
                summary=str(args.get("summary") or ""),
                category=self._optional_str(args.get("category")),
                metadata={**metadata, **scope},
                fallback_mode=self._optional_str(args.get("fallback_mode")),
            )
            return self._to_jsonable(result)

        if tool_name == "governance.resolve_gap":
            scope = self._verified_scope(args, metadata)
            result = await service.resolve_gap(
                question=str(args.get("question") or ""),
                category=self._optional_str(args.get("category")),
                metadata=metadata,
                org_id=scope["org_id"],
                team_id=scope["team_id"],
                persona_id=scope["persona_id"],
                workspace_id=scope["workspace_id"],
                resolution_mode=self._optional_str(args.get("resolution_mode")),
            )
            return self._to_jsonable(result)

        raise ValueError(f"Unknown tool: {tool_name}")

    async def _ensure_service(self) -> GovernanceService:
        if self._governance_service is not None:
            return self._governance_service

        async with self._service_lock:
            if self._governance_service is not None:
                return self._governance_service

            sqlite_path = str(
                self.config.settings.get("sqlite_path")
                or self.config.settings.get("db_path")
                or "Databases/governance.db"
            )
            db_parent = Path(sqlite_path).expanduser().resolve().parent
            db_parent.mkdir(parents=True, exist_ok=True)

            self._store = GovernanceStore(sqlite_path=sqlite_path)
            await self._store.ensure_schema()
            self._governance_service = GovernanceService(store=self._store)
            return self._governance_service

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None:
            return None
        rendered = str(value).strip()
        return rendered or None

    def _verified_scope(self, args: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
        verified = {
            "org_id": self._optional_int(metadata.get("org_id")),
            "team_id": self._optional_int(metadata.get("team_id")),
            "persona_id": self._optional_str(metadata.get("persona_id")),
            "workspace_id": self._optional_str(metadata.get("workspace_id")),
        }
        for field, expected in verified.items():
            provided = args.get(field)
            if provided is None or expected is None:
                continue
            if str(provided) != str(expected):
                raise PermissionError(f"{field} must match authenticated context")
        return {
            "org_id": verified["org_id"] if verified["org_id"] is not None else self._optional_int(args.get("org_id")),
            "team_id": verified["team_id"] if verified["team_id"] is not None else self._optional_int(args.get("team_id")),
            "persona_id": verified["persona_id"] if verified["persona_id"] is not None else self._optional_str(args.get("persona_id")),
            "workspace_id": verified["workspace_id"] if verified["workspace_id"] is not None else self._optional_str(args.get("workspace_id")),
        }

    @staticmethod
    def _merged_metadata(arguments: dict[str, Any], context: Any | None) -> dict[str, Any]:
        merged: dict[str, Any] = {}

        arg_metadata = arguments.get("metadata")
        if isinstance(arg_metadata, Mapping):
            merged.update(arg_metadata)

        context_metadata = getattr(context, "metadata", None)
        if isinstance(context_metadata, Mapping):
            for key, value in context_metadata.items():
                merged.setdefault(str(key), value)

        return merged

    @classmethod
    def _to_jsonable(cls, value: Any) -> Any:
        if is_dataclass(value):
            return cls._to_jsonable(asdict(value))
        if isinstance(value, dict):
            return {str(k): cls._to_jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._to_jsonable(v) for v in value]
        return value
