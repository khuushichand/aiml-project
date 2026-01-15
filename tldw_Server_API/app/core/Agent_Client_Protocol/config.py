from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from tldw_Server_API.app.core.config import get_config_section


@dataclass
class ACPRunnerConfig:
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    startup_timeout_sec: float = 10.0


def _parse_args(raw: Optional[str]) -> List[str]:
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


def _parse_env(raw: Optional[str]) -> Dict[str, str]:
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
    env: Dict[str, str] = {}
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
        try:
            timeout_sec = float(timeout_raw) / 1000.0
        except (TypeError, ValueError):
            pass

    return ACPRunnerConfig(
        command=str(command or ""),
        args=_parse_args(args_raw),
        env=_parse_env(env_raw),
        cwd=str(cwd) if cwd else None,
        startup_timeout_sec=timeout_sec,
    )
