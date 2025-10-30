from __future__ import annotations

import os
import shutil
from typing import Optional, List, Dict

from loguru import logger

from ..models import RunSpec, RunStatus, RunPhase
from ..streams import get_hub
from tldw_Server_API.app.core.config import settings as app_settings
import tempfile
import subprocess
from datetime import datetime
import threading
import time


def docker_available() -> bool:
    # Prefer explicit override for CI/tests; otherwise probe PATH
    env = os.getenv("TLDW_SANDBOX_DOCKER_AVAILABLE")
    if env is not None:
        return env.lower() in {"1", "true", "yes", "on"}
    return shutil.which("docker") is not None


class DockerRunner:
    """Stub Docker runner. Real container lifecycle management is out of scope for this scaffold.

    For now, this runner returns a NotImplementedError when invoked. Availability detection
    is provided for feature discovery endpoints.
    """

    def __init__(self) -> None:
        pass

    def _truthy(self, v: Optional[str]) -> bool:
        return bool(v) and str(v).strip().lower() in {"1", "true", "yes", "on", "y"}

    # Track active containers per run for cancellation
    _active_lock = threading.RLock()
    _active_cid: dict[str, str] = {}

    @classmethod
    def cancel_run(cls, run_id: str) -> bool:
        with cls._active_lock:
            cid = cls._active_cid.get(run_id)
        if not cid:
            return False
        # TERM -> grace -> KILL semantics
        try:
            try:
                grace = int(getattr(app_settings, "SANDBOX_CANCEL_GRACE_SECONDS", 3))
            except Exception:
                grace = 3

            # Send SIGTERM first
            try:
                subprocess.run(["docker", "kill", "--signal", "TERM", cid], check=False)
            except Exception:
                pass

            # Wait up to grace seconds for container to stop
            deadline = time.time() + max(0, grace)
            while time.time() < deadline:
                if not cls._is_container_running(cid):
                    break
                time.sleep(0.1)

            # If still running, send SIGKILL
            if cls._is_container_running(cid):
                try:
                    subprocess.run(["docker", "kill", cid], check=False)
                except Exception:
                    pass

            # Remove container
            try:
                subprocess.run(["docker", "rm", "-f", cid], check=False)
            except Exception:
                pass
        finally:
            with cls._active_lock:
                cls._active_cid.pop(run_id, None)
        # Do not publish WS end here; service layer will publish to avoid duplicates
        return True

    @staticmethod
    def _is_container_running(cid: str) -> bool:
        try:
            out = subprocess.check_output(["docker", "inspect", "-f", "{{.State.Running}}", cid], text=True, stderr=subprocess.DEVNULL).strip().lower()
            return out == "true"
        except Exception:
            return False

    def start_run(self, run_id: str, spec: RunSpec, session_workspace: Optional[str] = None) -> RunStatus:
        logger.debug(f"DockerRunner.start_run called with spec: {spec}")
        # Fake mode for tests/CI without Docker
        if self._truthy(os.getenv("TLDW_SANDBOX_DOCKER_FAKE_EXEC")):
            now = datetime.utcnow()
            try:
                get_hub().publish_event(run_id, "start", {"ts": now.isoformat()})
                get_hub().publish_event(run_id, "end", {"exit_code": 0})
            except Exception:
                pass
            return RunStatus(
                id="",  # caller should set id
                phase=RunPhase.completed,
                started_at=now,
                finished_at=now,
                exit_code=0,
                message="Docker fake execution",
            )

        if not docker_available():
            raise RuntimeError("Docker is not available on host")

        # Startup timeout budget
        try:
            startup_budget = int(spec.startup_timeout_sec) if spec.startup_timeout_sec else int(getattr(app_settings, "SANDBOX_DEFAULT_STARTUP_TIMEOUT_SEC", 20))
        except Exception:
            startup_budget = 20
        from datetime import datetime, timedelta
        deadline = datetime.utcnow() + timedelta(seconds=max(1, startup_budget))

        # Prepare tar stream from inline files (session workspace integration TBD)
        import io, tarfile, time
        tar_buf = io.BytesIO()
        with tarfile.open(fileobj=tar_buf, mode="w") as tf:
            # Session workspace files (if any)
            if session_workspace and os.path.isdir(session_workspace):
                base_len = len(session_workspace.rstrip("/"))
                for root, _dirs, files in os.walk(session_workspace):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        rel = fpath[base_len+1:]
                        try:
                            st = os.stat(fpath)
                            ti = tarfile.TarInfo(name=rel)
                            ti.size = st.st_size
                            ti.mtime = int(st.st_mtime)
                            with open(fpath, "rb") as rf:
                                tf.addfile(ti, rf)
                        except Exception as e:
                            logger.debug(f"Skipping workspace file {rel}: {e}")
            for (path, data) in (spec.files_inline or []):
                safe_path = path.lstrip("/\\").replace("..", "_")
                ti = tarfile.TarInfo(name=safe_path)
                ti.size = len(data)
                ti.mtime = int(time.time())
                tf.addfile(ti, io.BytesIO(data))
        tar_buf.seek(0)

        # Step 1: docker create
        cmd: List[str] = ["docker", "create"]
        # Network policy
        if (spec.network_policy or "deny_all").lower() == "deny_all":
            cmd += ["--network", "none"]
        # Resources
        try:
            pids_limit = int(getattr(app_settings, "SANDBOX_PIDS_LIMIT", 256))
        except Exception:
            pids_limit = 256
        cmd += ["--pids-limit", str(pids_limit)]
        if spec.cpu:
            cmd += ["--cpus", str(spec.cpu)]
        if spec.memory_mb:
            cmd += ["--memory", f"{int(spec.memory_mb)}m"]

        # Hardened security flags
        cmd += [
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
        ]
        # Optional seccomp/AppArmor (if configured). If no env is provided for seccomp,
        # try bundled default profile path.
        seccomp = os.getenv("SANDBOX_DOCKER_SECCOMP") or getattr(app_settings, "SANDBOX_DOCKER_SECCOMP", None)
        if not seccomp:
            try:
                project_root = getattr(app_settings, "PROJECT_ROOT", None)
                if project_root:
                    default_seccomp = os.path.join(project_root, "tldw_Server_API", "Config_Files", "sandbox", "seccomp_default.json")
                    if os.path.exists(default_seccomp):
                        seccomp = default_seccomp
            except Exception:
                seccomp = None
        security_opts: List[str] = []
        if seccomp:
            security_opts += ["--security-opt", f"seccomp={seccomp}"]
        apparmor_prof = os.getenv("SANDBOX_DOCKER_APPARMOR_PROFILE") or getattr(app_settings, "SANDBOX_DOCKER_APPARMOR_PROFILE", None)
        if apparmor_prof:
            security_opts += ["--security-opt", f"apparmor={apparmor_prof}"]
        cmd += security_opts

        # Ulimits (soft=hard)
        try:
            ul_nofile = int(getattr(app_settings, "SANDBOX_ULIMIT_NOFILE", 1024))
        except Exception:
            ul_nofile = 1024
        try:
            ul_nproc = int(getattr(app_settings, "SANDBOX_ULIMIT_NPROC", 512))
        except Exception:
            ul_nproc = 512
        # Always disable core dumps by default
        cmd += [
            "--ulimit", f"nofile={ul_nofile}:{ul_nofile}",
            "--ulimit", f"nproc={ul_nproc}:{ul_nproc}",
            "--ulimit", "core=0:0",
        ]

        # Random non-root UID/GID and tmpfs mounts with owners
        import random
        uid = random.randint(10000, 60000)
        gid = uid
        cmd += ["--user", f"{uid}:{gid}"]
        # tmpfs workdir and tmp
        ws_cap = int(getattr(app_settings, "SANDBOX_WORKSPACE_CAP_MB", 256))
        cmd += ["--tmpfs", f"/workspace:rw,noexec,nodev,nosuid,uid={uid},gid={gid},size={ws_cap}m"]
        cmd += ["--tmpfs", f"/tmp:rw,noexec,nodev,nosuid,uid={uid},gid={gid},size=64m"]
        # Working dir
        cmd += ["-w", "/workspace"]

        # Env vars (non-secret)
        env: Dict[str, str] = spec.env or {}
        for k, v in env.items():
            # basic sanitization: avoid newlines
            val = str(v).replace("\n", " ")
            cmd += ["-e", f"{k}={val}"]

        image = spec.base_image or "python:3.11-slim"
        cmd.append(image)
        if not spec.command:
            raise RuntimeError("No command provided for docker create/start")
        # Run in shell to ensure environment and path; safely quote user command
        import shlex
        user_cmd = " ".join(shlex.quote(x) for x in list(spec.command))
        shell_str = f"mkdir -p /workspace && exec {user_cmd}"
        cmd += ["sh", "-lc", shell_str]

        logger.info(f"Starting docker run: {' '.join(cmd)}")
        started = datetime.utcnow()
        hub = get_hub()
        max_log = None
        try:
            max_log = int(getattr(app_settings, "SANDBOX_MAX_LOG_BYTES", 10 * 1024 * 1024))
        except Exception:
            max_log = 10 * 1024 * 1024

        try:
            remaining = max(1, int((deadline - datetime.utcnow()).total_seconds()))
            cid = subprocess.check_output(cmd, text=True, timeout=remaining).strip()
        except FileNotFoundError:
            raise RuntimeError("docker binary not found in PATH")
        except subprocess.TimeoutExpired:
            finished = datetime.utcnow()
            hub.publish_event(run_id, "end", {"exit_code": None, "reason": "startup_timeout"})
            return RunStatus(
                id="",
                phase=RunPhase.timed_out,
                started_at=started,
                finished_at=finished,
                exit_code=None,
                message="startup_timeout",
            )
        except subprocess.CalledProcessError as e:
            # If security opts were provided, retry without them for portability (e.g., profile not loaded)
            if security_opts:
                try:
                    logger.warning(f"docker create failed with security options; retrying without them: {e}")
                    cmd_wo_sec = [c for c in cmd if c not in security_opts]
                    cid = subprocess.check_output(cmd_wo_sec, text=True).strip()
                except subprocess.CalledProcessError as e2:
                    raise RuntimeError(f"docker create failed (without security opts): {e2}")
            else:
                raise RuntimeError(f"docker create failed: {e}")

        # Register container for cancellation
        try:
            with DockerRunner._active_lock:
                DockerRunner._active_cid[run_id] = cid
        except Exception:
            pass

        # Step 2: copy session workspace and inline files using docker cp
        try:
            # Ensure /workspace exists via create flags; proceed to cp
            if session_workspace and os.path.isdir(session_workspace):
                remaining = max(1, int((deadline - datetime.utcnow()).total_seconds()))
                subprocess.check_call(["docker", "cp", f"{session_workspace}/.", f"{cid}:/workspace/"], timeout=remaining)
            # Stage inline files into a temp dir and copy
            if spec.files_inline:
                staging = tempfile.mkdtemp(prefix="tldw_inline_")
                try:
                    for (path, data) in (spec.files_inline or []):
                        safe_path = path.lstrip("/\\").replace("..", "_")
                        full = os.path.join(staging, safe_path)
                        os.makedirs(os.path.dirname(full), exist_ok=True)
                        with open(full, "wb") as f:
                            f.write(data)
                    remaining = max(1, int((deadline - datetime.utcnow()).total_seconds()))
                    subprocess.check_call(["docker", "cp", f"{staging}/.", f"{cid}:/workspace/"], timeout=remaining)
                finally:
                    try:
                        shutil.rmtree(staging, ignore_errors=True)
                    except Exception:
                        pass
        except subprocess.TimeoutExpired:
            # Cleanup container
            try:
                subprocess.check_call(["docker", "rm", "-f", cid])
            except Exception:
                pass
            finished = datetime.utcnow()
            hub.publish_event(run_id, "end", {"exit_code": None, "reason": "startup_timeout"})
            return RunStatus(
                id="",
                phase=RunPhase.timed_out,
                started_at=started,
                finished_at=finished,
                exit_code=None,
                message="startup_timeout",
            )
        except subprocess.CalledProcessError as e:
            # Cleanup container
            try:
                subprocess.check_call(["docker", "rm", "-f", cid])
            except Exception:
                pass
            raise RuntimeError(f"docker cp failed: {e}")

        # Step 3: start container and stream logs
        try:
            remaining = max(1, int((deadline - datetime.utcnow()).total_seconds()))
            subprocess.check_call(["docker", "start", cid], timeout=remaining)
        except subprocess.TimeoutExpired:
            try:
                subprocess.check_call(["docker", "rm", "-f", cid])
            except Exception:
                pass
            finished = datetime.utcnow()
            hub.publish_event(run_id, "end", {"exit_code": None, "reason": "startup_timeout"})
            return RunStatus(
                id="",
                phase=RunPhase.timed_out,
                started_at=started,
                finished_at=finished,
                exit_code=None,
                message="startup_timeout",
            )
        except subprocess.CalledProcessError as e:
            try:
                subprocess.check_call(["docker", "rm", "-f", cid])
            except Exception:
                pass
            raise RuntimeError(f"docker start failed: {e}")

        # Publish start event
        try:
            hub.publish_event(run_id, "start", {"ts": started.isoformat()})
        except Exception:
            pass

        # Stream logs via docker logs -f
        def _pump_logs():
            try:
                p = subprocess.Popen(["docker", "logs", "-f", cid], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                while True:
                    if p.stdout is not None:
                        data = p.stdout.readline()
                        if data:
                            hub.publish_stdout(run_id, data, max_log)
                    if p.stderr is not None:
                        data2 = p.stderr.readline()
                        if data2:
                            hub.publish_stderr(run_id, data2, max_log)
                    if p.poll() is not None and not (p.stdout and p.stdout.peek() or p.stderr and p.stderr.peek()):
                        break
            except Exception as _:
                return

        tlog = threading.Thread(target=_pump_logs, daemon=True)
        tlog.start()

        # Wait for container to finish
        timeout_sec = spec.timeout_sec or 300
        try:
            waited = subprocess.run(["docker", "wait", cid], capture_output=True, text=True, timeout=timeout_sec)
            try:
                exit_code = int(waited.stdout.strip()) if waited.stdout.strip() else 1
            except Exception:
                exit_code = waited.returncode if waited.returncode is not None else 1
        except subprocess.TimeoutExpired:
            try:
                subprocess.check_call(["docker", "kill", cid])
            except Exception:
                pass
            exit_code = None
            finished = datetime.utcnow()
            hub.publish_event(run_id, "end", {"exit_code": exit_code, "reason": "execution_timeout"})
            try:
                subprocess.check_call(["docker", "rm", "-f", cid])
            except Exception:
                pass
            return RunStatus(
                id="",
                phase=RunPhase.timed_out,
                started_at=started,
                finished_at=finished,
                exit_code=exit_code,
                message="execution_timeout",
            )

        # Join logs thread
        try:
            tlog.join(timeout=1)
        except Exception:
            pass

        finished = datetime.utcnow()
        # Resolve image digest (best-effort)
        image_digest: Optional[str] = None
        try:
            out = subprocess.check_output(["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True).strip()
            if out:
                image_digest = out
        except Exception:
            image_digest = None
        # Step 4: Collect artifacts via docker cp of workspace and filter by glob allowlist
        artifacts_map: dict[str, bytes] = {}
        try:
            if spec.capture_patterns:
                host_ws = tempfile.mkdtemp(prefix="tldw_ws_copy_")
                try:
                    subprocess.check_call(["docker", "cp", f"{cid}:/workspace/.", f"{host_ws}/"])
                    # Apply glob
                    import fnmatch
                    for root, _dirs, files in os.walk(host_ws):
                        for fname in files:
                            rel = os.path.relpath(os.path.join(root, fname), host_ws)
                            # match posix style
                            rel_posix = rel.replace(os.sep, "/")
                            if any(fnmatch.fnmatchcase(rel_posix, pat) for pat in (spec.capture_patterns or [])):
                                try:
                                    with open(os.path.join(host_ws, rel), "rb") as rf:
                                        data = rf.read()
                                    artifacts_map[rel_posix] = data
                                except Exception as e:
                                    logger.debug(f"Skip artifact {rel}: {e}")
                finally:
                    try:
                        shutil.rmtree(host_ws, ignore_errors=True)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Artifact collection failed: {e}")

        phase = RunPhase.completed if exit_code == 0 else RunPhase.failed
        msg = "Docker execution finished" if exit_code == 0 else f"Docker execution failed (exit={exit_code})"
        hub.publish_event(run_id, "end", {"exit_code": exit_code})
        try:
            subprocess.check_call(["docker", "rm", "-f", cid])
        except Exception:
            pass
        return RunStatus(
            id="",
            phase=phase,
            started_at=started,
            finished_at=finished,
            exit_code=exit_code,
            message=msg,
            image_digest=image_digest,
            artifacts=artifacts_map or None,
        )
