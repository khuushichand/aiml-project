"""Phase-1 command adapters for the MCP-backed virtual CLI runtime."""

from __future__ import annotations

import difflib
import hashlib
import json
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .models import CommandChain, CommandSpillReference, CommandStepResult
from .registry import CommandDescriptor


@dataclass(slots=True)
class AdapterContext:
    """Execution context shared by all command adapters."""

    protocol: Any
    request_context: Any
    visible_commands: Mapping[str, CommandDescriptor]
    parent_idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class _GovernedCallPlan:
    tool_name: str
    arguments: dict[str, Any]
    renderer: Callable[[Any], str]


@dataclass(frozen=True, slots=True)
class _UsageError:
    message: str
    exit_code: int = 2


@dataclass(slots=True)
class _PreparedStep:
    prepared: Any
    plan: _GovernedCallPlan


class PreflightCommandError(Exception):
    """Raised when a preflighted command cannot be parsed/validated."""

    def __init__(self, result: CommandStepResult):
        super().__init__(result.stderr if isinstance(result.stderr, str) else "preflight command error")
        self.result = result


def normalize_step_content(argv: list[str]) -> str:
    """Return a deterministic normalized representation for one command step."""

    return json.dumps([str(part) for part in argv], ensure_ascii=False, separators=(",", ":"))


def derive_step_idempotency_key(parent_key: str | None, argv: list[str], step_index: int) -> str | None:
    """Derive deterministic nested idempotency key from parent key + normalized step."""

    base = str(parent_key or "").strip()
    if not base:
        return None
    normalized = normalize_step_content(argv)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{base}:step:{step_index}:{digest}"


def run_help_text(visible_commands: Mapping[str, CommandDescriptor]) -> str:
    """Render policy-filtered help for the run command surface."""

    lines = ["Virtual CLI commands available in this context:"]
    for name in sorted(visible_commands.keys()):
        descriptor = visible_commands[name]
        lines.append(f"  {name:9} {descriptor.summary}")
    return "\n".join(lines)


def visible_command_registry(
    *,
    tools_payload: dict[str, Any],
    registry: Any,
) -> dict[str, CommandDescriptor]:
    """Filter phase-1 commands by currently executable backing tools."""

    allowed_tools: set[str] = set()
    for tool in tools_payload.get("tools", []) or []:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        can_execute = tool.get("canExecute")
        if can_execute is False:
            continue
        allowed_tools.add(name.strip())
    return registry.visible_commands(allowed_tools)


