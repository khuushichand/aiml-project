from __future__ import annotations

import contextlib
import json
import os
import shlex
from dataclasses import dataclass, field

from tldw_Server_API.app.core.config import get_config_section
from tldw_Server_API.app.core.testing import is_truthy


@dataclass
class ACPRunnerConfig:
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    startup_timeout_sec: float = 10.0


@dataclass
class ACPSandboxConfig:
    enabled: bool = False
    runtime: str = "docker"
    base_image: str = "tldw/acp-agent:latest"
    network_policy: str = "allow_all"
    ssh_enabled: bool = True
    ssh_user: str = "acp"
    ssh_host: str = "127.0.0.1"
    ssh_port_min: int = 2222
    ssh_port_max: int = 2299
    agent_command: str = ""
    agent_args: list[str] = field(default_factory=list)
    agent_env: dict[str, str] = field(default_factory=dict)


def _parse_args(raw: str | None) -> list[str]:
    if not raw:
        return []
    text = raw.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return shlex.split(text)
        if isinstance(data, list):
            return [str(item) for item in data]
        return []
    return shlex.split(text)


def _parse_env(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    text = raw.strip()
    if not text:
        return {}
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        return {}
    pairs = [seg.strip() for seg in text.split(",") if seg.strip()]
    env: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        key = key.strip()
        if not key:
            continue
        env[key] = value.strip()
    return env


def load_acp_runner_config() -> ACPRunnerConfig:
    section = get_config_section("ACP")
    command = os.getenv("ACP_RUNNER_COMMAND") or section.get("runner_command", "")
    args_raw = os.getenv("ACP_RUNNER_ARGS") or section.get("runner_args", "")
    env_raw = os.getenv("ACP_RUNNER_ENV") or section.get("runner_env", "")
    cwd = os.getenv("ACP_RUNNER_CWD") or section.get("runner_cwd")

    timeout_raw = os.getenv("ACP_RUNNER_STARTUP_TIMEOUT_MS") or section.get(
        "startup_timeout_ms"
    )
    timeout_sec = 10.0
    if timeout_raw:
        with contextlib.suppress(TypeError, ValueError):
            timeout_sec = float(timeout_raw) / 1000.0

    return ACPRunnerConfig(
        command=str(command or ""),
        args=_parse_args(args_raw),
        env=_parse_env(env_raw),
        cwd=str(cwd) if cwd else None,
        startup_timeout_sec=timeout_sec,
    )


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return is_truthy(raw)


def _parse_int(raw: str | None, default: int) -> int:
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def load_acp_sandbox_config() -> ACPSandboxConfig:
    section = get_config_section("ACP-SANDBOX")
    enabled = _parse_bool(os.getenv("ACP_SANDBOX_ENABLED") or section.get("enabled"), False)
    runtime = os.getenv("ACP_SANDBOX_RUNTIME") or section.get("runtime", "docker")
    base_image = os.getenv("ACP_SANDBOX_BASE_IMAGE") or section.get("base_image", "tldw/acp-agent:latest")
    network_policy = os.getenv("ACP_SANDBOX_NETWORK_POLICY") or section.get("network_policy", "allow_all")
    ssh_enabled = _parse_bool(os.getenv("ACP_SSH_ENABLED") or section.get("ssh_enabled"), True)
    ssh_user = os.getenv("ACP_SSH_USER") or section.get("ssh_user", "acp")
    ssh_host = os.getenv("ACP_SSH_HOST") or section.get("ssh_host", "127.0.0.1")
    ssh_port_min = _parse_int(os.getenv("ACP_SSH_PORT_MIN") or section.get("ssh_port_min"), 2222)
    ssh_port_max = _parse_int(os.getenv("ACP_SSH_PORT_MAX") or section.get("ssh_port_max"), 2299)
    agent_command = os.getenv("ACP_SANDBOX_AGENT_COMMAND") or section.get("agent_command", "")
    agent_args_raw = os.getenv("ACP_SANDBOX_AGENT_ARGS") or section.get("agent_args", "")
    agent_env_raw = os.getenv("ACP_SANDBOX_AGENT_ENV") or section.get("agent_env", "")

    return ACPSandboxConfig(
        enabled=bool(enabled),
        runtime=str(runtime or "docker"),
        base_image=str(base_image or "tldw/acp-agent:latest"),
        network_policy=str(network_policy or "allow_all"),
        ssh_enabled=bool(ssh_enabled),
        ssh_user=str(ssh_user or "acp"),
        ssh_host=str(ssh_host or "127.0.0.1"),
        ssh_port_min=int(ssh_port_min),
        ssh_port_max=int(ssh_port_max),
        agent_command=str(agent_command or ""),
        agent_args=_parse_args(agent_args_raw),
        agent_env=_parse_env(agent_env_raw),
    )
