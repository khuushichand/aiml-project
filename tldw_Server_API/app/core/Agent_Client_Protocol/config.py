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
    binary_path: str | None = None


@dataclass
class ACPSandboxConfig:
    enabled: bool = False
    runtime: str = "docker"
    base_image: str = "tldw/acp-agent:latest"
    network_policy: str = "deny_all"
    allowed_egress_hosts: list[str] = field(default_factory=list)
    run_as_root: bool = False
    read_only_root: bool = True
    ssh_enabled: bool = True
    ssh_user: str = "acp"
    ssh_host: str = "127.0.0.1"
    ssh_container_port: int = 2222
    ssh_port_min: int = 2222
    ssh_port_max: int = 2299
    agent_command: str = ""
    agent_args: list[str] = field(default_factory=list)
    agent_env: dict[str, str] = field(default_factory=dict)

    # Session TTL and quotas
    session_ttl_seconds: int = 86400  # 24h default
    max_concurrent_sessions_per_user: int = 5
    max_tokens_per_session: int = 1_000_000
    max_session_duration_seconds: int = 14400  # 4h default
    audit_retention_days: int = 30


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
    binary_path = os.getenv("ACP_RUNNER_BINARY_PATH") or section.get("runner_binary_path")
    command = os.getenv("ACP_RUNNER_COMMAND") or section.get("runner_command", "")
    args_raw = os.getenv("ACP_RUNNER_ARGS") or section.get("runner_args", "")
    env_raw = os.getenv("ACP_RUNNER_ENV") or section.get("runner_env", "")
    cwd = os.getenv("ACP_RUNNER_CWD") or section.get("runner_cwd")

    # If binary_path is set, use it as the command directly (shortcut)
    if binary_path and not command:
        command = str(binary_path)
        args_raw = args_raw or ""
        cwd = cwd or None

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
        binary_path=str(binary_path) if binary_path else None,
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


def _parse_string_list(raw: str | None) -> list[str]:
    """Parse a comma-separated or JSON array string into a list of strings."""
    if not raw:
        return []
    text = raw.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return [s.strip() for s in text.split(",") if s.strip()]
        if isinstance(data, list):
            return [str(item) for item in data]
        return []
    return [s.strip() for s in text.split(",") if s.strip()]


def load_acp_sandbox_config() -> ACPSandboxConfig:
    section = get_config_section("ACP-SANDBOX")
    enabled = _parse_bool(os.getenv("ACP_SANDBOX_ENABLED") or section.get("enabled"), False)
    runtime = os.getenv("ACP_SANDBOX_RUNTIME") or section.get("runtime", "docker")
    base_image = os.getenv("ACP_SANDBOX_BASE_IMAGE") or section.get("base_image", "tldw/acp-agent:latest")
    network_policy = os.getenv("ACP_SANDBOX_NETWORK_POLICY") or section.get("network_policy", "deny_all")
    allowed_egress_raw = os.getenv("ACP_SANDBOX_ALLOWED_EGRESS_HOSTS") or section.get("allowed_egress_hosts", "")
    run_as_root = _parse_bool(os.getenv("ACP_SANDBOX_RUN_AS_ROOT") or section.get("run_as_root"), False)
    read_only_root = _parse_bool(os.getenv("ACP_SANDBOX_READ_ONLY_ROOT") or section.get("read_only_root"), True)
    ssh_enabled = _parse_bool(os.getenv("ACP_SSH_ENABLED") or section.get("ssh_enabled"), True)
    ssh_user = os.getenv("ACP_SSH_USER") or section.get("ssh_user", "acp")
    ssh_host = os.getenv("ACP_SSH_HOST") or section.get("ssh_host", "127.0.0.1")
    ssh_container_port = _parse_int(
        os.getenv("ACP_SSH_CONTAINER_PORT") or section.get("ssh_container_port"),
        2222,
    )
    ssh_port_min = _parse_int(os.getenv("ACP_SSH_PORT_MIN") or section.get("ssh_port_min"), 2222)
    ssh_port_max = _parse_int(os.getenv("ACP_SSH_PORT_MAX") or section.get("ssh_port_max"), 2299)
    agent_command = os.getenv("ACP_SANDBOX_AGENT_COMMAND") or section.get("agent_command", "")
    agent_args_raw = os.getenv("ACP_SANDBOX_AGENT_ARGS") or section.get("agent_args", "")
    agent_env_raw = os.getenv("ACP_SANDBOX_AGENT_ENV") or section.get("agent_env", "")

    # Session management config
    session_ttl = _parse_int(
        os.getenv("ACP_SESSION_TTL_SECONDS") or section.get("session_ttl_seconds"), 86400
    )
    max_concurrent = _parse_int(
        os.getenv("ACP_MAX_CONCURRENT_SESSIONS_PER_USER") or section.get("max_concurrent_sessions_per_user"), 5
    )
    max_tokens = _parse_int(
        os.getenv("ACP_MAX_TOKENS_PER_SESSION") or section.get("max_tokens_per_session"), 1_000_000
    )
    max_duration = _parse_int(
        os.getenv("ACP_MAX_SESSION_DURATION_SECONDS") or section.get("max_session_duration_seconds"), 14400
    )
    audit_retention = _parse_int(
        os.getenv("ACP_AUDIT_RETENTION_DAYS") or section.get("audit_retention_days"), 30
    )

    return ACPSandboxConfig(
        enabled=bool(enabled),
        runtime=str(runtime or "docker"),
        base_image=str(base_image or "tldw/acp-agent:latest"),
        network_policy=str(network_policy or "deny_all"),
        allowed_egress_hosts=_parse_string_list(allowed_egress_raw),
        run_as_root=bool(run_as_root),
        read_only_root=bool(read_only_root),
        ssh_enabled=bool(ssh_enabled),
        ssh_user=str(ssh_user or "acp"),
        ssh_host=str(ssh_host or "127.0.0.1"),
        ssh_container_port=int(ssh_container_port),
        ssh_port_min=int(ssh_port_min),
        ssh_port_max=int(ssh_port_max),
        agent_command=str(agent_command or ""),
        agent_args=_parse_args(agent_args_raw),
        agent_env=_parse_env(agent_env_raw),
        session_ttl_seconds=session_ttl,
        max_concurrent_sessions_per_user=max_concurrent,
        max_tokens_per_session=max_tokens,
        max_session_duration_seconds=max_duration,
        audit_retention_days=audit_retention,
    )
