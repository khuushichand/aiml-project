"""
Sandbox Module for Unified MCP

Provides a management tool `sandbox.run` that triggers code execution via the
server's sandbox service. This is a stub-level integration intended to expose
the tool schema and a basic, policy-aware execution path per the PRD.

Notes:
- Write-capable tool; includes a custom validator.
- Execution uses the internal SandboxService scaffold; honors admin policy.
- For streaming logs or artifact downloads, clients should use the REST/WS endpoints.
"""

from __future__ import annotations

import base64
import binascii
from typing import Any

from loguru import logger

from ....Sandbox.models import RunSpec
from ....Sandbox.models import RuntimeType as SbxRuntimeType
from ....Sandbox.service import SandboxService
from ..base import BaseModule


class SandboxModule(BaseModule):
    async def on_initialize(self) -> None:
        logger.info(f"Initializing Sandbox module: {self.name}")
        self._svc = SandboxService()

    async def on_shutdown(self) -> None:
        logger.info(f"Shutting down Sandbox module: {self.name}")

    async def check_health(self) -> dict[str, bool]:
        checks = {"initialized": hasattr(self, "_svc") and self._svc is not None}
        # Minimal health: service scaffold exists
        return checks

    async def get_tools(self) -> list[dict[str, Any]]:
        # Return explicit schema with oneOf to reflect PRD (session vs one-shot)
        return [
            {
                "name": "sandbox.run",
                "description": "Execute a run in the code sandbox (Docker/Firecracker/Lima).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "runtime": {"type": "string", "enum": ["docker", "firecracker", "lima"]},
                        "session_id": {"type": "string"},
                        "base_image": {"type": "string"},
                        "command": {"type": "array", "items": {"type": "string"}},
                        "files": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "content_b64": {"type": "string"}
                                },
                                "required": ["path", "content_b64"],
                                "additionalProperties": False
                            }
                        },
                        "timeout_sec": {"type": "integer", "minimum": 1},
                        "env": {"type": "object"},
                        "persona_id": {"type": "string"},
                        "workspace_id": {"type": "string"},
                        "workspace_group_id": {"type": "string"},
                        "scope_snapshot_id": {"type": "string"},
                        "spec_version": {"type": "string"}
                    },
                    "oneOf": [
                        {"required": ["session_id", "command"]},
                        {"required": ["base_image", "command"]}
                    ],
                    "additionalProperties": False
                },
                # Categorize as management to enable policy enforcement and validator checks
                "metadata": {"category": "management", "notes": "Session-based vs one-shot per PRD"}
            }
        ]

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any], context: Any | None = None) -> Any:
        args = self.sanitize_input(arguments)
        if tool_name != "sandbox.run":
            raise ValueError(f"Unknown tool: {tool_name}")
        # Validate strictly (write-capable tool)
        self.validate_tool_arguments(tool_name, args)

        # Prepare RunSpec
        runtime_raw = (args.get("runtime") or "").strip().lower()
        runtime: SbxRuntimeType | None = None
        if runtime_raw in ("docker", "firecracker", "lima"):
            runtime = SbxRuntimeType(runtime_raw)
        # files (inline)
        files_inline: list[tuple[str, bytes]] = []
        for f in (args.get("files") or []):
            try:
                p = str(f.get("path", ""))
                b64 = str(f.get("content_b64", ""))
                data = base64.b64decode(b64)
                files_inline.append((p, data))
            except (TypeError, ValueError, binascii.Error, AttributeError) as exc:
                logger.debug("sandbox.run: skipping invalid inline file payload: {}", exc)
                continue
        command = [str(x) for x in (args.get("command") or [])]
        env = args.get("env") or {}
        if not isinstance(env, dict):
            env = {}
        timeout = int(args.get("timeout_sec") or 300)
        spec = RunSpec(
            session_id=args.get("session_id"),
            runtime=runtime,
            base_image=args.get("base_image"),
            command=command,
            env={str(k): str(v) for k, v in env.items()},
            timeout_sec=timeout,
            cpu=None,
            memory_mb=None,
            network_policy=None,
            files_inline=files_inline,
            capture_patterns=[],
            persona_id=(str(args.get("persona_id")) if args.get("persona_id") is not None else None),
            workspace_id=(str(args.get("workspace_id")) if args.get("workspace_id") is not None else None),
            workspace_group_id=(str(args.get("workspace_group_id")) if args.get("workspace_group_id") is not None else None),
            scope_snapshot_id=(str(args.get("scope_snapshot_id")) if args.get("scope_snapshot_id") is not None else None),
        )

        # Spec version
        spec_version = str(args.get("spec_version") or "1.0")
        # Idempotency optional
        idem_key = None
        try:
            idem_key = str(args.get("idempotency_key") or args.get("idempotencyKey") or "") or None
        except Exception:
            idem_key = None

        # Require authenticated principal binding; no synthetic fallback identity.
        user_id = getattr(context, "user_id", None) if context is not None else None
        if user_id is None or not str(user_id).strip():
            raise PermissionError("sandbox.run requires an authenticated user context")
        try:
            status = self._svc.start_run_scaffold(
                user_id=str(user_id),
                spec=spec,
                spec_version=spec_version,
                idem_key=idem_key,
                raw_body=args,
            )
        except Exception as e:
            raise RuntimeError(f"Sandbox execution failed: {e}") from e

        # Return a compact result for MCP
        def _iso(dt):
            try:
                return dt.isoformat() if dt else None
            except Exception:
                return None

        return {
            "id": status.id,
            "phase": status.phase.value,
            "exit_code": status.exit_code,
            "runtime": status.runtime.value if status.runtime else None,
            "base_image": status.base_image,
            "policy_hash": status.policy_hash,
            "image_digest": status.image_digest,
            "started_at": _iso(status.started_at),
            "finished_at": _iso(status.finished_at),
            "message": status.message,
            "session_id": status.session_id,
            "persona_id": status.persona_id,
            "workspace_id": status.workspace_id,
            "workspace_group_id": status.workspace_group_id,
            "scope_snapshot_id": status.scope_snapshot_id,
        }

    def sanitize_input(self, input_data: Any, _depth: int = 0) -> Any:
        """
        Relaxed sanitizer for sandbox payloads.

        Allows CLI-style args and comment tokens while still stripping control chars
        and guarding against overly deep payloads.
        """
        if _depth > 20:
            raise ValueError("Input too deeply nested")

        def _clean_str(s: str) -> str:
            # Strip NULs and control chars only.
            return "".join(ch for ch in s if ch >= " " or ch == "\n")

        if isinstance(input_data, str):
            return _clean_str(input_data)
        if isinstance(input_data, dict):
            return {k: self.sanitize_input(v, _depth + 1) for k, v in input_data.items()}
        if isinstance(input_data, list):
            return [self.sanitize_input(v, _depth + 1) for v in input_data]
        return input_data

    def validate_tool_arguments(self, tool_name: str, arguments: dict[str, Any]):
        # Enforce PRD oneOf and types
        cmd = arguments.get("command")
        sess = arguments.get("session_id")
        img = arguments.get("base_image")
        if not isinstance(cmd, list) or not cmd or not all(isinstance(x, str) and x for x in cmd):
            raise ValueError("command must be a non-empty array of strings")
        if not ((isinstance(sess, str) and sess) or (isinstance(img, str) and img)):
            raise ValueError("Either session_id or base_image is required")
        if (isinstance(sess, str) and sess) and (isinstance(img, str) and img):
            raise ValueError("Provide only one of session_id or base_image, not both")
        rt = arguments.get("runtime")
        if rt is not None and str(rt).lower() not in {"docker", "firecracker", "lima"}:
            raise ValueError("runtime must be docker|firecracker|lima when provided")
        if arguments.get("timeout_sec") is not None:
            try:
                ts = int(arguments.get("timeout_sec"))
                if ts <= 0:
                    raise ValueError
            except Exception:
                raise ValueError("timeout_sec must be a positive integer") from None
        files = arguments.get("files")
        if files is not None:
            if not isinstance(files, list):
                raise ValueError("files must be an array when provided")
            for i, f in enumerate(files):
                if not isinstance(f, dict) or not f.get("path") or not f.get("content_b64"):
                    raise ValueError(f"files[{i}] must include path and content_b64")
