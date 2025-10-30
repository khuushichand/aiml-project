"""
Utilities for starting, monitoring, and stopping the FastAPI server used in CI workflows.

This script consolidates all lifecycle management so that GitHub Actions workflows can call
`python tldw_Server_API/scripts/server_lifecycle.py <command>` instead of embedding large
inline Python blocks.

Commands:
    start         Launch the server using environment configuration and record its PID/log.
    health-check  Poll the server's health endpoint until it responds or timeout occurs.
    stop          Terminate the server and clean up pid/log files.

All commands rely on the following environment variables (with sensible defaults):
    SERVER_LABEL         Distinguishes concurrently running servers ("single", "multi", etc.)
    E2E_TEST_BASE_URL    Base URL of the server (default http://127.0.0.1:8000).
    SERVER_PORT          Explicit port (takes precedence over URL port, default 8000).

The script is intentionally light on dependencies so it can run in GitHub runners without
additional packages.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PORT = "8000"
HEALTH_PATH = "/api/v1/health"
STARTUP_TIMEOUT_SECONDS = 120
POLL_INTERVAL_SECONDS = 2


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    return value if value is not None else default


def _paths(label: str) -> tuple[Path, Path]:
    pid_path = Path(f"server-{label}.pid")
    log_path = Path(f"server-{label}.log")
    return pid_path, log_path


def start_server() -> None:
    label = _env("SERVER_LABEL", "server")
    base_url = _env("E2E_TEST_BASE_URL", DEFAULT_BASE_URL)
    port = _env("SERVER_PORT") or _extract_port_from_url(base_url) or DEFAULT_PORT

    pid_path, log_path = _paths(label)

    # If a previous PID file exists, attempt to stop it first to avoid port conflicts.
    if pid_path.exists():
        try:
            _stop_server_by_pid(pid_path)
        except Exception:
            pass

    env = os.environ.copy()
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "tldw_Server_API.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        port,
    ]

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=log_file,
            stderr=log_file,
        )
    pid_path.write_text(str(process.pid), encoding="utf-8")
    print(f"[server-lifecycle] Started server '{label}' (PID {process.pid}) on port {port}")


def health_check() -> None:
    label = _env("SERVER_LABEL", "server")
    base_url = _env("E2E_TEST_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    url = f"{base_url}{HEALTH_PATH}"
    deadline = time.time() + STARTUP_TIMEOUT_SECONDS

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    print(f"[server-lifecycle] Health check OK for '{label}'")
                    return
        except Exception:
            time.sleep(POLL_INTERVAL_SECONDS)

    _print_recent_logs(label)
    raise SystemExit(f"[server-lifecycle] Server '{label}' failed health check within timeout")


def stop_server() -> None:
    label = _env("SERVER_LABEL", "server")
    pid_path, log_path = _paths(label)

    if not pid_path.exists():
        print(f"[server-lifecycle] No PID file found for '{label}' (already stopped?)")
        return

    try:
        _stop_server_by_pid(pid_path)
        print(f"[server-lifecycle] Stopped server '{label}'")
    finally:
        pid_path.unlink(missing_ok=True)
        # Keep log file for debugging; do not remove automatically


def _stop_server_by_pid(pid_path: Path) -> None:
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except Exception:
        return

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return

    for _ in range(30):
        if not _process_alive(pid):
            return
        time.sleep(1)

    # Force kill if still running
    kill_signal = getattr(signal, "SIGKILL", signal.SIGTERM)
    try:
        os.kill(pid, kill_signal)
    except OSError:
        pass


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _extract_port_from_url(url: str) -> Optional[str]:
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.port:
            return str(parsed.port)
        if parsed.scheme == "http":
            return "80"
        if parsed.scheme == "https":
            return "443"
    except Exception:
        pass
    return None


def _print_recent_logs(label: str, lines: int = 200) -> None:
    _, log_path = _paths(label)
    if log_path.exists():
        tail = "".join(log_path.read_text(encoding="utf-8").splitlines(keepends=True)[-lines:])
        print(f"[server-lifecycle] ==== recent logs for '{label}' ====\n{tail}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the lifecycle of the FastAPI server used in CI.")
    parser.add_argument("command", choices={"start", "health-check", "stop"}, help="Lifecycle command to execute")
    args = parser.parse_args()

    if args.command == "start":
        start_server()
    elif args.command == "health-check":
        health_check()
    elif args.command == "stop":
        stop_server()
    else:
        parser.error(f"Unknown command {args.command}")


if __name__ == "__main__":
    main()
