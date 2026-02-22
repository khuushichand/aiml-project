from __future__ import annotations

import asyncio
import base64
import contextlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from loguru import logger

from tldw_Server_API.app.core.Audit.unified_audit_service import (
    AuditContext,
    AuditEventCategory,
    AuditEventType,
    AuditSeverity,
    UnifiedAuditService,
)
from tldw_Server_API.app.core.config import settings as app_settings
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Metrics import observe_histogram
from tldw_Server_API.app.core.testing import is_truthy

from .models import (
    RunPhase,
    RunSpec,
    RunStatus,
    RuntimeType,
    Session,
    SessionSpec,
)
from .orchestrator import SandboxOrchestrator
from .policy import SandboxPolicy, SandboxPolicyConfig, compute_policy_hash
from .runners.docker_runner import DockerRunner, docker_available
from .runners.firecracker_runner import FirecrackerRunner, firecracker_available, firecracker_real_enabled
from .runners.lima_runner import LimaRunner, lima_available
from .snapshots import SnapshotManager
from .store import get_store_mode
from .streams import get_hub

_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS = (
    asyncio.CancelledError,
    asyncio.TimeoutError,
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    ImportError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
    UnicodeDecodeError,
)


class SandboxService:
    """High-level orchestrator facade for sandbox operations (scaffold).

    Provides feature discovery and minimal ID generation for sessions/runs.
    Actual execution is intentionally not implemented at this stage.
    """

    def __init__(self, policy: SandboxPolicy | None = None) -> None:
        cfg = SandboxPolicyConfig.from_settings()
        self.policy = policy or SandboxPolicy(cfg)
        self._orch = SandboxOrchestrator(self.policy)
        self._supported_specs = list(self.policy.cfg.supported_spec_versions or ["1.0"])
        self._claim_worker_id = f"sandbox-worker-{os.getpid()}-{id(self)}"
        self._bg_executor_lock = threading.RLock()
        self._bg_executor: ThreadPoolExecutor | None = None
        self._bg_executor_workers = 0
        self._snapshots = SnapshotManager(
            storage_path=os.getenv("SANDBOX_SNAPSHOT_PATH")
        )

    class InvalidSpecVersion(Exception):
        def __init__(self, provided: str, supported: list[str]) -> None:
            super().__init__(f"Unsupported spec_version '{provided}'")
            self.provided = provided
            self.supported = supported

    class InvalidFirecrackerConfig(Exception):
        def __init__(self, message: str, details: dict) -> None:
            super().__init__(message)
            self.details = details

    def _validate_firecracker_config(self, spec: RunSpec | SessionSpec) -> None:
        # Only validate when real Firecracker execution is enabled.
        try:
            if spec.runtime != RuntimeType.firecracker:
                return
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
            return
        if not firecracker_real_enabled():
            return

        errors: dict[str, str] = {}
        base_image = getattr(spec, "base_image", None)
        rootfs_path: str | None = None
        if base_image:
            try:
                if os.path.exists(str(base_image)):
                    if os.path.isfile(str(base_image)):
                        rootfs_path = str(base_image)
                    else:
                        errors["base_image"] = "not_file"
            except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                pass
        if not rootfs_path:
            rootfs_path = os.getenv("SANDBOX_FC_ROOTFS_PATH")

        kernel_path = os.getenv("SANDBOX_FC_KERNEL_PATH")
        if not kernel_path:
            errors["kernel_path"] = "missing"
        elif not os.path.exists(kernel_path):
            errors["kernel_path"] = "not_found"
        elif not os.path.isfile(kernel_path):
            errors["kernel_path"] = "not_file"

        if not rootfs_path:
            errors["rootfs_path"] = "missing"
        elif not os.path.exists(rootfs_path):
            errors["rootfs_path"] = "not_found"
        elif not os.path.isfile(rootfs_path):
            errors["rootfs_path"] = "not_file"

        if errors:
            raise SandboxService.InvalidFirecrackerConfig(
                "firecracker_config_invalid",
                {
                    "runtime": "firecracker",
                    "errors": errors,
                },
            )

    def _validate_spec_version(self, spec_version: str | None) -> None:
        if not spec_version:
            return
        if spec_version not in self._supported_specs:
            raise SandboxService.InvalidSpecVersion(spec_version, self._supported_specs)

    def _effective_claim_lease_seconds(self) -> int:
        try:
            raw = os.getenv("SANDBOX_RUN_CLAIM_LEASE_SEC")
            if raw is None:
                raw = getattr(app_settings, "SANDBOX_RUN_CLAIM_LEASE_SEC", 30)
            return max(1, int(raw))
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
            return 30

    def _effective_max_concurrent_runs(self) -> int:
        try:
            raw = os.getenv("SANDBOX_MAX_CONCURRENT_RUNS")
            if raw is None:
                raw = getattr(app_settings, "SANDBOX_MAX_CONCURRENT_RUNS", 8)
            return max(1, int(raw))
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
            return 8

    def _background_executor(self) -> ThreadPoolExecutor:
        workers = self._effective_max_concurrent_runs()
        with self._bg_executor_lock:
            if self._bg_executor is not None and self._bg_executor_workers == workers:
                return self._bg_executor
            old = self._bg_executor
            self._bg_executor = ThreadPoolExecutor(
                max_workers=workers,
                thread_name_prefix="sandbox-runner",
            )
            self._bg_executor_workers = workers
            if old is not None:
                with contextlib.suppress(_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS):
                    old.shutdown(wait=False, cancel_futures=False)
            return self._bg_executor

    def _submit_background_worker(self, worker_fn) -> None:
        # Keep worker fan-out bounded by executor max_workers.
        self._background_executor().submit(worker_fn)

    def _admit_run_starting(self, run_id: str) -> RunStatus | None:
        max_active_runs = self._effective_max_concurrent_runs()
        lease_seconds = self._effective_claim_lease_seconds()
        while True:
            admitted = self._orch.try_admit_run_start(
                run_id,
                worker_id=self._claim_worker_id,
                max_active_runs=max_active_runs,
                lease_seconds=lease_seconds,
            )
            if admitted is not None:
                return admitted
            current = self._orch.get_run(run_id)
            if current is None:
                return None
            owner = str(getattr(current, "claim_owner", "") or "").strip()
            if current.phase != RunPhase.queued or owner != self._claim_worker_id:
                return current
            time.sleep(0.05)

    def _apply_admitted_status(self, target: RunStatus, admitted: RunStatus) -> None:
        target.phase = admitted.phase
        target.started_at = admitted.started_at
        target.finished_at = admitted.finished_at
        target.exit_code = admitted.exit_code
        target.claim_owner = admitted.claim_owner
        target.claim_expires_at = admitted.claim_expires_at

    def _run_with_claim_lease(self, run_id: str, fn):
        lease_seconds = self._effective_claim_lease_seconds()
        heartbeat_interval = max(1, min(10, lease_seconds // 3 if lease_seconds > 2 else 1))
        stop = threading.Event()

        def _heartbeat() -> None:
            while not stop.wait(heartbeat_interval):
                try:
                    ok = self._orch.renew_run_claim(
                        run_id,
                        worker_id=self._claim_worker_id,
                        lease_seconds=lease_seconds,
                    )
                except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                    ok = False
                if not ok:
                    break

        hb = threading.Thread(target=_heartbeat, daemon=True)
        hb.start()
        try:
            return fn()
        finally:
            stop.set()
            with contextlib.suppress(_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS):
                hb.join(timeout=0.1)

    def feature_discovery(self) -> list[dict]:
        images = [
            "python:3.11-slim",
            "node:20-alpine",
            # generic shell base left for future: e.g., "ubuntu:24.04"
        ]
        # Defaults pulled from policy cfg (wired to env/config)
        max_cpu = self.policy.cfg.max_cpu
        max_mem_mb = self.policy.cfg.max_mem_mb
        max_upload_mb = self.policy.cfg.max_upload_mb
        max_log_bytes = self.policy.cfg.max_log_bytes
        workspace_cap_mb = self.policy.cfg.workspace_cap_mb
        artifact_ttl_hours = self.policy.cfg.artifact_ttl_hours
        supported_spec_versions = list(self.policy.cfg.supported_spec_versions or ["1.0"])
        # Queue/backpressure defaults from app settings
        try:
            queue_max_length = int(getattr(app_settings, "SANDBOX_QUEUE_MAX_LENGTH", 100))
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
            queue_max_length = 100
        try:
            queue_ttl_sec = int(getattr(app_settings, "SANDBOX_QUEUE_TTL_SEC", 120))
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
            queue_ttl_sec = 120
        # Store mode advertised to clients (e.g., memory|sqlite|cluster)
        try:
            store_mode = str(get_store_mode())
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
            store_mode = "unknown"
        # Whether we have active enforcement for egress allowlisting (Docker only for now)
        try:
            env_enf = is_truthy(
                str(
                    os.getenv("SANDBOX_EGRESS_ENFORCEMENT")
                    or getattr(app_settings, "SANDBOX_EGRESS_ENFORCEMENT", "")
                ).strip().lower()
            )
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
            env_enf = False
        egress_supported = bool(self.policy.cfg.egress_enforcement) or bool(env_enf)
        try:
            env_gran = is_truthy(
                str(
                    os.getenv("SANDBOX_EGRESS_GRANULAR_ENFORCEMENT")
                    or getattr(app_settings, "SANDBOX_EGRESS_GRANULAR_ENFORCEMENT", "")
                ).strip().lower()
            )
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
            env_gran = False
        granular = bool(egress_supported and env_gran)
        # Whether execution is enabled (env overrides settings)
        try:
            env_exec = os.getenv("SANDBOX_ENABLE_EXECUTION")
            if env_exec is not None:
                execute_enabled = is_truthy(env_exec)
            else:
                execute_enabled = bool(getattr(app_settings, "SANDBOX_ENABLE_EXECUTION", False))
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
            execute_enabled = False

        return [
            {
                "name": "docker",
                "available": bool(docker_available()),
                "default_images": images,
                "max_cpu": max_cpu,
                "max_mem_mb": max_mem_mb,
                "max_upload_mb": max_upload_mb,
                "max_log_bytes": max_log_bytes,
                "queue_max_length": queue_max_length,
                "queue_ttl_sec": queue_ttl_sec,
                "workspace_cap_mb": workspace_cap_mb,
                "artifact_ttl_hours": artifact_ttl_hours,
                "supported_spec_versions": supported_spec_versions,
                # Advertise interactive only when real runner execution is enabled and available
                "interactive_supported": bool(execute_enabled and docker_available()),
                "egress_allowlist_supported": bool(egress_supported),
                "store_mode": store_mode,
                "notes": (
                    "Granular egress allowlist (CIDR, hostname) enforced via host iptables (DOCKER-USER) with DNS pinning"
                    if bool(egress_supported and granular)
                    else ("Egress allowlist enforced as deny-all (network=none)" if bool(egress_supported) else None)
                ),
            },
            {
                "name": "firecracker",
                "available": bool(firecracker_available()),
                "default_images": images,  # firecracker images will differ; placeholder for UX
                "max_cpu": max_cpu,
                "max_mem_mb": max_mem_mb,
                "max_upload_mb": max_upload_mb,
                "max_log_bytes": max_log_bytes,
                "queue_max_length": queue_max_length,
                "queue_ttl_sec": queue_ttl_sec,
                "workspace_cap_mb": workspace_cap_mb,
                "artifact_ttl_hours": artifact_ttl_hours,
                "supported_spec_versions": supported_spec_versions,
                "interactive_supported": False,
                # Only advertise allowlist support when explicit Firecracker enforcement is enabled
                "egress_allowlist_supported": bool(
                    is_truthy(
                        str(
                            os.getenv("SANDBOX_FIRECRACKER_EGRESS_ENFORCEMENT")
                            or getattr(app_settings, "SANDBOX_FIRECRACKER_EGRESS_ENFORCEMENT", "")
                        ).strip().lower()
                    )
                ),
                "store_mode": store_mode,
                "notes": (
                    "Granular egress allowlist enforced via VM tap/bridge + host firewall (planned)"
                    if bool(
                        is_truthy(
                            str(
                                os.getenv("SANDBOX_FIRECRACKER_EGRESS_GRANULAR_ENFORCEMENT")
                                or getattr(app_settings, "SANDBOX_FIRECRACKER_EGRESS_GRANULAR_ENFORCEMENT", "")
                            ).strip().lower()
                        )
                    )
                    else "Allowlist enforcement uses deny-all fallback currently; granular Firecracker egress isolation planned"
                ),
            },
            {
                "name": "lima",
                "available": bool(lima_available()),
                "default_images": ["ubuntu:24.04"],  # Lima uses distro images
                "max_cpu": max_cpu,
                "max_mem_mb": max_mem_mb,
                "max_upload_mb": max_upload_mb,
                "max_log_bytes": max_log_bytes,
                "queue_max_length": queue_max_length,
                "queue_ttl_sec": queue_ttl_sec,
                "workspace_cap_mb": workspace_cap_mb,
                "artifact_ttl_hours": artifact_ttl_hours,
                "supported_spec_versions": supported_spec_versions,
                "interactive_supported": False,  # Not implemented for Lima yet
                "egress_allowlist_supported": False,  # Lima uses VM-level network isolation
                "store_mode": store_mode,
                "notes": "Full VM isolation via Lima; recommended for macOS",
            },
        ]

    def _audit_run_completion(self, *, user_id: str | int | None, run_id: str, status: RunStatus, spec_version: str, session_id: str | None) -> None:
        """Log a completion audit event in a fire-and-forget manner."""
        try:
            uid_int = None
            try:
                uid_int = int(str(user_id)) if user_id is not None else None
            except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                uid_int = None
            db_path = DatabasePaths.get_audit_db_path(uid_int) if uid_int is not None else None

            async def _alog() -> None:
                svc = UnifiedAuditService(db_path=str(db_path) if db_path else None)
                # One-off audit emission: avoid spawning background tasks.
                await svc.initialize(start_background_tasks=False)
                try:
                    ctx = AuditContext(
                        user_id=(str(user_id) if user_id is not None else None),
                        session_id=session_id,
                        method="INTERNAL",
                        endpoint="/api/v1/sandbox/runs (background)",
                    )
                    outcome = (
                        "success" if status.phase in (RunPhase.completed,) and (status.exit_code or 0) == 0 else
                        "timeout" if status.phase == RunPhase.timed_out else
                        "killed" if status.phase == RunPhase.killed else
                        "failed" if status.phase == RunPhase.failed else
                        status.phase.value
                    )
                    dur_ms = None
                    try:
                        if status.started_at and status.finished_at:
                            dur_ms = max(0.0, (status.finished_at - status.started_at).total_seconds() * 1000.0)
                    except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                        dur_ms = None
                    # Include reason_code for non-success outcomes when available
                    reason_code = None
                    try:
                        if outcome in ("timeout", "failed"):
                            reason_code = (status.message or None)
                    except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                        reason_code = None
                    await svc.log_event(
                        event_type=AuditEventType.API_RESPONSE,
                        category=AuditEventCategory.API_CALL,
                        severity=(AuditSeverity.INFO if outcome == "success" else AuditSeverity.WARNING),
                        context=ctx,
                        resource_type="sandbox.run",
                        resource_id=run_id,
                        action="run",
                        result=("success" if outcome == "success" else outcome),
                        duration_ms=dur_ms,
                        metadata={
                            "runtime": status.runtime.value if status.runtime else None,
                            "base_image": status.base_image,
                            "image_digest": status.image_digest,
                            "policy_hash": status.policy_hash,
                            "exit_code": status.exit_code,
                            "spec_version": spec_version,
                            "reason_code": reason_code,
                        },
                    )
                finally:
                    await svc.stop()

            # Run now; if we're already in an event loop, schedule task
            try:
                asyncio.run(_alog())
            except RuntimeError:
                loop = asyncio.get_event_loop()
                loop.create_task(_alog())
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as e:
            logger.debug(f"audit(run.completion) failed: {e}")
        # (rest of method continues)

    def create_session(self, user_id: str | int, spec: SessionSpec, spec_version: str, idem_key: str | None, raw_body: dict) -> Session:
        # Validate requested spec version
        self._validate_spec_version(spec_version)
        fc_ok = firecracker_available()
        lima_ok = lima_available()
        spec = self.policy.apply_to_session(spec, firecracker_available=fc_ok, lima_available=lima_ok)
        # Validate Firecracker kernel/rootfs when real execution is enabled
        self._validate_firecracker_config(spec)
        # delegate to orchestrator (with idempotency)
        sess = self._orch.create_session(user_id=user_id, spec=spec, spec_version=spec_version, idem_key=idem_key, body=raw_body)
        return sess

    def destroy_session(self, session_id: str) -> bool:
        try:
            return bool(self._orch.destroy_session(session_id))
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as e:
            logger.debug(f"destroy_session failed: {e}")
            return False

    def parse_inline_files(self, files: list[dict] | None) -> list[tuple[str, bytes]]:
        results: list[tuple[str, bytes]] = []
        if not files:
            return results
        for f in files:
            try:
                p = str(f.get("path", ""))
                b64 = str(f.get("content_b64", ""))
                data = base64.b64decode(b64)
                results.append((p, data))
            except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as e:
                logger.warning(f"Failed to parse inline file: {e}")
        return results

    def start_run_scaffold(self, user_id: str | int, spec: RunSpec, spec_version: str, idem_key: str | None, raw_body: dict) -> RunStatus:
        # Validate requested spec version
        self._validate_spec_version(spec_version)
        # Apply policy then enqueue via orchestrator (idempotency-aware)
        fc_ok = firecracker_available()
        lima_ok = lima_available()
        spec = self.policy.apply_to_run(spec, firecracker_available=fc_ok, lima_available=lima_ok)
        # Validate Firecracker kernel/rootfs when real execution is enabled
        self._validate_firecracker_config(spec)
        status = self._orch.enqueue_run(user_id=user_id, spec=spec, spec_version=spec_version, idem_key=idem_key, body=raw_body)
        # Configure stdin caps in hub if interactive is requested (spec 1.1)
        try:
            interactive = bool(spec.interactive) if getattr(spec, "interactive", None) is not None else False
            if interactive:
                get_hub().configure_stdin(
                    status.id,
                    interactive=True,
                    stdin_max_bytes=(int(spec.stdin_max_bytes) if getattr(spec, "stdin_max_bytes", None) is not None else None),
                    stdin_max_frame_bytes=(int(spec.stdin_max_frame_bytes) if getattr(spec, "stdin_max_frame_bytes", None) is not None else None),
                    stdin_bps=(int(spec.stdin_bps) if getattr(spec, "stdin_bps", None) is not None else None),
                    stdin_idle_timeout_sec=(int(spec.stdin_idle_timeout_sec) if getattr(spec, "stdin_idle_timeout_sec", None) is not None else None),
                )
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
            pass
        # Emit queue-wait metric as soon as we move out of queued (or immediately after enqueue)
        # so tests that disable execution still observe this metric.
        try:
            ts = self._orch.get_enqueue_time(status.id)  # type: ignore[attr-defined]
            if ts:
                import time as _time
                qwait = max(0.0, _time.time() - float(ts))
                observe_histogram("sandbox_queue_wait_seconds", value=float(qwait), labels={"runtime": str(spec.runtime.value if spec.runtime else "unknown")})
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
            pass
        # Optional: Execute via Docker runner if enabled and requested
        # Allow per-test overrides via env even if settings were loaded earlier
        try:
            env_exec = os.getenv("SANDBOX_ENABLE_EXECUTION")
            if env_exec is not None:
                execute_enabled = is_truthy(env_exec)
            else:
                execute_enabled = bool(getattr(app_settings, "SANDBOX_ENABLE_EXECUTION", False))
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
            execute_enabled = False
        if execute_enabled:
            lease_seconds = self._effective_claim_lease_seconds()
            claimed = self._orch.try_claim_run(
                status.id,
                worker_id=self._claim_worker_id,
                lease_seconds=lease_seconds,
            )
            if claimed is None:
                existing = self._orch.get_run(status.id)
                return existing or status
            status = claimed
        if execute_enabled and spec.runtime == RuntimeType.docker:
            try:
                env_bg = os.getenv("SANDBOX_BACKGROUND_EXECUTION")
                if env_bg is not None:
                    background = is_truthy(env_bg)
                else:
                    background = bool(getattr(app_settings, "SANDBOX_BACKGROUND_EXECUTION", False))
                # Force foreground when using Docker fake execution to satisfy tests
                try:
                    if is_truthy(str(os.getenv("TLDW_SANDBOX_DOCKER_FAKE_EXEC") or "").strip().lower()):
                        background = False
                except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                    pass
                if background:
                    # Return early and execute in background
                    # Metrics: queue wait histogram (if enqueued timestamp known)
                    try:
                        ts = self._orch.get_enqueue_time(status.id)  # type: ignore[attr-defined]
                        if ts:
                            import time as _time
                            qwait = max(0.0, _time.time() - float(ts))
                            observe_histogram("sandbox_queue_wait_seconds", value=float(qwait), labels={"runtime": "docker"})
                    except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                        pass
                    def _worker():
                        try:
                            admitted = self._admit_run_starting(status.id)
                            if admitted is None or admitted.phase != RunPhase.starting:
                                return
                            self._apply_admitted_status(status, admitted)
                            with contextlib.suppress(_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS):
                                get_hub().publish_event(status.id, "start", {"bg": True})
                            dr = DockerRunner()
                            ws = self._orch.get_session_workspace_path(spec.session_id) if spec.session_id else None
                            real = self._run_with_claim_lease(
                                status.id,
                                lambda: dr.start_run(status.id, spec, ws),
                            )
                            real.id = status.id
                            # Merge results
                            status.phase = real.phase
                            status.exit_code = real.exit_code
                            status.started_at = real.started_at
                            status.finished_at = real.finished_at
                            status.message = real.message
                            status.image_digest = real.image_digest
                            # Attach resource usage if produced by runner
                            try:
                                if getattr(real, "resource_usage", None):
                                    status.resource_usage = real.resource_usage  # type: ignore[assignment]
                            except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                                pass
                            if real.artifacts:
                                self._orch.store_artifacts(status.id, real.artifacts)
                            try:
                                self._orch.update_run(status.id, status)  # type: ignore[attr-defined]
                            except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as _e:
                                logger.debug(f"sandbox: update_run(completed) skipped: {_e}")
                            # Ensure an 'end' event is published even if the runner didn't
                            with contextlib.suppress(_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS):
                                get_hub().publish_event(status.id, "end", {"exit_code": status.exit_code})
                            # Ensure policy hash is present (compute if missing)
                            if not status.policy_hash:
                                status.policy_hash = compute_policy_hash(self.policy.cfg)
                            # Audit completion
                            self._audit_run_completion(user_id=user_id, run_id=status.id, status=status, spec_version=spec_version, session_id=spec.session_id)
                        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as e:
                            logger.warning(f"Background docker execution failed: {e}")
                    try:
                        self._submit_background_worker(_worker)
                    except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as e:
                        logger.warning(f"Background docker submission failed: {e}")
                else:
                    dr = DockerRunner()
                    ws = self._orch.get_session_workspace_path(spec.session_id) if spec.session_id else None
                    # Metrics: queue wait histogram before starting execution
                    try:
                        ts = self._orch.get_enqueue_time(status.id)  # type: ignore[attr-defined]
                        if ts:
                            import time as _time
                            qwait = max(0.0, _time.time() - float(ts))
                            observe_histogram("sandbox_queue_wait_seconds", value=float(qwait), labels={"runtime": "docker"})
                    except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                        pass
                    admitted = self._admit_run_starting(status.id)
                    if admitted is None:
                        existing = self._orch.get_run(status.id)
                        return existing or status
                    if admitted.phase != RunPhase.starting:
                        return admitted
                    self._apply_admitted_status(status, admitted)
                    real = self._run_with_claim_lease(
                        status.id,
                        lambda: dr.start_run(status.id, spec, ws),
                    )
                    real.id = status.id
                    status.phase = real.phase
                    status.exit_code = real.exit_code
                    status.started_at = real.started_at
                    status.finished_at = real.finished_at
                    status.message = real.message
                    status.image_digest = real.image_digest
                    try:
                        if getattr(real, "resource_usage", None):
                            status.resource_usage = real.resource_usage  # type: ignore[assignment]
                    except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                        pass
                    if real.artifacts:
                        self._orch.store_artifacts(status.id, real.artifacts)
                    self._orch.update_run(status.id, status)
                    # Audit completion (sync path)
                    with contextlib.suppress(_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS):
                        self._audit_run_completion(user_id=user_id, run_id=status.id, status=status, spec_version=spec_version, session_id=spec.session_id)
            except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as e:
                logger.warning(f"Docker execution failed; keeping enqueue status. Error: {e}")
        elif execute_enabled and spec.runtime == RuntimeType.firecracker:
            try:
                env_bg = os.getenv("SANDBOX_BACKGROUND_EXECUTION")
                if env_bg is not None:
                    background = is_truthy(env_bg)
                else:
                    background = bool(getattr(app_settings, "SANDBOX_BACKGROUND_EXECUTION", False))
                if background:
                    def _worker_fc():
                        try:
                            admitted = self._admit_run_starting(status.id)
                            if admitted is None or admitted.phase != RunPhase.starting:
                                return
                            self._apply_admitted_status(status, admitted)
                            with contextlib.suppress(_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS):
                                get_hub().publish_event(status.id, "start", {"bg": True})
                            fr = FirecrackerRunner()
                            ws = self._orch.get_session_workspace_path(spec.session_id) if spec.session_id else None
                            real = self._run_with_claim_lease(
                                status.id,
                                lambda: fr.start_run(status.id, spec, ws),
                            )
                            real.id = status.id
                            status.phase = real.phase
                            status.exit_code = real.exit_code
                            status.started_at = real.started_at
                            status.finished_at = real.finished_at
                            status.message = real.message
                            status.image_digest = real.image_digest
                            status.runtime_version = real.runtime_version
                            try:
                                if getattr(real, "resource_usage", None):
                                    status.resource_usage = real.resource_usage  # type: ignore[assignment]
                            except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                                pass
                            if real.artifacts:
                                self._orch.store_artifacts(status.id, real.artifacts)
                            self._orch.update_run(status.id, status)
                            with contextlib.suppress(_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS):
                                self._audit_run_completion(user_id=user_id, run_id=status.id, status=status, spec_version=spec_version, session_id=spec.session_id)
                        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as e:
                            logger.warning(f"Firecracker background execution failed: {e}")
                    try:
                        self._submit_background_worker(_worker_fc)
                    except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as e:
                        logger.warning(f"Firecracker background submission failed: {e}")
                else:
                    # Foreground
                    fr = FirecrackerRunner()
                    ws = self._orch.get_session_workspace_path(spec.session_id) if spec.session_id else None
                    admitted = self._admit_run_starting(status.id)
                    if admitted is None:
                        existing = self._orch.get_run(status.id)
                        return existing or status
                    if admitted.phase != RunPhase.starting:
                        return admitted
                    self._apply_admitted_status(status, admitted)
                    real = self._run_with_claim_lease(
                        status.id,
                        lambda: fr.start_run(status.id, spec, ws),
                    )
                    real.id = status.id
                    status.phase = real.phase
                    status.exit_code = real.exit_code
                    status.started_at = real.started_at
                    status.finished_at = real.finished_at
                    status.message = real.message
                    status.image_digest = real.image_digest
                    status.runtime_version = real.runtime_version
                    try:
                        if getattr(real, "resource_usage", None):
                            status.resource_usage = real.resource_usage  # type: ignore[assignment]
                    except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                        pass
                    if real.artifacts:
                        self._orch.store_artifacts(status.id, real.artifacts)
                    self._orch.update_run(status.id, status)
                    with contextlib.suppress(_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS):
                        self._audit_run_completion(user_id=user_id, run_id=status.id, status=status, spec_version=spec_version, session_id=spec.session_id)
            except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as e:
                logger.warning(f"Firecracker execution failed; marking run failed. Error: {e}")
                try:
                    status.phase = RunPhase.failed
                    status.message = "firecracker_failed"
                    status.finished_at = datetime.utcnow()
                    self._orch.update_run(status.id, status)
                    with contextlib.suppress(_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS):
                        get_hub().publish_event(status.id, "end", {"exit_code": status.exit_code, "reason": "firecracker_failed"})
                except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                    pass
        elif execute_enabled and spec.runtime == RuntimeType.lima:
            try:
                env_bg = os.getenv("SANDBOX_BACKGROUND_EXECUTION")
                if env_bg is not None:
                    background = is_truthy(env_bg)
                else:
                    background = bool(getattr(app_settings, "SANDBOX_BACKGROUND_EXECUTION", False))
                if background:
                    def _worker_lima():
                        try:
                            admitted = self._admit_run_starting(status.id)
                            if admitted is None or admitted.phase != RunPhase.starting:
                                return
                            self._apply_admitted_status(status, admitted)
                            with contextlib.suppress(_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS):
                                get_hub().publish_event(status.id, "start", {"bg": True})
                            lr = LimaRunner()
                            ws = self._orch.get_session_workspace_path(spec.session_id) if spec.session_id else None
                            real = self._run_with_claim_lease(
                                status.id,
                                lambda: lr.start_run(status.id, spec, ws),
                            )
                            real.id = status.id
                            status.phase = real.phase
                            status.exit_code = real.exit_code
                            status.started_at = real.started_at
                            status.finished_at = real.finished_at
                            status.message = real.message
                            status.image_digest = real.image_digest
                            status.runtime_version = real.runtime_version
                            try:
                                if getattr(real, "resource_usage", None):
                                    status.resource_usage = real.resource_usage
                            except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                                pass
                            if real.artifacts:
                                self._orch.store_artifacts(status.id, real.artifacts)
                            self._orch.update_run(status.id, status)
                            with contextlib.suppress(_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS):
                                self._audit_run_completion(user_id=user_id, run_id=status.id, status=status, spec_version=spec_version, session_id=spec.session_id)
                        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as e:
                            logger.warning(f"Lima background execution failed: {e}")
                    try:
                        self._submit_background_worker(_worker_lima)
                    except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as e:
                        logger.warning(f"Lima background submission failed: {e}")
                else:
                    # Foreground
                    lr = LimaRunner()
                    ws = self._orch.get_session_workspace_path(spec.session_id) if spec.session_id else None
                    admitted = self._admit_run_starting(status.id)
                    if admitted is None:
                        existing = self._orch.get_run(status.id)
                        return existing or status
                    if admitted.phase != RunPhase.starting:
                        return admitted
                    self._apply_admitted_status(status, admitted)
                    real = self._run_with_claim_lease(
                        status.id,
                        lambda: lr.start_run(status.id, spec, ws),
                    )
                    real.id = status.id
                    status.phase = real.phase
                    status.exit_code = real.exit_code
                    status.started_at = real.started_at
                    status.finished_at = real.finished_at
                    status.message = real.message
                    status.image_digest = real.image_digest
                    status.runtime_version = real.runtime_version
                    try:
                        if getattr(real, "resource_usage", None):
                            status.resource_usage = real.resource_usage
                    except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                        pass
                    if real.artifacts:
                        self._orch.store_artifacts(status.id, real.artifacts)
                    self._orch.update_run(status.id, status)
                    with contextlib.suppress(_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS):
                        self._audit_run_completion(user_id=user_id, run_id=status.id, status=status, spec_version=spec_version, session_id=spec.session_id)
            except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as e:
                logger.warning(f"Lima execution failed; marking run failed. Error: {e}")
                try:
                    status.phase = RunPhase.failed
                    status.message = "lima_failed"
                    status.finished_at = datetime.utcnow()
                    self._orch.update_run(status.id, status)
                    with contextlib.suppress(_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS):
                        get_hub().publish_event(status.id, "end", {"exit_code": status.exit_code, "reason": "lima_failed"})
                except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
                    pass
        else:
            # Stub artifacts even without execution
            artifacts: dict[str, bytes] = {}
            for pattern in spec.capture_patterns or []:
                artifacts[pattern] = b""
            if artifacts:
                self._orch.store_artifacts(status.id, artifacts)
        # Attach canonical policy hash for metadata consistency
        try:
            status.policy_hash = compute_policy_hash(self.policy.cfg)
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
            status.policy_hash = None  # type: ignore[assignment]
        # Keep phase/status fields contract-safe and persist before returning so
        # POST response fields match subsequent GET/cross-node reads.
        now = datetime.utcnow()
        if status.phase == RunPhase.queued:
            status.started_at = None
            status.finished_at = None
            status.exit_code = None
        elif status.phase in (RunPhase.completed, RunPhase.failed, RunPhase.killed, RunPhase.timed_out):
            if not status.started_at:
                status.started_at = now
            if not status.finished_at:
                status.finished_at = now
            if status.exit_code is None and status.phase == RunPhase.completed:
                status.exit_code = 0
        try:
            self._orch.update_run(status.id, status)
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as _e:
            logger.debug(f"sandbox: update_run(final) skipped: {_e}")
        return status

    def get_run(self, run_id: str) -> RunStatus | None:
        return self._orch.get_run(run_id)

    def get_session_workspace_path(self, session_id: str) -> str | None:
        return self._orch.get_session_workspace_path(session_id)

    def cancel_run(self, run_id: str) -> bool:
        st = self._orch.get_run(run_id)
        if not st:
            return False
        # If already finished, no-op
        if st.phase in (RunPhase.completed, RunPhase.failed, RunPhase.killed, RunPhase.timed_out):
            return False
        cancelled = False
        try:
            if st.runtime == RuntimeType.docker:
                cancelled = DockerRunner.cancel_run(run_id)
            elif st.runtime == RuntimeType.lima:
                cancelled = LimaRunner.cancel_run(run_id)
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as e:
            logger.debug(f"cancel_run failed: {e}")
            cancelled = False
        # Update status
        try:
            st.phase = RunPhase.killed
            st.message = "canceled_by_user"
            st.finished_at = datetime.utcnow()
            st.exit_code = None
            self._orch.update_run(run_id, st)
            # Consider the operation successful if we set killed state
            cancelled = True
        except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS:
            pass
        # Ensure WS end event is sent even if runner didn't publish
        with contextlib.suppress(_SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS):
            get_hub().publish_event(run_id, "end", {"exit_code": None, "canceled": True})
        return bool(cancelled)

    # -----------------
    # Snapshot Operations
    # -----------------

    def create_snapshot(self, session_id: str) -> dict:
        """Create a snapshot of a session's workspace.

        Args:
            session_id: The session to snapshot.

        Returns:
            Snapshot metadata including snapshot_id, created_at, and size_bytes.

        Raises:
            ValueError: If session not found or has no workspace.
        """
        ws = self._orch.get_session_workspace_path(session_id)
        if not ws:
            raise ValueError("Session not found or no workspace")
        return self._snapshots.create_snapshot(session_id, ws)

    def restore_snapshot(self, session_id: str, snapshot_id: str) -> bool:
        """Restore a session's workspace from a snapshot.

        Args:
            session_id: The session to restore.
            snapshot_id: The snapshot to restore from.

        Returns:
            True if restoration was successful.

        Raises:
            ValueError: If session or snapshot not found.
        """
        ws = self._orch.get_session_workspace_path(session_id)
        if not ws:
            raise ValueError("Session not found or no workspace")
        return self._snapshots.restore_snapshot(session_id, snapshot_id, ws)

    def clone_session(self, session_id: str, new_name: str | None = None) -> Session:
        """Clone a session including its workspace.

        Args:
            session_id: The source session to clone.
            new_name: Optional name/label for the new session.

        Returns:
            The newly created session.

        Raises:
            ValueError: If source session not found.
        """
        # Get source session info
        source_ws = self._orch.get_session_workspace_path(session_id)
        if not source_ws:
            raise ValueError("Source session not found or no workspace")

        source_owner = self._orch.get_session_owner(session_id)
        if not source_owner:
            raise ValueError("Source session owner not found")

        # Resolve source session details from orchestrator cache/store.
        source_sess = self._orch.get_session(session_id)

        if not source_sess:
            raise ValueError("Source session not found")

        # Create new session with same spec
        spec = SessionSpec(
            runtime=source_sess.runtime,
            base_image=source_sess.base_image,
            persona_id=source_sess.persona_id,
            workspace_id=source_sess.workspace_id,
            workspace_group_id=source_sess.workspace_group_id,
            scope_snapshot_id=source_sess.scope_snapshot_id,
        )
        new_sess = self._orch.create_session(
            user_id=source_owner,
            spec=spec,
            spec_version="1.0",
            idem_key=None,
            body={"cloned_from": session_id},
        )

        # Copy workspace
        new_ws = self._orch.get_session_workspace_path(new_sess.id)
        if new_ws:
            try:
                self._snapshots.clone_session(session_id, source_ws, new_sess.id, new_ws)
            except _SANDBOX_SERVICE_NONCRITICAL_EXCEPTIONS as e:
                logger.warning(f"Failed to clone workspace: {e}")
                # Clean up on failure
                self._orch.destroy_session(new_sess.id)
                raise ValueError(f"Failed to clone workspace: {e}") from e

        return new_sess

    def list_snapshots(self, session_id: str) -> list[dict]:
        """List all snapshots for a session.

        Args:
            session_id: The session to list snapshots for.

        Returns:
            List of snapshot metadata dictionaries.
        """
        return self._snapshots.list_snapshots(session_id)

    def delete_snapshot(self, session_id: str, snapshot_id: str) -> bool:
        """Delete a specific snapshot.

        Args:
            session_id: The session owning the snapshot.
            snapshot_id: The snapshot to delete.

        Returns:
            True if deleted successfully.
        """
        return self._snapshots.delete_snapshot(session_id, snapshot_id)

    def get_snapshot_info(self, session_id: str, snapshot_id: str) -> dict | None:
        """Get information about a specific snapshot.

        Args:
            session_id: The session owning the snapshot.
            snapshot_id: The snapshot to get info for.

        Returns:
            Snapshot metadata or None if not found.
        """
        return self._snapshots.get_snapshot_info(session_id, snapshot_id)
