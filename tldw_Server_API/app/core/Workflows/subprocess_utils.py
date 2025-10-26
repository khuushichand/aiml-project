from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger


@dataclass
class SubprocessTask:
    cmd: List[str]
    workdir: Path
    stdout_path: Path
    stderr_path: Path
    pid: Optional[int] = None
    pgid: Optional[int] = None
    started_at: float = 0.0


def start_process(cmd: List[str], workdir: str | Path, log_dir: str | Path) -> SubprocessTask:
    """Start a subprocess in a new process group and log stdout/stderr to files.

    Returns a SubprocessTask with pid/pgid for later cancellation.
    """
    workdir = Path(workdir)
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = log_dir / "stdout.log"
    stderr_path = log_dir / "stderr.log"

    stdout_f = open(stdout_path, "ab", buffering=0)
    stderr_f = open(stderr_path, "ab", buffering=0)

    kwargs = {"cwd": str(workdir), "stdout": stdout_f, "stderr": stderr_f}

    # POSIX: create a new session -> new process group
    creationflags = 0
    if os.name == "posix":
        kwargs["start_new_session"] = True  # type: ignore[assignment]
    else:
        # Windows new process group
        import subprocess as sp
        creationflags = getattr(sp, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        kwargs["creationflags"] = creationflags  # type: ignore[assignment]

    proc = subprocess.Popen(cmd, **kwargs)
    pgid = None
    if os.name == "posix":
        try:
            pgid = os.getpgid(proc.pid)
        except Exception:
            pgid = None

    task = SubprocessTask(
        cmd=cmd,
        workdir=Path(workdir),
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        pid=proc.pid,
        pgid=pgid,
        started_at=time.time(),
    )
    logger.info(f"Started subprocess pid={task.pid} pgid={task.pgid} cmd={' '.join(cmd)}")
    return task


def terminate_process(task: SubprocessTask, grace_ms: int = 5000) -> Tuple[bool, bool]:
    """Terminate a subprocess process-group with escalation.

    Returns (terminated, forced_kill)
    """
    terminated = False
    forced = False
    try:
        if os.name == "posix" and task.pgid:
            try:
                os.killpg(task.pgid, signal.SIGTERM)
                time.sleep(grace_ms / 1000.0)
                # Check if group still alive: best-effort
                try:
                    os.killpg(task.pgid, 0)
                    os.killpg(task.pgid, signal.SIGKILL)
                    forced = True
                except ProcessLookupError:
                    pass
            except Exception as e:
                logger.warning(f"Failed to SIGTERM pgid={task.pgid}: {e}")
        elif task.pid:
            try:
                if os.name == "posix":
                    os.kill(task.pid, signal.SIGTERM)
                    time.sleep(grace_ms / 1000.0)
                    try:
                        os.kill(task.pid, 0)
                        os.kill(task.pid, signal.SIGKILL)
                        forced = True
                    except ProcessLookupError:
                        pass
                else:
                    # Windows: try CTRL_BREAK, then kill
                    try:
                        import signal as _sig
                        os.kill(task.pid, _sig.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
                    except Exception as e:
                        logger.debug(f"Subprocess terminate: CTRL_BREAK failed for pid={task.pid}: {e}")
                    time.sleep(grace_ms / 1000.0)
                    try:
                        os.kill(task.pid, signal.SIGTERM)
                    except Exception as e:
                        logger.debug(f"Subprocess terminate: SIGTERM failed for pid={task.pid}: {e}")
            except Exception as e:
                logger.warning(f"Failed to terminate pid={task.pid}: {e}")
        terminated = True
    except Exception as e:
        logger.error(f"Terminate process failed: {e}")
    return terminated, forced
