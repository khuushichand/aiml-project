"""Helpers for rendering seatbelt profiles and launch environments."""

from __future__ import annotations

import json
import os
import shutil

_CONTROLLED_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
_RESERVED_ENV_KEYS = {"HOME", "PATH", "TMPDIR", "TMP", "TEMP", "PWD"}


def _escape_seatbelt_string(value: str) -> str:
    """Escape a string literal for seatbelt's S-expression profile syntax."""

    return json.dumps(str(value))[1:-1]


def render_seatbelt_profile(
    *,
    command_path: str,
    workspace_path: str,
    home_path: str,
    temp_path: str,
    network_policy: str,
) -> str:
    """Render a minimal seatbelt profile for trusted host-local subprocesses."""

    if str(network_policy or "deny_all").strip().lower() == "allowlist":
        raise ValueError("allowlist network policy is not supported for seatbelt")

    lines = [
        "(version 1)",
        "(deny default)",
        '(import "system.sb")',
        "(allow process-fork)",
        '(allow process-exec (literal "{}"))'.format(_escape_seatbelt_string(command_path)),
        "(allow signal (target self))",
        "(allow sysctl-read)",
        "(allow file-read-data file-read-metadata",
        '       (literal "{}")'.format(_escape_seatbelt_string(command_path)),
        '       (subpath "{}")'.format(_escape_seatbelt_string(workspace_path)),
        '       (subpath "{}")'.format(_escape_seatbelt_string(home_path)),
        '       (subpath "{}")'.format(_escape_seatbelt_string(temp_path)),
        '       (subpath "/bin")',
        '       (subpath "/usr/bin")',
        '       (subpath "/usr/lib")',
        '       (subpath "/System"))',
        "(allow file-write*",
        '       (subpath "{}")'.format(_escape_seatbelt_string(workspace_path)),
        '       (subpath "{}")'.format(_escape_seatbelt_string(home_path)),
        '       (subpath "{}"))'.format(_escape_seatbelt_string(temp_path)),
        "(deny network*)",
        "",
    ]
    return "\n".join(lines)


def build_seatbelt_env(
    *,
    workspace_path: str,
    home_path: str,
    temp_path: str,
    spec_env: dict[str, str] | None,
) -> dict[str, str]:
    """Build a curated subprocess environment for seatbelt execution."""

    env: dict[str, str] = {
        "PATH": _CONTROLLED_PATH,
        "HOME": home_path,
        "TMPDIR": temp_path,
        "TMP": temp_path,
        "TEMP": temp_path,
        "PWD": workspace_path,
    }
    for key, value in (spec_env or {}).items():
        if key in _RESERVED_ENV_KEYS:
            continue
        env[str(key)] = str(value)
    return env


def resolve_command_argv(command: list[str], env_path: str) -> list[str]:
    """Resolve the executable in an argv command using a controlled PATH."""

    if not command:
        raise ValueError("command must not be empty")

    executable = str(command[0] or "").strip()
    if not executable:
        raise ValueError("command executable must not be empty")

    if os.path.isabs(executable):
        resolved = executable
    else:
        resolved = shutil.which(executable, path=env_path)
        if not resolved:
            raise FileNotFoundError(f"command not found in PATH: {executable}")

    return [resolved, *command[1:]]
