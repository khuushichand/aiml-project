"""MCP module exposing the phase-1 virtual CLI `run` tool."""

from __future__ import annotations

import time
from typing import Any, Mapping

from loguru import logger

from ...command_runtime.adapters import (
    AdapterContext,
    PhaseOneCommandAdapters,
    PreflightCommandError,
    run_help_text,
    visible_command_registry,
)
from ...command_runtime.executor import CommandBackend, CommandRuntimeExecutor
from ...command_runtime.models import CommandExecutionResult, CommandStepResult
from ...command_runtime.parser import parse_command
from ...command_runtime.presentation import present_command_execution_result
from ...command_runtime.registry import CommandDescriptor, CommandRegistry, build_default_registry
from ..base import BaseModule, ModuleConfig, create_tool_definition

RUN_PARENT_IDEMPOTENCY_KEY_METADATA_KEY = "run_parent_idempotency_key"

_RUN_WRITE_BACKEND_TOOLS = {"fs.write_text", "sandbox.run"}


class _AdapterBackend(CommandBackend):
    def __init__(self, adapters: PhaseOneCommandAdapters) -> None:
        self._adapters = adapters

    async def execute(self, argv: list[str], stdin: Any) -> CommandStepResult:
        return await self._adapters.execute(argv, stdin)


