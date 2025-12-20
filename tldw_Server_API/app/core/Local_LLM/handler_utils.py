"""Shared utilities for Local LLM handlers.

This module provides common functionality used by LlamaCpp, Llamafile, and other handlers:
- Environment variable parsing
- Port availability checking and auto-selection
- Path security validation
- Defensive logging
- CLI argument denylist for secrets
"""

from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from loguru import logger as default_logger

if TYPE_CHECKING:
    from loguru import Logger


# Unified denylist of CLI arguments that should not be passed directly
# (secrets should be passed via environment variables instead)
DEFAULT_SECRET_DENYLIST: Set[str] = {
    "hf_token",
    "token",
    "openai_api_key",
    "anthropic_api_key",
}


def env_bool(name: str) -> Optional[bool]:
    """Parse a boolean value from an environment variable.

    Returns True for "1", "true", "yes", "on" (case-insensitive).
    Returns False for "0", "false", "no", "off" (case-insensitive).
    Returns None if the variable is not set.
    """
    v = os.getenv(name)
    if v is None:
        return None
    v_lower = str(v).strip().lower()
    if v_lower in {"1", "true", "yes", "on"}:
        return True
    if v_lower in {"0", "false", "no", "off"}:
        return False
    return None


def env_int(name: str) -> Optional[int]:
    """Parse an integer value from an environment variable.

    Returns None if the variable is not set or cannot be parsed.
    """
    v = os.getenv(name)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def env_paths(name: str) -> Optional[List[Path]]:
    """Parse a comma-separated list of paths from an environment variable.

    Returns None if the variable is not set or empty.
    """
    v = os.getenv(name)
    if not v:
        return None
    parts = [p.strip() for p in v.split(",") if p.strip()]
    return [Path(p) for p in parts] if parts else None


def is_port_free(host: str, port: int) -> bool:
    """Check if a port is available for binding.

    Args:
        host: Host address to check (e.g., "127.0.0.1")
        port: Port number to check

    Returns:
        True if the port is free, False otherwise
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def pick_port(
    host: str,
    start_port: int,
    autoselect: bool = True,
    max_probe: int = 10,
) -> int:
    """Find an available port starting from start_port.

    Args:
        host: Host address to check
        start_port: Starting port number
        autoselect: If False, return start_port without checking
        max_probe: Maximum number of ports to probe

    Returns:
        An available port number, or start_port as fallback
    """
    if not autoselect:
        return start_port
    for i in range(max_probe + 1):
        candidate = start_port + i
        if is_port_free(host, candidate):
            return candidate
    return start_port  # Fallback


def is_path_allowed(
    path: Path,
    base_dirs: List[Path],
) -> bool:
    """Check if a path is under one of the allowed base directories.

    Uses os.path.realpath to fully resolve symlinks for security,
    preventing symlink-based path traversal attacks.

    Args:
        path: The path to check
        base_dirs: List of allowed base directories

    Returns:
        True if path is under one of the base directories, False otherwise
    """
    try:
        # Use realpath to fully resolve symlinks
        resolved_path = Path(os.path.realpath(str(path)))
    except Exception:
        return False

    for base in base_dirs:
        try:
            # Resolve symlinks in base dir too to prevent bypass
            resolved_base = Path(os.path.realpath(str(base)))
            resolved_path.relative_to(resolved_base)
            return True
        except (ValueError, Exception):
            continue
    return False


def build_allowed_paths(
    models_dir: Path,
    extra_paths: Optional[List[Path]] = None,
) -> List[Path]:
    """Build a list of allowed base paths for security checks.

    Args:
        models_dir: The primary models directory
        extra_paths: Optional additional allowed paths

    Returns:
        List of Path objects representing allowed directories
    """
    bases = [models_dir]
    if extra_paths:
        bases.extend(extra_paths)
    return bases


def check_denylist(
    args: Dict[str, Any],
    allow_secrets: bool = False,
    denylist: Optional[Set[str]] = None,
) -> None:
    """Check if any arguments are in the denylist.

    Args:
        args: Dictionary of arguments to check
        allow_secrets: If True, skip the check
        denylist: Set of denied argument names (uses DEFAULT_SECRET_DENYLIST if None)

    Raises:
        ValueError: If any denied arguments are found and allow_secrets is False
    """
    if allow_secrets:
        return

    deny = denylist if denylist is not None else DEFAULT_SECRET_DENYLIST
    bad = [k for k in args.keys() if k in deny]
    if bad:
        raise ValueError(
            f"Refusing secret flags {bad}. Set environment variables "
            f"(e.g., HF_TOKEN) instead, or enable allow_cli_secrets."
        )


def safe_log(
    log: "Logger",
    level: str,
    msg: str,
    *args,
) -> None:
    """Log defensively to avoid errors when sinks are closed during atexit.

    Args:
        log: Logger instance
        level: Log level (e.g., "info", "warning", "error")
        msg: Message to log
        *args: Additional arguments for the log message
    """
    try:
        log_fn = getattr(log, level, None)
        if callable(log_fn):
            log_fn(msg, *args)
    except Exception:
        # Swallow logging errors on interpreter shutdown / closed sinks
        pass


def apply_env_overrides(config: Any) -> None:
    """Apply environment variable overrides to a handler config.

    Checks for:
    - LOCAL_LLM_ALLOW_CLI_SECRETS
    - LOCAL_LLM_PORT_AUTOSELECT
    - LOCAL_LLM_PORT_PROBE_MAX
    - LOCAL_LLM_ALLOWED_PATHS

    Args:
        config: Handler config object to modify
    """
    b = env_bool("LOCAL_LLM_ALLOW_CLI_SECRETS")
    if b is not None:
        config.allow_cli_secrets = b

    b = env_bool("LOCAL_LLM_PORT_AUTOSELECT")
    if b is not None:
        config.port_autoselect = b

    i = env_int("LOCAL_LLM_PORT_PROBE_MAX")
    if i is not None:
        config.port_probe_max = i

    paths = env_paths("LOCAL_LLM_ALLOWED_PATHS")
    if paths is not None:
        config.allowed_paths = paths
