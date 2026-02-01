from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

from loguru import logger

from .models import RuntimeType, RunSpec, SessionSpec, TrustLevel
from tldw_Server_API.app.core.config import settings as app_settings
import json
import hashlib


# Trust-level presets define resource limits and security constraints
# based on the trust level of the code being executed.
TRUST_PROFILES: dict[TrustLevel, dict] = {
    TrustLevel.trusted: {
        "max_cpu": 8,
        "max_mem_mb": 16384,
        "timeout_sec": 600,
        "network_policy": "allowlist",  # Can access configured egress
        "workspace_cap_mb": 512,
        "pids_limit": 512,
        "ulimit_nofile": 4096,
    },
    TrustLevel.standard: {
        "max_cpu": 4,
        "max_mem_mb": 8192,
        "timeout_sec": 300,
        "network_policy": "deny_all",
        "workspace_cap_mb": 256,
        "pids_limit": 256,
        "ulimit_nofile": 1024,
    },
    TrustLevel.untrusted: {
        "max_cpu": 1,
        "max_mem_mb": 1024,
        "timeout_sec": 60,
        "network_policy": "deny_all",
        "workspace_cap_mb": 64,
        "pids_limit": 64,
        "ulimit_nofile": 256,
    },
}


@dataclass
class SandboxPolicyConfig:
    default_runtime: RuntimeType = RuntimeType.docker
    network_default: str = "deny_all"  # deny_all | allowlist (allowlist controlled elsewhere)
    # Opt-in egress allowlist enforcement (runtime dependent; Docker only for now)
    egress_enforcement: bool = False
    egress_allowlist: List[str] = field(default_factory=list)
    artifact_ttl_hours: int = 24
    max_upload_mb: int = 64
    max_log_bytes: int = 10 * 1024 * 1024
    pids_limit: int = 256
    max_cpu: float = 4.0
    max_mem_mb: int = 8192
    workspace_cap_mb: int = 256
    supported_spec_versions: List[str] = field(default_factory=lambda: ["1.0"])

    @classmethod
    def from_settings(cls) -> "SandboxPolicyConfig":
        try:
            rt_raw = str(getattr(app_settings, "SANDBOX_DEFAULT_RUNTIME", "docker")).strip().lower()
        except Exception:
            rt_raw = "docker"
        runtime = RuntimeType.firecracker if rt_raw == "firecracker" else RuntimeType.docker
        try:
            network_default = str(getattr(app_settings, "SANDBOX_NETWORK_DEFAULT", "deny_all")).strip().lower()
        except Exception:
            network_default = "deny_all"
        def _get_int(key: str, dv: int) -> int:
            try:
                return int(getattr(app_settings, key))  # type: ignore[arg-type]
            except Exception:
                return dv
        def _get_float(key: str, dv: float) -> float:
            try:
                return float(getattr(app_settings, key))  # type: ignore[arg-type]
            except Exception:
                return dv
        def _get_list(key: str, dv: List[str]) -> List[str]:
            try:
                v = getattr(app_settings, key)
                if isinstance(v, list):
                    return [str(x) for x in v]
                s = str(v)
                return [t.strip() for t in s.split(',') if t.strip()]
            except Exception:
                return dv
        def _get_bool(key: str, dv: bool) -> bool:
            try:
                v = getattr(app_settings, key)
                if isinstance(v, bool):
                    return v
                s = str(v).strip().lower()
                return s in {"1", "true", "yes", "on", "y"}
            except Exception:
                return dv
        return cls(
            default_runtime=runtime,
            network_default=network_default,
            egress_enforcement=_get_bool("SANDBOX_EGRESS_ENFORCEMENT", False),
            egress_allowlist=_get_list("SANDBOX_EGRESS_ALLOWLIST", []),
            artifact_ttl_hours=_get_int("SANDBOX_ARTIFACT_TTL_HOURS", 24),
            max_upload_mb=_get_int("SANDBOX_MAX_UPLOAD_MB", 64),
            max_log_bytes=_get_int("SANDBOX_MAX_LOG_BYTES", 10 * 1024 * 1024),
            pids_limit=_get_int("SANDBOX_PIDS_LIMIT", 256),
            max_cpu=_get_float("SANDBOX_MAX_CPU", 4.0),
            max_mem_mb=_get_int("SANDBOX_MAX_MEM_MB", 8192),
            workspace_cap_mb=_get_int("SANDBOX_WORKSPACE_CAP_MB", 256),
            supported_spec_versions=_get_list("SANDBOX_SUPPORTED_SPEC_VERSIONS", ["1.0"]),
        )