class RunCommandModule(BaseModule):
    """Expose a policy-aware virtual CLI through MCP tool `run`."""

    def __init__(self, config: ModuleConfig) -> None:
        super().__init__(config)
        self._registry: CommandRegistry = build_default_registry()

    async def on_initialize(self) -> None:
        logger.info(f"Initializing run command module: {self.name}")

    async def on_shutdown(self) -> None:
        logger.info(f"Shutting down run command module: {self.name}")

    async def check_health(self) -> dict[str, bool]:
        return {"initialized": True}

    async def get_tools(self) -> list[dict[str, Any]]:
        run_tool = create_tool_definition(
            name="run",
            description="Execute a governed command in the MCP virtual CLI runtime.",
            parameters={
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command chain to execute (example: ls | grep py).",
                    },
                    "idempotencyKey": {
                        "type": "string",
                        "description": "Optional parent idempotency key for nested governed steps.",
                    },
                },
                "required": ["command"],
            },
            metadata={
                "category": "utility",
                "notes": "Wrapper tool; nested prepared MCP calls carry path/process metadata",
            },
        )
        run_tool["inputSchema"]["additionalProperties"] = False
        return [run_tool]

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any], context: Any | None = None) -> Any:
        if tool_name != "run":
            raise ValueError(f"Unknown tool: {tool_name}")
        args = self.sanitize_input(arguments or {})
        self.validate_tool_arguments(tool_name, args)

        command_text = str(args.get("command") or "").strip()
        visible = await self._visible_commands_for_context(context)
        if command_text in {"help", "--help"}:
            return present_command_execution_result(
                CommandExecutionResult(
                    stdout=run_help_text(visible),
                    stderr="",
                    exit_code=0,
                    duration_ms=0.0,
                )
            )

        start = time.perf_counter()
        try:
            chain = parse_command(command_text)
        except ValueError as exc:
            return present_command_execution_result(
                CommandExecutionResult(
                    stdout="",
                    stderr=str(exc),
                    exit_code=2,
                    duration_ms=max(0.0, (time.perf_counter() - start) * 1000.0),
                )
            )

        protocol = await self._resolve_protocol()
        adapter_context = AdapterContext(
            protocol=protocol,
            request_context=context,
            visible_commands=visible,
            parent_idempotency_key=self._parent_idempotency_key(context, arguments),
        )
        adapters = PhaseOneCommandAdapters(adapter_context)
        executor = CommandRuntimeExecutor(backend=_AdapterBackend(adapters))
        try:
            if adapters.requires_whole_chain_preflight(chain):
                await adapters.preflight_chain(chain)
            result = await executor.execute(chain)
        except PreflightCommandError as exc:
            result = CommandExecutionResult(
                stdout="",
                stderr=exc.result.stderr,
                exit_code=exc.result.exit_code,
                duration_ms=max(0.0, (time.perf_counter() - start) * 1000.0),
            )
        except ValueError as exc:
            result = CommandExecutionResult(
                stdout="",
                stderr=str(exc),
                exit_code=2,
                duration_ms=max(0.0, (time.perf_counter() - start) * 1000.0),
            )
        return present_command_execution_result(result)

    def validate_tool_arguments(self, tool_name: str, arguments: dict[str, Any]) -> None:
        if tool_name != "run":
            raise ValueError(f"Unknown tool: {tool_name}")
        unknown = sorted({key for key in arguments.keys()} - {"command", "idempotencyKey"})
        if unknown:
            raise ValueError(f"unknown arguments: {', '.join(unknown)}")
        command = arguments.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command is required")
        idempotency_key = arguments.get("idempotencyKey")
        if idempotency_key is not None and not isinstance(idempotency_key, str):
            raise ValueError("idempotencyKey must be a string")

    def sanitize_input(self, input_data: Any, _depth: int = 0) -> Any:
        """Sanitize input while allowing CLI flags like `--help` and shell-like tokens."""

        if _depth > 20:
            raise ValueError("Input too deeply nested")

        def _clean_string(value: str) -> str:
            cleaned = []
            for ch in value:
                if ch == "\n" or ch == "\t" or ch >= " ":
                    cleaned.append(ch)
            return "".join(cleaned)

        if isinstance(input_data, str):
            return _clean_string(input_data)
        if isinstance(input_data, dict):
            return {k: self.sanitize_input(v, _depth + 1) for k, v in input_data.items()}
        if isinstance(input_data, list):
            return [self.sanitize_input(v, _depth + 1) for v in input_data]
        return input_data

    def is_write_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_def: dict[str, Any] | None = None,
    ) -> bool:
        if tool_name != "run":
            return super().is_write_tool_call(tool_name, arguments, tool_def=tool_def)

        command = str(arguments.get("command") or "").strip()
        if not command or command in {"help", "--help"}:
            return False
        try:
            chain = parse_command(command)
        except ValueError:
            return False

        for segment in chain.segments:
            for invocation in segment.commands:
                if not invocation.argv:
                    continue
                try:
                    descriptor = self._registry.get_command(invocation.argv[0])
                except KeyError:
                    continue
                if any(tool in _RUN_WRITE_BACKEND_TOOLS for tool in descriptor.backend_tools):
                    return True
        return False

    async def _resolve_protocol(self) -> Any:
        configured = self.config.settings.get("protocol")
        if configured is not None:
            return configured
        from ...protocol import MCPProtocol
        from ...server import get_mcp_server

        try:
            return get_mcp_server().protocol
        except Exception:
            return MCPProtocol()

    async def _visible_commands_for_context(self, context: Any | None) -> Mapping[str, CommandDescriptor]:
        protocol = await self._resolve_protocol()
        context_for_listing = context
        if context_for_listing is None:
            from ...protocol import RequestContext

            context_for_listing = RequestContext(request_id="run-module")
        tools_payload = await protocol._handle_tools_list({}, context_for_listing)
        tools_payload = await self._filter_tools_payload_for_context(
            protocol,
            tools_payload,
            context_for_listing,
        )
        return visible_command_registry(tools_payload=tools_payload, registry=self._registry)

    async def _filter_tools_payload_for_context(
        self,
        protocol: Any,
        tools_payload: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        tools = tools_payload.get("tools")
        if not isinstance(tools, list):
            return tools_payload

        resolve_policy = getattr(protocol, "_resolve_effective_tool_policy", None)
        if callable(resolve_policy):
            effective_policy = await resolve_policy(context)
        else:
            effective_policy = None
        context_filter = getattr(protocol, "_is_tool_allowed_by_context", None)
        policy_filter = getattr(protocol, "_is_tool_allowed_by_effective_policy", None)

        filtered_tools: list[dict[str, Any]] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            name = tool.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            tool_args = {}
            if callable(context_filter) and not context_filter(name, tool_args, context):
                continue
            if callable(policy_filter) and not policy_filter(name, tool_args, effective_policy):
                continue
            filtered_tools.append(tool)
        return {"tools": filtered_tools}

    @staticmethod
    def _parent_idempotency_key(context: Any | None, arguments: dict[str, Any]) -> str | None:
        metadata = getattr(context, "metadata", None)
        if isinstance(metadata, dict):
            meta_value = metadata.get(RUN_PARENT_IDEMPOTENCY_KEY_METADATA_KEY)
            if isinstance(meta_value, str) and meta_value.strip():
                return meta_value.strip()

        for key in ("idempotency_key", "idempotencyKey"):
            value = arguments.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
