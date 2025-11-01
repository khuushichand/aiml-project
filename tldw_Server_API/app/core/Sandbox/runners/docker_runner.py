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
from datetime import datetime, timedelta
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
            # Collect basic usage from hub
            try:
                log_bytes_total = int(get_hub().get_log_bytes(run_id))
            except Exception:
                log_bytes_total = 0
            usage = {
                "cpu_time_sec": 0,
                "wall_time_sec": 0,
                "peak_rss_mb": 0,
                "log_bytes": int(log_bytes_total),
                "artifact_bytes": 0,
            }
            return RunStatus(
                id="",  # caller should set id
                phase=RunPhase.completed,
                started_at=now,
                finished_at=now,
                exit_code=0,
                message="Docker fake execution",
                resource_usage=usage,
            )

        if not docker_available():
            raise RuntimeError("Docker is not available on host")

        # Startup timeout budget
        try:
            startup_budget = int(spec.startup_timeout_sec) if spec.startup_timeout_sec else int(getattr(app_settings, "SANDBOX_DEFAULT_STARTUP_TIMEOUT_SEC", 20))
        except Exception:
            startup_budget = 20
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
            # Usage (no logs/artifacts expected yet)
            usage = {
                "cpu_time_sec": 0,
                "wall_time_sec": int(max(0.0, (finished - started).total_seconds())),
                "peak_rss_mb": 0,
                "log_bytes": int(get_hub().get_log_bytes(run_id)),
                "artifact_bytes": 0,
            }
            return RunStatus(
                id="",
                phase=RunPhase.timed_out,
                started_at=started,
                finished_at=finished,
                exit_code=None,
                message="startup_timeout",
                resource_usage=usage,
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
            # Attempt a best-effort CPU usage readback from cgroup before removal
            try:
                cpu_sec_cp = self._read_cgroup_cpu_time_sec_by_cid(cid)
            except Exception:
                cpu_sec_cp = None
            usage = {
                "cpu_time_sec": int(max(0, (cpu_sec_cp or 0))),
                "wall_time_sec": int(max(0.0, (finished - started).total_seconds())),
                "peak_rss_mb": 0,
                "log_bytes": int(get_hub().get_log_bytes(run_id)),
                "artifact_bytes": 0,
            }
            return RunStatus(
                id="",
                phase=RunPhase.timed_out,
                started_at=started,
                finished_at=finished,
                exit_code=None,
                message="startup_timeout",
                resource_usage=usage,
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
            finished = datetime.utcnow()
            hub.publish_event(run_id, "end", {"exit_code": None, "reason": "startup_timeout"})
            # Even if start timed out, try to read any cgroup CPU used (should be minimal)
            try:
                cpu_sec = self._read_cgroup_cpu_time_sec_by_cid(cid)
            except Exception:
                cpu_sec = None
            usage = {
                "cpu_time_sec": int(max(0, cpu_sec or 0)),
                "wall_time_sec": int(max(0.0, (finished - started).total_seconds())),
                "peak_rss_mb": 0,
                "log_bytes": int(get_hub().get_log_bytes(run_id)),
                "artifact_bytes": 0,
            }
            # Remove after collecting stats
            try:
                subprocess.check_call(["docker", "rm", "-f", cid])
            except Exception:
                pass
            return RunStatus(
                id="",
                phase=RunPhase.timed_out,
                started_at=started,
                finished_at=finished,
                exit_code=None,
                message="startup_timeout",
                resource_usage=usage,
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

        # Baseline CPU usage and resolved cgroup file after container start (best-effort)
        baseline_cpu_sec: Optional[int] = None
        baseline_cgroup_file: Optional[tuple[str, str]] = None  # (file_path, format: 'v1'|'v2')
        try:
            # Resolve cgroup stats file while container is running so we can reuse it later
            baseline_cgroup_file = self._resolve_cgroup_cpu_file_by_cid(cid)
            if baseline_cgroup_file is not None:
                baseline_cpu_sec = self._read_cpu_file_to_seconds(baseline_cgroup_file)
            else:
                baseline_cpu_sec = self._read_cgroup_cpu_time_sec_by_cid(cid)
        except Exception:
            baseline_cpu_sec = None

        # Stream logs via docker logs -f
        log_bytes_local = 0
        def _pump_logs():
            try:
                p = subprocess.Popen(["docker", "logs", "-f", cid], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                while True:
                    if p.stdout is not None:
                        data = p.stdout.readline()
                        if data:
                            hub.publish_stdout(run_id, data, max_log)
                            nonlocal log_bytes_local
                            log_bytes_local += len(data)
                    if p.stderr is not None:
                        data2 = p.stderr.readline()
                        if data2:
                            hub.publish_stderr(run_id, data2, max_log)
                            log_bytes_local += len(data2)
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
            # Take a last CPU snapshot while the container is still running, before SIGKILL
            prekill_cpu: Optional[int] = None
            try:
                if baseline_cgroup_file is not None:
                    prekill_cpu = self._read_cpu_file_to_seconds(baseline_cgroup_file)
                else:
                    prekill_cpu = self._read_cgroup_cpu_time_sec_by_cid(cid)
            except Exception:
                prekill_cpu = None

            # Kill, compute stats, then remove
            try:
                subprocess.check_call(["docker", "kill", cid])
            except Exception:
                pass
            exit_code = None
            finished = datetime.utcnow()
            hub.publish_event(run_id, "end", {"exit_code": exit_code, "reason": "execution_timeout"})
            # CPU time: prefer cgroup delta if baseline captured; use pre-kill snapshot first
            final_cpu: Optional[int] = prekill_cpu
            if final_cpu is None:
                try:
                    if baseline_cgroup_file is not None:
                        final_cpu = self._read_cpu_file_to_seconds(baseline_cgroup_file)
                    else:
                        final_cpu = self._read_cgroup_cpu_time_sec_by_cid(cid)
                except Exception:
                    final_cpu = None
            if baseline_cpu_sec is not None and final_cpu is not None:
                cpu_time_val = max(0, int(final_cpu - baseline_cpu_sec))
            else:
                cpu_time_val = self._get_cpu_time_sec(cid, started, finished)
            usage = {
                "cpu_time_sec": int(max(0, cpu_time_val)),
                "wall_time_sec": int(max(0.0, (finished - started).total_seconds())),
                "peak_rss_mb": self._get_mem_usage_mb(cid),
                "log_bytes": int(get_hub().get_log_bytes(run_id)),
                "artifact_bytes": 0,
            }
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
                resource_usage=usage,
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
        # Compute resource usage (best-effort) before removing container
        try:
            total_log = int(get_hub().get_log_bytes(run_id))
        except Exception:
            total_log = int(log_bytes_local)
        art_bytes = 0
        try:
            if artifacts_map:
                art_bytes = sum(len(v) for v in artifacts_map.values())
        except Exception:
            art_bytes = 0
        # CPU time: prefer cgroup delta when baseline available; reuse persisted cgroup file if present
        try:
            if baseline_cgroup_file is not None:
                final_cpu2 = self._read_cpu_file_to_seconds(baseline_cgroup_file)
            else:
                final_cpu2 = self._read_cgroup_cpu_time_sec_by_cid(cid)
        except Exception:
            final_cpu2 = None
        if baseline_cpu_sec is not None and final_cpu2 is not None:
            cpu_time = max(0, int(final_cpu2 - baseline_cpu_sec))
        else:
            cpu_time = self._get_cpu_time_sec(cid, started, finished)
        usage = {
            "cpu_time_sec": int(max(0, cpu_time)),
            "wall_time_sec": int(max(0.0, (finished - started).total_seconds())),
            "peak_rss_mb": self._get_mem_usage_mb(cid),
            "log_bytes": int(total_log),
            "artifact_bytes": int(art_bytes),
        }
        # Remove container after collecting stats
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
            resource_usage=usage,
        )

    @staticmethod
    def _read_cgroup_cpu_time_sec_by_cid(cid: str) -> Optional[int]:
        """Read absolute CPU time (seconds) from cgroup for a container by CID.

        Returns None if not available (non-Linux or permissions), so callers can fallback.
        """
        try:
            pid_out = subprocess.check_output(["docker", "inspect", cid, "--format", "{{.State.Pid}}"], text=True, timeout=3).strip()
            pid = int(pid_out)
            return DockerRunner._read_cgroup_cpu_time_sec_by_pid(pid)
        except Exception:
            return None

    @staticmethod
    def _read_cgroup_cpu_time_sec_by_pid(pid: int) -> Optional[int]:
        """Read absolute CPU time (seconds) from cgroup for a process PID.

        Supports cgroup v1 and v2; returns None if unavailable.
        """
        cgroups: Dict[str, str] = {}
        try:
            with open(f"/proc/{pid}/cgroup", "r") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if len(parts) == 3:
                        subsystems = parts[1]
                        path = parts[2]
                        cgroups[subsystems] = path
        except Exception:
            return None
        # cgroup v1
        path_v1 = None
        for key, val in cgroups.items():
            if "cpuacct" in key:
                path_v1 = val
                break
        if path_v1:
            cg_file = os.path.join("/sys/fs/cgroup", "cpuacct", path_v1.lstrip("/"), "cpuacct.usage")
            try:
                with open(cg_file, "r") as f:
                    ns = int(f.read().strip())
                    return int(ns / 1_000_000_000)
            except Exception:
                pass
        # cgroup v2
        path_v2 = cgroups.get("") or cgroups.get("0") or None
        if not path_v2:
            for key, val in cgroups.items():
                if key == "0":
                    path_v2 = val
                    break
        if path_v2:
            cg_file2 = os.path.join("/sys/fs/cgroup", path_v2.lstrip("/"), "cpu.stat")
            try:
                with open(cg_file2, "r") as f:
                    content = f.read()
                    for ln in content.splitlines():
                        if ln.startswith("usage_usec "):
                            usec = int(ln.split()[1])
                            return int(usec / 1_000_000)
            except Exception:
                pass
        return None

    @staticmethod
    def _resolve_cgroup_cpu_file_by_cid(cid: str) -> Optional[tuple[str, str]]:
        """Resolve the cgroup CPU stats file for a container by CID.

        Returns a tuple of (file_path, format), where format is 'v1' or 'v2'.
        Returns None if resolution fails.
        """
        try:
            pid_out = subprocess.check_output(["docker", "inspect", cid, "--format", "{{.State.Pid}}"], text=True, timeout=3).strip()
            pid = int(pid_out)
            return DockerRunner._resolve_cgroup_cpu_file_by_pid(pid)
        except Exception:
            return None

    @staticmethod
    def _resolve_cgroup_cpu_file_by_pid(pid: int) -> Optional[tuple[str, str]]:
        """Resolve the cgroup CPU stats file for a process PID.

        Returns (file_path, 'v1'|'v2') if found, else None.
        """
        cgroups: Dict[str, str] = {}
        try:
            with open(f"/proc/{pid}/cgroup", "r") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if len(parts) == 3:
                        subsystems = parts[1]
                        path = parts[2]
                        cgroups[subsystems] = path
        except Exception:
            return None

        # cgroup v1: cpuacct
        path_v1 = None
        for key, val in cgroups.items():
            if "cpuacct" in key:
                path_v1 = val
                break
        if path_v1:
            cg_file = os.path.join("/sys/fs/cgroup", "cpuacct", path_v1.lstrip("/"), "cpuacct.usage")
            return (cg_file, "v1")

        # cgroup v2 unified
        path_v2 = cgroups.get("") or cgroups.get("0") or None
        if not path_v2:
            for key, val in cgroups.items():
                if key == "0":
                    path_v2 = val
                    break
        if path_v2:
            cg_file2 = os.path.join("/sys/fs/cgroup", path_v2.lstrip("/"), "cpu.stat")
            return (cg_file2, "v2")
        return None

    @staticmethod
    def _read_cpu_file_to_seconds(file_info: tuple[str, str]) -> Optional[int]:
        """Read a previously resolved cgroup CPU stats file and return seconds.

        file_info is (file_path, 'v1'|'v2').
        - v1: cpuacct.usage (nanoseconds)
        - v2: cpu.stat with usage_usec line
        Returns None if read/parse fails.
        """
        path, fmt = file_info
        try:
            if fmt == "v1":
                with open(path, "r") as f:
                    ns = int(f.read().strip())
                    return int(ns / 1_000_000_000)
            elif fmt == "v2":
                with open(path, "r") as f:
                    content = f.read()
                    for ln in content.splitlines():
                        if ln.startswith("usage_usec "):
                            usec = int(ln.split()[1])
                            return int(usec / 1_000_000)
        except Exception:
            return None
        return None

    @staticmethod
    def _get_mem_usage_mb(cid: str) -> int:
        """Best-effort memory usage snapshot in MB using `docker stats --no-stream`.

        Returns 0 if stats are unavailable. This is not a true peak metric but
        offers a coarse indication of memory footprint.
        """
        try:
            out = subprocess.check_output(["docker", "stats", cid, "--no-stream", "--format", "{{.MemUsage}}"], text=True, timeout=3).strip()
            # Expect forms like "12.3MiB / 2.00GiB" or "800KiB / 2.00GiB"
            val = out.split("/")[0].strip()
            num_str, unit = DockerRunner._split_num_unit(val)
            num = float(num_str)
            unit_l = unit.lower()
            if unit_l.startswith("gb") or unit_l.startswith("gib"):
                return int(num * 1024)
            if unit_l.startswith("mb") or unit_l.startswith("mib"):
                return int(num)
            if unit_l.startswith("kb") or unit_l.startswith("kib"):
                return int(num / 1024)
            if unit_l.endswith("b"):
                return int(num / (1024 * 1024))
            return int(num)
        except Exception:
            return 0

    @staticmethod
    def _split_num_unit(s: str) -> tuple[str, str]:
        s = s.strip()
        num = []
        unit = []
        dot_seen = False
        for ch in s:
            if ch.isdigit() or (ch == "." and not dot_seen):
                if ch == ".":
                    dot_seen = True
                num.append(ch)
            elif ch.strip():
                unit.append(ch)
        return ("".join(num) or "0", "".join(unit) or "B")

    @staticmethod
    def _get_cpu_time_sec(cid: str, started: datetime, finished: datetime) -> int:
        """Best-effort CPU time in seconds using cgroup stats, falling back to a CPUPerc sample.

        Strategy:
        - Try cgroup v1: read /sys/fs/cgroup/cpuacct/<cgroup>/cpuacct.usage (nanoseconds)
        - Try cgroup v2: read /sys/fs/cgroup/<cgroup>/cpu.stat (usage_usec)
        - Fallback: sample `docker stats --no-stream --format {{.CPUPerc}}` once and approximate
          cpu_time = wall_time * (percent/100). This is coarse but better than zero.
        Returns 0 on failure.
        """
        try:
            # Resolve the container's init PID
            pid_out = subprocess.check_output(["docker", "inspect", cid, "--format", "{{.State.Pid}}"], text=True, timeout=3).strip()
            pid = int(pid_out)
            # Read cgroup membership
            cgroups = {}
            with open(f"/proc/{pid}/cgroup", "r") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if len(parts) == 3:
                        subsystems = parts[1]
                        path = parts[2]
                        cgroups[subsystems] = path
            # cgroup v1 path for cpuacct
            path_v1 = None
            for key, val in cgroups.items():
                if "cpuacct" in key:
                    path_v1 = val
                    break
            if path_v1:
                cg_file = os.path.join("/sys/fs/cgroup", "cpuacct", path_v1.lstrip("/"), "cpuacct.usage")
                try:
                    with open(cg_file, "r") as f:
                        ns = int(f.read().strip())
                        return int(ns / 1_000_000_000)
                except Exception:
                    pass
            # cgroup v2 unified
            path_v2 = cgroups.get("") or cgroups.get("0") or None
            if not path_v2:
                # Detect v2 by lines like '0::/docker/<id>'
                for key, val in cgroups.items():
                    if key == "0":
                        path_v2 = val
                        break
            if path_v2:
                cg_file2 = os.path.join("/sys/fs/cgroup", path_v2.lstrip("/"), "cpu.stat")
                try:
                    with open(cg_file2, "r") as f:
                        content = f.read()
                        for ln in content.splitlines():
                            if ln.startswith("usage_usec "):
                                usec = int(ln.split()[1])
                                return int(usec / 1_000_000)
                except Exception:
                    pass
        except Exception:
            pass
        # Fallback: approximate from an instantaneous CPU percentage
        try:
            out = subprocess.check_output(["docker", "stats", cid, "--no-stream", "--format", "{{.CPUPerc}}"], text=True, timeout=3).strip()
            # CPUPerc like '12.34%'
            pct = float(out.strip().rstrip("% ") or "0")
            wall = max(0.0, (finished - started).total_seconds())
            return int((pct / 100.0) * wall)
        except Exception:
            return 0
