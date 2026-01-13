#!/usr/bin/env python3
"""
Smoke test: start the embeddings Redis worker and ensure it shuts down on signal.

This script:
- launches the Redis worker as a subprocess,
- waits briefly to confirm it stays up,
- sends SIGTERM or SIGINT,
- verifies the process exits within a timeout.

Requires a reachable Redis at REDIS_URL (or --redis-url).
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from typing import List, Optional


def _build_command(stage: str, python_bin: str) -> List[str]:
    """Build the Redis worker command line."""
    cmd = [
        python_bin,
        "-m",
        "tldw_Server_API.app.core.Embeddings.services.redis_worker",
        "--stage",
        stage,
    ]
    return cmd


def _send_signal(proc: subprocess.Popen[str], signal_name: str) -> None:
    """Send SIGTERM or SIGINT to the subprocess."""
    if signal_name == "int":
        proc.send_signal(signal.SIGINT)
    else:
        proc.send_signal(signal.SIGTERM)


def main() -> int:
    """Run the Redis worker shutdown smoke test."""
    parser = argparse.ArgumentParser(
        description="Smoke test embeddings Redis worker shutdown behavior",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--stage", choices=("chunking", "embedding", "storage", "content", "all"), default="all")
    parser.add_argument("--workers", type=int, help="Override workers per stage", default=None)
    parser.add_argument("--redis-url", help="Redis URL (sets REDIS_URL)", default=None)
    parser.add_argument("--startup-wait", type=float, help="Seconds to wait before signaling", default=3.0)
    parser.add_argument("--shutdown-timeout", type=float, help="Seconds to wait for shutdown", default=10.0)
    parser.add_argument("--signal", choices=("term", "int"), default="term", help="Signal to send")
    parser.add_argument("--python", default=sys.executable, help="Python executable for the subprocess")
    args = parser.parse_args()

    env = os.environ.copy()
    if args.redis_url:
        env["REDIS_URL"] = args.redis_url
    if args.workers is not None:
        if args.stage == "all":
            for stage in ("chunking", "embedding", "storage", "content"):
                env[f"EMBEDDINGS_REDIS_WORKERS_{stage.upper()}"] = str(args.workers)
        else:
            env[f"EMBEDDINGS_REDIS_WORKERS_{args.stage.upper()}"] = str(args.workers)
    env.setdefault("PYTHONUNBUFFERED", "1")

    cmd = _build_command(args.stage, args.python)
    print(f"[smoke] starting redis worker: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, env=env)

    time.sleep(max(0.0, args.startup_wait))
    if proc.poll() is not None:
        print(f"[smoke] orchestrator exited early with code {proc.returncode}")
        return 1

    print(f"[smoke] sending SIG{args.signal.upper()} to redis worker")
    _send_signal(proc, args.signal)

    try:
        proc.wait(timeout=max(0.1, args.shutdown_timeout))
    except subprocess.TimeoutExpired:
        print("[smoke] shutdown timed out; killing redis worker")
        proc.kill()
        proc.wait(timeout=5)
        return 2

    if proc.returncode != 0:
        print(f"[smoke] non-zero exit code after shutdown: {proc.returncode}")
        return 3

    print("[smoke] redis worker shut down cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