class SandboxPolicy:
    """Evaluates and normalizes sandbox requests against admin policy.

    This v0 policy is intentionally simple and conservative: deny-all network by default,
    and prefer Docker for broad compatibility unless Firecracker is explicitly requested
    and available.
    """

    def __init__(self, cfg: Optional[SandboxPolicyConfig] = None) -> None:
        self.cfg = cfg or SandboxPolicyConfig.from_settings()

    class RuntimeUnavailable(Exception):
        def __init__(self, runtime: RuntimeType) -> None:
            super().__init__(f"Requested runtime '{runtime.value}' is unavailable")
            self.runtime = runtime

    def select_runtime(
        self,
        requested: Optional[RuntimeType],
        firecracker_available: bool,
        lima_available: bool = False,
    ) -> RuntimeType:
        if requested is not None:
            if requested == RuntimeType.firecracker and not firecracker_available:
                # Do not silently fallback; surface unavailability to caller
                raise SandboxPolicy.RuntimeUnavailable(requested)
            if requested == RuntimeType.lima and not lima_available:
                raise SandboxPolicy.RuntimeUnavailable(requested)
            return requested
        # No explicit request: honor default, but still enforce availability
        if self.cfg.default_runtime == RuntimeType.firecracker and not firecracker_available:
            raise SandboxPolicy.RuntimeUnavailable(self.cfg.default_runtime)
        if self.cfg.default_runtime == RuntimeType.lima and not lima_available:
            raise SandboxPolicy.RuntimeUnavailable(self.cfg.default_runtime)
        return self.cfg.default_runtime

    def apply_to_session(
        self,
        spec: SessionSpec,
        firecracker_available: bool,
        lima_available: bool = False,
    ) -> SessionSpec:
        spec.runtime = self.select_runtime(spec.runtime, firecracker_available, lima_available)

        # Apply trust-level profile constraints
        trust = spec.trust_level or TrustLevel.standard
        profile = TRUST_PROFILES.get(trust, TRUST_PROFILES[TrustLevel.standard])

        if not spec.network_policy:
            spec.network_policy = profile.get("network_policy", self.cfg.network_default)

        # Apply trust-level resource limits (more restrictive of trust profile and global policy)
        profile_max_cpu = float(profile.get("max_cpu", self.cfg.max_cpu))
        profile_max_mem = int(profile.get("max_mem_mb", self.cfg.max_mem_mb))
        profile_max_timeout = int(profile.get("timeout_sec", 300))

        # Effective max is the minimum of global policy and trust profile
        effective_max_cpu = min(self.cfg.max_cpu, profile_max_cpu)
        effective_max_mem = min(self.cfg.max_mem_mb, profile_max_mem)

        # Clamp resources to effective maxima
        try:
            if spec.cpu_limit is None:
                spec.cpu_limit = effective_max_cpu
            elif spec.cpu_limit > effective_max_cpu:
                spec.cpu_limit = float(effective_max_cpu)
        except Exception:
            pass
        try:
            if spec.memory_mb is None:
                spec.memory_mb = effective_max_mem
            elif spec.memory_mb > effective_max_mem:
                spec.memory_mb = int(effective_max_mem)
        except Exception:
            pass
        try:
            if spec.timeout_sec > profile_max_timeout:
                spec.timeout_sec = profile_max_timeout
        except Exception:
            pass

        return spec

    def apply_to_run(
        self,
        spec: RunSpec,
        firecracker_available: bool,
        lima_available: bool = False,
    ) -> RunSpec:
        # Always go through selection to enforce availability on defaults
        spec.runtime = self.select_runtime(spec.runtime, firecracker_available, lima_available)

        # Apply trust-level profile constraints
        trust = spec.trust_level or TrustLevel.standard
        profile = TRUST_PROFILES.get(trust, TRUST_PROFILES[TrustLevel.standard])

        if not spec.network_policy:
            spec.network_policy = profile.get("network_policy", self.cfg.network_default)

        # Apply trust-level resource limits (more restrictive of trust profile and global policy)
        profile_max_cpu = float(profile.get("max_cpu", self.cfg.max_cpu))
        profile_max_mem = int(profile.get("max_mem_mb", self.cfg.max_mem_mb))
        profile_max_timeout = int(profile.get("timeout_sec", 300))

        # Effective max is the minimum of global policy and trust profile
        effective_max_cpu = min(self.cfg.max_cpu, profile_max_cpu)
        effective_max_mem = min(self.cfg.max_mem_mb, profile_max_mem)

        # Clamp resources to effective maxima
        try:
            if spec.cpu is None:
                spec.cpu = effective_max_cpu
            elif spec.cpu > effective_max_cpu:
                spec.cpu = float(effective_max_cpu)
        except Exception:
            pass
        try:
            if spec.memory_mb is None:
                spec.memory_mb = effective_max_mem
            elif spec.memory_mb > effective_max_mem:
                spec.memory_mb = int(effective_max_mem)
        except Exception:
            pass
        try:
            if spec.timeout_sec > profile_max_timeout:
                spec.timeout_sec = profile_max_timeout
        except Exception:
            pass

        return spec