class PhaseOneCommandAdapters:
    """Adapter layer that separates pure transforms from governed MCP tool calls."""

    def __init__(self, context: AdapterContext) -> None:
        self.context = context
        self._preflighted: dict[str, deque[_PreparedStep]] = {}
        self._next_step_index = 0

    def requires_whole_chain_preflight(self, chain: CommandChain) -> bool:
        """Return True when the chain includes any governed command."""

        for segment in chain.segments:
            for invocation in segment.commands:
                if not invocation.argv:
                    continue
                descriptor = self.context.visible_commands.get(invocation.argv[0])
                if descriptor is not None and not descriptor.pure_transform:
                    return True
        return False

    async def preflight_chain(self, chain: CommandChain) -> None:
        """Prepare all governed steps before execution starts."""

        step_index = 0
        for segment in chain.segments:
            for invocation in segment.commands:
                argv = list(invocation.argv)
                if not argv:
                    continue
                descriptor = self.context.visible_commands.get(argv[0])
                if descriptor is None:
                    raise PreflightCommandError(
                        self._unknown_command_result(argv[0])
                    )
                if descriptor.pure_transform:
                    step_index += 1
                    continue

                plan_or_error = self._governed_plan(argv)
                if isinstance(plan_or_error, _UsageError):
                    raise PreflightCommandError(
                        CommandStepResult(stderr=plan_or_error.message, exit_code=plan_or_error.exit_code)
                    )
                prepared = await self.context.protocol.prepare_tool_call(
                    params={"name": plan_or_error.tool_name, "arguments": dict(plan_or_error.arguments)},
                    context=self.context.request_context,
                    idempotency_key=derive_step_idempotency_key(
                        self.context.parent_idempotency_key,
                        argv,
                        step_index,
                    ),
                )
                signature = normalize_step_content(argv)
                bucket = self._preflighted.setdefault(signature, deque())
                bucket.append(_PreparedStep(prepared=prepared, plan=plan_or_error))
                step_index += 1

    async def execute(self, argv: list[str], stdin: Any) -> CommandStepResult:
        """Execute one command invocation for the runtime backend."""

        if not argv:
            return CommandStepResult(stderr="Missing command", exit_code=127)

        step_index = self._next_step_index
        self._next_step_index += 1
        descriptor = self.context.visible_commands.get(argv[0])
        if descriptor is None:
            return self._unknown_command_result(argv[0])

        if descriptor.pure_transform:
            return self._execute_pure_transform(argv, stdin)

        return await self._execute_governed(argv, step_index)

    async def _execute_governed(self, argv: list[str], step_index: int) -> CommandStepResult:
        signature = normalize_step_content(argv)
        bucket = self._preflighted.get(signature)
        if bucket:
            prepared_step = bucket.popleft()
        else:
            plan_or_error = self._governed_plan(argv)
            if isinstance(plan_or_error, _UsageError):
                return CommandStepResult(stderr=plan_or_error.message, exit_code=plan_or_error.exit_code)
            prepared = await self.context.protocol.prepare_tool_call(
                params={"name": plan_or_error.tool_name, "arguments": dict(plan_or_error.arguments)},
                context=self.context.request_context,
                idempotency_key=derive_step_idempotency_key(
                    self.context.parent_idempotency_key,
                    argv,
                    step_index,
                ),
            )
            prepared_step = _PreparedStep(prepared=prepared, plan=plan_or_error)

        payload = await self.context.protocol.execute_prepared_tool_call(prepared_step.prepared)
        rendered = prepared_step.plan.renderer(payload)
        return CommandStepResult(stdout=rendered, stderr="", exit_code=0)

    def _execute_pure_transform(self, argv: list[str], stdin: Any) -> CommandStepResult:
        command = argv[0]
        if command == "grep":
            return self._pure_grep(argv, stdin)
        if command == "head":
            return self._pure_head(argv, stdin)
        if command == "tail":
            return self._pure_tail(argv, stdin)
        if command == "json":
            return self._pure_json(argv, stdin)
        return CommandStepResult(stderr=f"Unknown command: {command}", exit_code=127)

    def _governed_plan(self, argv: list[str]) -> _GovernedCallPlan | _UsageError:
        command = argv[0]
        if command == "ls":
            if len(argv) > 2:
                return _UsageError("usage: ls [path]")
            path = argv[1] if len(argv) == 2 else "."
            return _GovernedCallPlan(
                tool_name="fs.list",
                arguments={"path": path},
                renderer=self._render_ls,
            )
        if command == "cat":
            if len(argv) != 2:
                return _UsageError("usage: cat <path>")
            return _GovernedCallPlan(
                tool_name="fs.read_text",
                arguments={"path": argv[1]},
                renderer=self._render_cat,
            )
        if command == "write":
            if len(argv) < 3:
                return _UsageError("usage: write <path> <content>")
            return _GovernedCallPlan(
                tool_name="fs.write_text",
                arguments={"path": argv[1], "content": " ".join(argv[2:])},
                renderer=self._render_write,
            )
        if command == "knowledge":
            return self._knowledge_plan(argv)
        if command == "media":
            return self._media_plan(argv)
        if command == "mcp":
            return self._mcp_plan(argv)
        if command == "sandbox":
            if len(argv) < 2:
                return _UsageError("usage: sandbox <command...>")
            return _GovernedCallPlan(
                tool_name="sandbox.run",
                arguments={"base_image": "python:3.11", "command": argv[1:]},
                renderer=self._render_json_payload,
            )
        return _UsageError(self._unknown_command_message(command), exit_code=127)

    def _knowledge_plan(self, argv: list[str]) -> _GovernedCallPlan | _UsageError:
        if len(argv) < 2:
            return _UsageError("usage: knowledge <search|get> ...")
        sub = argv[1]
        if sub == "search":
            if len(argv) < 3:
                return _UsageError("usage: knowledge search <query>")
            return _GovernedCallPlan(
                tool_name="knowledge.search",
                arguments={"query": " ".join(argv[2:])},
                renderer=self._render_json_payload,
            )
        if sub == "get":
            if len(argv) != 4:
                return _UsageError("usage: knowledge get <source> <id>")
            return _GovernedCallPlan(
                tool_name="knowledge.get",
                arguments={"source": argv[2], "id": self._coerce_scalar(argv[3])},
                renderer=self._render_json_payload,
            )
        return _UsageError("usage: knowledge <search|get> ...")

    def _media_plan(self, argv: list[str]) -> _GovernedCallPlan | _UsageError:
        if len(argv) < 2:
            return _UsageError("usage: media <search|get> ...")
        sub = argv[1]
        if sub == "search":
            if len(argv) < 3:
                return _UsageError("usage: media search <query>")
            return _GovernedCallPlan(
                tool_name="media.search",
                arguments={"query": " ".join(argv[2:])},
                renderer=self._render_json_payload,
            )
        if sub == "get":
            if len(argv) != 3:
                return _UsageError("usage: media get <media_id>")
            return _GovernedCallPlan(
                tool_name="media.get",
                arguments={"media_id": self._coerce_scalar(argv[2])},
                renderer=self._render_json_payload,
            )
        return _UsageError("usage: media <search|get> ...")

    def _mcp_plan(self, argv: list[str]) -> _GovernedCallPlan | _UsageError:
        if len(argv) != 2:
            return _UsageError("usage: mcp <tools|modules|catalogs>")
        sub = argv[1]
        if sub == "tools":
            return _GovernedCallPlan(
                tool_name="mcp.tools.list",
                arguments={},
                renderer=self._render_json_payload,
            )
        if sub == "modules":
            return _GovernedCallPlan(
                tool_name="mcp.modules.list",
                arguments={},
                renderer=self._render_json_payload,
            )
        if sub == "catalogs":
            return _GovernedCallPlan(
                tool_name="mcp.catalogs.list",
                arguments={},
                renderer=self._render_json_payload,
            )
        return _UsageError("usage: mcp <tools|modules|catalogs>")

    def _pure_grep(self, argv: list[str], stdin: Any) -> CommandStepResult:
        if len(argv) < 2:
            return CommandStepResult(stderr="usage: grep <pattern> [-i|--ignore-case]", exit_code=2)
        pattern = argv[1]
        flags = set(argv[2:])
        unsupported_flags = [flag for flag in flags if flag not in {"-i", "--ignore-case"}]
        if unsupported_flags:
            return CommandStepResult(stderr="usage: grep <pattern> [-i|--ignore-case]", exit_code=2)

        text = self._stdin_text(stdin)
        lines = text.splitlines()
        ignore_case = "-i" in flags or "--ignore-case" in flags
        needle = pattern.lower() if ignore_case else pattern
        matched: list[str] = []
        for line in lines:
            haystack = line.lower() if ignore_case else line
            if needle in haystack:
                matched.append(line)
        output = "\n".join(matched)
        if matched and text.endswith("\n"):
            output += "\n"
        return CommandStepResult(stdout=output, stderr="", exit_code=0 if matched else 1)

    def _pure_head(self, argv: list[str], stdin: Any) -> CommandStepResult:
        count_or_error = self._line_count_or_error(argv, default=10, usage="usage: head [count]")
        if isinstance(count_or_error, _UsageError):
            return CommandStepResult(stderr=count_or_error.message, exit_code=count_or_error.exit_code)
        text = self._stdin_text(stdin)
        return CommandStepResult(stdout=self._slice_head(text, count_or_error), stderr="", exit_code=0)

    def _pure_tail(self, argv: list[str], stdin: Any) -> CommandStepResult:
        count_or_error = self._line_count_or_error(argv, default=10, usage="usage: tail [count]")
        if isinstance(count_or_error, _UsageError):
            return CommandStepResult(stderr=count_or_error.message, exit_code=count_or_error.exit_code)
        text = self._stdin_text(stdin)
        return CommandStepResult(stdout=self._slice_tail(text, count_or_error), stderr="", exit_code=0)

    def _pure_json(self, argv: list[str], stdin: Any) -> CommandStepResult:
        if len(argv) > 2:
            return CommandStepResult(stderr="usage: json [path]", exit_code=2)
        text = self._stdin_text(stdin)
        if not text.strip():
            return CommandStepResult(stderr="json: stdin is required", exit_code=1)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            return CommandStepResult(stderr=f"json: invalid input ({exc.msg})", exit_code=1)

        if len(argv) == 1:
            return CommandStepResult(stdout=json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), stderr="", exit_code=0)

        path = argv[1]
        current: Any = payload
        for part in self._split_json_path(path):
            if isinstance(current, dict) and part in current:
                current = current[part]
                continue
            if isinstance(current, list) and part.isdigit():
                index = int(part)
                if 0 <= index < len(current):
                    current = current[index]
                    continue
            return CommandStepResult(stderr=f"json: path not found: {path}", exit_code=1)

        if isinstance(current, str):
            return CommandStepResult(stdout=current, stderr="", exit_code=0)
        return CommandStepResult(stdout=json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True), stderr="", exit_code=0)

    @staticmethod
    def _split_json_path(path: str) -> list[str]:
        normalized = path.strip().lstrip(".")
        if not normalized:
            return []

        parts: list[str] = []
        current: list[str] = []
        escaped = False
        for char in normalized:
            if escaped:
                current.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == ".":
                if current:
                    parts.append("".join(current))
                    current = []
                continue
            current.append(char)
        if escaped:
            current.append("\\")
        if current:
            parts.append("".join(current))
        return parts

    @staticmethod
    def _slice_head(text: str, count: int) -> str:
        if count <= 0:
            return ""
        lines = text.splitlines(keepends=True)
        return "".join(lines[:count])

    @staticmethod
    def _slice_tail(text: str, count: int) -> str:
        if count <= 0:
            return ""
        lines = text.splitlines(keepends=True)
        return "".join(lines[-count:])

    @staticmethod
    def _line_count_or_error(argv: list[str], *, default: int, usage: str) -> int | _UsageError:
        if len(argv) == 1:
            return default
        if len(argv) != 2:
            return _UsageError(usage)
        try:
            return max(0, int(argv[1]))
        except ValueError:
            return _UsageError(usage)

    @staticmethod
    def _coerce_scalar(value: str) -> int | float | str:
        try:
            if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
                return int(value)
            return float(value)
        except ValueError:
            return value

    @staticmethod
    def _stdin_text(stdin: Any) -> str:
        if isinstance(stdin, CommandSpillReference):
            try:
                return stdin.read_text()
            except OSError:
                return ""
        if isinstance(stdin, bytes):
            try:
                return stdin.decode("utf-8")
            except UnicodeDecodeError:
                return ""
        if stdin is None:
            return ""
        return str(stdin)

    @staticmethod
    def _extract_json_content(payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload
        content = payload.get("content")
        if not isinstance(content, list):
            return payload
        for item in content:
            if isinstance(item, dict) and item.get("type") == "json":
                return item.get("json")
        if len(content) == 1 and isinstance(content[0], dict) and "text" in content[0]:
            return content[0].get("text")
        return payload

    def _render_ls(self, payload: Any) -> str:
        decoded = self._extract_json_content(payload)
        if not isinstance(decoded, dict):
            return str(decoded)
        entries = decoded.get("entries")
        if not isinstance(entries, list):
            return str(decoded)
        lines: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                lines.append(str(entry))
                continue
            name = str(entry.get("name") or entry.get("path") or "")
            if not name:
                continue
            if str(entry.get("type") or "").lower() == "directory":
                name = f"{name}/"
            lines.append(name)
        if decoded.get("truncated") is True:
            remaining = decoded.get("remaining_count")
            if isinstance(remaining, int) and remaining > 0:
                lines.append(f"... truncated ({remaining} more entries)")
            else:
                lines.append("... truncated")
        return "\n".join(lines)

    def _render_cat(self, payload: Any) -> str:
        decoded = self._extract_json_content(payload)
        if isinstance(decoded, dict):
            text = decoded.get("text")
            return str(text or "")
        return str(decoded or "")

    def _render_write(self, payload: Any) -> str:
        decoded = self._extract_json_content(payload)
        if isinstance(decoded, dict):
            path = str(decoded.get("path") or "").strip()
            bytes_written = decoded.get("bytes_written")
            if path and isinstance(bytes_written, int):
                return f"wrote {bytes_written} bytes to {path}"
            if path:
                return f"wrote file: {path}"
        return str(decoded or "")

    def _render_json_payload(self, payload: Any) -> str:
        decoded = self._extract_json_content(payload)
        if isinstance(decoded, str):
            return decoded
        try:
            return json.dumps(decoded, ensure_ascii=False, indent=2, sort_keys=True)
        except TypeError:
            return str(decoded)

    def _unknown_command_result(self, command: str) -> CommandStepResult:
        return CommandStepResult(stderr=self._unknown_command_message(command), exit_code=127)

    def _unknown_command_message(self, command: str) -> str:
        available = sorted(self.context.visible_commands.keys())
        suggestions = difflib.get_close_matches(command, available, n=3, cutoff=0.3)
        if suggestions:
            return (
                f"Unknown command: {command}. "
                f"Did you mean: {', '.join(suggestions)}? "
                f"Available: {', '.join(available)}"
            )
        return f"Unknown command: {command}. Available: {', '.join(available)}"