def _canonical_policy_dict(cfg: SandboxPolicyConfig) -> dict:
    """Build a canonical, stable dict capturing policy-affecting settings.

    The material intentionally avoids environment-specific paths and
    includes only values that impact sandbox behavior and security.
    """
    try:
        # Runner security toggles (booleans for determinism)
        docker_seccomp_enabled = bool(getattr(app_settings, "SANDBOX_DOCKER_SECCOMP", None))
    except Exception:
        docker_seccomp_enabled = False
    try:
        docker_apparmor_enabled = bool(getattr(app_settings, "SANDBOX_DOCKER_APPARMOR_PROFILE", None))
    except Exception:
        docker_apparmor_enabled = False
    try:
        ul_nofile = int(getattr(app_settings, "SANDBOX_ULIMIT_NOFILE", 1024))
    except Exception:
        ul_nofile = 1024
    try:
        ul_nproc = int(getattr(app_settings, "SANDBOX_ULIMIT_NPROC", 512))
    except Exception:
        ul_nproc = 512

    # Normalize supported spec versions list
    spec_versions = list(cfg.supported_spec_versions or ["1.0"])
    spec_versions = sorted(str(v) for v in spec_versions)

    material = {
        "default_runtime": cfg.default_runtime.value,
        "network_default": str(cfg.network_default),
        "egress": {
            "enforced": bool(cfg.egress_enforcement),
            "allowlist_count": int(len(cfg.egress_allowlist or [])),
        },
        "artifact_ttl_hours": int(cfg.artifact_ttl_hours),
        "max_upload_mb": int(cfg.max_upload_mb),
        "max_log_bytes": int(cfg.max_log_bytes),
        "pids_limit": int(cfg.pids_limit),
        "max_cpu": float(cfg.max_cpu),
        "max_mem_mb": int(cfg.max_mem_mb),
        "workspace_cap_mb": int(cfg.workspace_cap_mb),
        "supported_spec_versions": spec_versions,
        # Runner-level security primitives
        "security": {
            "docker_seccomp": bool(docker_seccomp_enabled),
            "docker_apparmor": bool(docker_apparmor_enabled),
            "ulimit_nofile": int(ul_nofile),
            "ulimit_nproc": int(ul_nproc),
        },
    }
    return material


def compute_policy_hash(cfg: SandboxPolicyConfig) -> str:
    """Return a short, reproducible hash for the canonical policy material.

    Uses sha256 of the canonical JSON (sorted keys, compact separators) and
    returns the first 16 hex chars for brevity, as used elsewhere.
    """
    mat = _canonical_policy_dict(cfg)
    canon = json.dumps(mat, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]
