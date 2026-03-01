# rate_limiter.py
# Per-user rate limiting for embeddings service
#
# Phase 2 Deprecation Notice
# ─────────────────────────────────────────────────────────────
# This module is a **Phase 2 legacy shim**. Primary rate-limit enforcement is
# handled by the Resource Governor (``RGSimpleMiddleware`` + per-module RG
# integration). When RG is unavailable or disabled, the shim fails open (no
# counters, no enforcement) with a deprecation warning. This shim will be
# removed in a future release.
# ─────────────────────────────────────────────────────────────

import asyncio
import configparser
import os
import time
import warnings
from typing import Optional

from loguru import logger

try:
    # Resource Governor (optional; enabled via RG flags)
    from tldw_Server_API.app.core.config import rg_enabled  # type: ignore
    from tldw_Server_API.app.core.Resource_Governance import (
        MemoryResourceGovernor,
        RedisResourceGovernor,
        RGRequest,
    )
    from tldw_Server_API.app.core.Resource_Governance.policy_loader import (
        PolicyLoader,
        PolicyReloadConfig,
        default_policy_loader,
    )
except Exception:  # pragma: no cover - RG is optional for embeddings
    MemoryResourceGovernor = None  # type: ignore
    RedisResourceGovernor = None  # type: ignore
    RGRequest = None  # type: ignore
    PolicyLoader = None  # type: ignore
    PolicyReloadConfig = None  # type: ignore
    default_policy_loader = None  # type: ignore
    rg_enabled = None  # type: ignore

_EMBEDDINGS_DEPRECATION_WARNED = False


def _emit_embeddings_legacy_deprecation(context: str) -> None:
    global _EMBEDDINGS_DEPRECATION_WARNED
    if _EMBEDDINGS_DEPRECATION_WARNED:
        return
    _EMBEDDINGS_DEPRECATION_WARNED = True
    msg = (
        "Embeddings legacy rate limiter is deprecated (Phase 2). "
        f"Context: {context}. Enable RG_ENABLED=true for enforcement. "
        "This shim will be removed in a future release."
    )
    warnings.warn(msg, DeprecationWarning, stacklevel=3)
    logger.warning(msg)


class UserRateLimiter:
    """
    Per-user rate limiter (Phase 2 shim).

    **Phase 2 Deprecation Notice**:
    All enforcement is delegated to Resource Governor. When RG is disabled or
    unavailable, this shim fails open with a deprecation warning. No internal
    counters or deques are maintained. This shim will be removed in a future
    release.
    """

    def __init__(
        self,
        default_limit: int = 60,
        window_seconds: int = 60,
        premium_limit: int = 200,
        burst_allowance: float = 1.5,
    ):
        # Config preserved for API compatibility.
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.premium_limit = premium_limit
        self.burst_allowance = burst_allowance
        self.user_tiers: dict[str, str] = {}

        logger.info(
            f"UserRateLimiter initialized (Phase 2 shim): "
            f"default_limit={default_limit}/{window_seconds}s, "
            f"premium_limit={premium_limit}/{window_seconds}s"
        )

    def set_user_tier(self, user_id: str, tier: str) -> None:
        """Set the tier for a user (no-op for enforcement, config only)."""
        self.user_tiers[user_id] = tier

    def get_user_limit(self, user_id: str) -> int:
        """Get the rate limit for a specific user."""
        tier = self.user_tiers.get(user_id, 'free')
        if tier in ['premium', 'enterprise']:
            return self.premium_limit
        return self.default_limit

    def check_rate_limit(
        self,
        user_id: str,
        cost: int = 1,
        ip_address: Optional[str] = None,
    ) -> tuple[bool, Optional[int]]:
        """Always allows (Phase 2 shim: no counters)."""
        _emit_embeddings_legacy_deprecation("check_rate_limit")
        return True, None

    def get_user_usage(self, user_id: str) -> dict[str, any]:
        """Return config-only usage stats (no request tracking)."""
        limit = self.get_user_limit(user_id)
        return {
            "user_id": user_id,
            "tier": self.user_tiers.get(user_id, 'free'),
            "current_usage": 0,
            "limit": limit,
            "burst_limit": int(limit * self.burst_allowance),
            "window_seconds": self.window_seconds,
            "percentage_used": 0,
            "requests_remaining": limit,
            "rate_limit_source": "resource_governor",
        }

    def get_statistics(self) -> dict[str, any]:
        """Return static statistics (no request tracking)."""
        return {
            "total_requests": 0,
            "total_blocked": 0,
            "block_rate": 0,
            "active_users": 0,
            "window_seconds": self.window_seconds,
            "default_limit": self.default_limit,
            "premium_limit": self.premium_limit,
            "rate_limit_source": "resource_governor",
        }


# Global rate limiter instance
_rate_limiter: Optional[UserRateLimiter] = None


def get_rate_limiter() -> UserRateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        # Prefer Embeddings-specific config and environment overrides; fall back gracefully
        try:
            from tldw_Server_API.app.core.config import load_comprehensive_config
            cfg = load_comprehensive_config()
            emb_cfg = {}
            try:
                if cfg and cfg.has_section('Embeddings-Module'):
                    emb_cfg = dict(cfg.items('Embeddings-Module'))
            except (AttributeError, KeyError, TypeError, configparser.Error) as exc:
                logger.debug(f"Embeddings rate limiter: failed to read Embeddings-Module config: {exc}")
                emb_cfg = {}

            # Environment overrides take precedence
            import os
            rate_limit = None
            win_seconds = None
            premium_limit = None

            try:
                env_rate = os.getenv('EMBEDDINGS_RATE_LIMIT_PER_MINUTE')
                if env_rate is not None:
                    rate_limit = max(1, int(env_rate))
            except (TypeError, ValueError) as exc:
                logger.debug(f"Embeddings rate limiter: invalid EMBEDDINGS_RATE_LIMIT_PER_MINUTE: {exc}")
            try:
                env_win = os.getenv('EMBEDDINGS_WINDOW_SECONDS')
                if env_win is not None:
                    win_seconds = max(1, int(env_win))
            except (TypeError, ValueError) as exc:
                logger.debug(f"Embeddings rate limiter: invalid EMBEDDINGS_WINDOW_SECONDS: {exc}")
            try:
                env_pl = os.getenv('EMBEDDINGS_PREMIUM_LIMIT')
                if env_pl is not None:
                    premium_limit = max(1, int(env_pl))
            except (TypeError, ValueError) as exc:
                logger.debug(f"Embeddings rate limiter: invalid EMBEDDINGS_PREMIUM_LIMIT: {exc}")

            # Config fallbacks if envs are not set
            if rate_limit is None:
                if 'rate_limit_per_minute' in emb_cfg:
                    try:
                        rate_limit = max(1, int(emb_cfg.get('rate_limit_per_minute', 60)))
                    except (TypeError, ValueError) as exc:
                        logger.debug(f"Embeddings rate limiter: invalid rate_limit_per_minute: {exc}")
                        rate_limit = 60
                else:
                    # Legacy fallback to Chat-Module if Embeddings not configured
                    chat_cfg = {}
                    try:
                        if cfg and cfg.has_section('Chat-Module'):
                            chat_cfg = dict(cfg.items('Chat-Module'))
                    except (AttributeError, KeyError, TypeError, configparser.Error) as exc:
                        logger.debug(f"Embeddings rate limiter: failed to read Chat-Module config: {exc}")
                        chat_cfg = {}
                    try:
                        rate_limit = max(1, int(chat_cfg.get('rate_limit_per_minute', 60)))
                    except (TypeError, ValueError) as exc:
                        logger.debug(f"Embeddings rate limiter: invalid chat rate_limit_per_minute: {exc}")
                        rate_limit = 60

            if win_seconds is None:
                if emb_cfg:
                    try:
                        win_seconds = int(emb_cfg.get('window_seconds', 60))
                    except (TypeError, ValueError) as exc:
                        logger.debug(f"Embeddings rate limiter: invalid window_seconds: {exc}")
                        win_seconds = 60
                else:
                    win_seconds = 60

            if premium_limit is None:
                # Allow premium multiplier or absolute limit
                try:
                    mult = emb_cfg.get('premium_multiplier') if emb_cfg else None
                    premium_limit = int(float(mult) * rate_limit) if mult is not None else rate_limit * 3
                except (TypeError, ValueError) as exc:
                    logger.debug(f"Embeddings rate limiter: invalid premium_multiplier: {exc}")
                    premium_limit = rate_limit * 3

            _rate_limiter = UserRateLimiter(
                default_limit=rate_limit,
                window_seconds=win_seconds,
                premium_limit=premium_limit,
            )
        except (AttributeError, ImportError, KeyError, OSError, TypeError, ValueError, configparser.Error) as e:
            logger.warning(f"Could not load embeddings rate limit config: {e}. Using defaults.")
            _rate_limiter = UserRateLimiter()

    return _rate_limiter


def check_user_rate_limit(
    user_id: str,
    cost: int = 1,
    ip_address: Optional[str] = None
) -> tuple[bool, Optional[int]]:
    """
    Convenience function to check rate limit for a user.

    Args:
        user_id: User identifier
        cost: Cost of the request
        ip_address: IP address of the request

    Returns:
        Tuple of (allowed, retry_after_seconds)
    """
    limiter = get_rate_limiter()
    return limiter.check_rate_limit(user_id, cost, ip_address)


# Async extensions for rate limiting


class AsyncRateLimiter:
    """Async rate limiter for embeddings (Phase 2 shim)."""

    def __init__(self, rate_limiter: Optional[UserRateLimiter] = None):
        self.rate_limiter = rate_limiter
        self.executor = None

    async def check_rate_limit_async(
        self,
        user_id: str,
        cost: int = 1,
        ip_address: Optional[str] = None,
        tokens_units: int = 0,
    ) -> tuple[bool, Optional[int]]:
        """
        Async version of check_rate_limit.

        When RG is enabled, delegates to RG. When RG is disabled or
        unavailable, fails open with a deprecation warning.
        """
        if not _rg_embeddings_enabled():
            _emit_embeddings_legacy_deprecation("rg_disabled")
            return True, None

        # Prefer Resource Governor when configured.
        rg_decision = await _maybe_enforce_with_rg(
            user_id=user_id,
            cost=cost,
            tokens_units=int(tokens_units or 0),
        )

        if rg_decision is not None:
            rg_allowed = bool(rg_decision.get("allowed", False))
            return rg_allowed, rg_decision.get("retry_after")

        _log_rg_embeddings_fallback("rg_decision_unavailable")
        _emit_embeddings_legacy_deprecation("rg_decision_unavailable")
        return True, None

    async def record_usage_async(self, user_id: str, cost: int = 1):
        """Record usage asynchronously (for post-processing)"""
        pass

    async def get_user_usage_async(self, user_id: str) -> dict[str, any]:
        """Get user usage statistics asynchronously"""
        if self.rate_limiter is None:
            return {"available": False, "reason": "rate_limiter_disabled", "rate_limit_source": "resource_governor"}
        return self.rate_limiter.get_user_usage(user_id)


# Global async rate limiter
_async_rate_limiter: Optional[AsyncRateLimiter] = None


def get_async_rate_limiter() -> AsyncRateLimiter:
    """Get or create the global async rate limiter."""
    global _async_rate_limiter
    if _async_rate_limiter is None:
        _async_rate_limiter = AsyncRateLimiter()
    return _async_rate_limiter


# --- Resource Governor plumbing (optional) ---
_rg_embeddings_governor = None
_rg_embeddings_loader = None
_rg_embeddings_lock = asyncio.Lock()
_rg_embeddings_init_error: Optional[str] = None
_rg_embeddings_init_error_logged = False
_rg_embeddings_fallback_logged = False

_rate_limit_mode_warned = False


def _rate_limit_mode() -> str:
    """Return the embeddings rate limit mode ('tokens' or 'requests')."""
    raw = os.getenv("EMBEDDINGS_RATE_LIMIT_MODE", "tokens")
    mode = str(raw or "").strip().lower()
    if mode in {"token", "tokens", "tok"}:
        return "tokens"
    if mode in {"request", "requests", "req"}:
        return "requests"
    global _rate_limit_mode_warned
    if not _rate_limit_mode_warned:
        _rate_limit_mode_warned = True
        logger.warning(
            "Unknown EMBEDDINGS_RATE_LIMIT_MODE={}; defaulting to 'tokens'.",
            raw,
        )
    return "tokens"


def _rg_embeddings_context() -> dict[str, str]:
    policy_path = os.getenv(
        "RG_POLICY_PATH",
        "tldw_Server_API/Config_Files/resource_governor_policies.yaml",
    )
    try:
        policy_path_resolved = os.path.abspath(policy_path)
    except Exception:  # noqa: BLE001 - best-effort path resolution
        policy_path_resolved = policy_path
    return {
        "backend": os.getenv("RG_BACKEND", "memory"),
        "policy_path": policy_path,
        "policy_path_resolved": policy_path_resolved,
        "policy_store": os.getenv("RG_POLICY_STORE", ""),
        "policy_reload_enabled": os.getenv("RG_POLICY_RELOAD_ENABLED", ""),
        "policy_reload_interval": os.getenv("RG_POLICY_RELOAD_INTERVAL_SEC", ""),
        "cwd": os.getcwd(),
    }


def _log_rg_embeddings_init_failure(exc: Exception) -> None:
    global _rg_embeddings_init_error, _rg_embeddings_init_error_logged
    _rg_embeddings_init_error = repr(exc)
    if _rg_embeddings_init_error_logged:
        return
    _rg_embeddings_init_error_logged = True
    ctx = _rg_embeddings_context()
    logger.exception(
        "Embeddings ResourceGovernor init failed; compatibility shim remains diagnostics-only. "
        "backend={backend} policy_path={policy_path} policy_path_resolved={policy_path_resolved} "
        "policy_store={policy_store} reload_enabled={policy_reload_enabled} "
        "reload_interval={policy_reload_interval} cwd={cwd}",
        **ctx,
    )


def _log_rg_embeddings_fallback(reason: str) -> None:
    global _rg_embeddings_fallback_logged
    if _rg_embeddings_fallback_logged:
        return
    _rg_embeddings_fallback_logged = True
    ctx = _rg_embeddings_context()
    logger.error(
        "Embeddings ResourceGovernor unavailable; using diagnostics-only compatibility shim (no enforcement). "
        "reason={} init_error={} backend={backend} policy_path={policy_path} "
        "policy_path_resolved={policy_path_resolved} policy_store={policy_store} "
        "reload_enabled={policy_reload_enabled} reload_interval={policy_reload_interval} cwd={cwd}",
        reason,
        _rg_embeddings_init_error,
        **ctx,
    )


def _rg_embeddings_enabled() -> bool:
    if rg_enabled:
        try:
            return bool(rg_enabled(True))  # type: ignore[func-returns-value]
        except Exception:  # noqa: BLE001 - RG should never break rate limiting
            return False
    return False


async def _get_embeddings_rg_governor():
    """Lazily initialize a ResourceGovernor for embeddings if enabled."""
    global _rg_embeddings_governor, _rg_embeddings_loader
    if not _rg_embeddings_enabled():
        return None
    if RGRequest is None or PolicyLoader is None:
        _log_rg_embeddings_fallback("rg_components_unavailable")
        return None
    if _rg_embeddings_governor is not None:
        return _rg_embeddings_governor
    async with _rg_embeddings_lock:
        if _rg_embeddings_governor is not None:
            return _rg_embeddings_governor
        try:
            loader = default_policy_loader() if default_policy_loader else PolicyLoader(
                os.getenv("RG_POLICY_PATH", "tldw_Server_API/Config_Files/resource_governor_policies.yaml"),
                PolicyReloadConfig(enabled=True, interval_sec=int(os.getenv("RG_POLICY_RELOAD_INTERVAL_SEC", "10") or "10")),
            )
            await loader.load_once()
            _rg_embeddings_loader = loader
            backend = os.getenv("RG_BACKEND", "memory").lower()
            if backend == "redis" and RedisResourceGovernor is not None:
                gov = RedisResourceGovernor(policy_loader=loader)  # type: ignore[call-arg]
            else:
                gov = MemoryResourceGovernor(policy_loader=loader)  # type: ignore[call-arg]
            _rg_embeddings_governor = gov
            return gov
        except Exception as exc:  # pragma: no cover - optional path  # noqa: BLE001
            _log_rg_embeddings_init_failure(exc)
            return None


async def _maybe_enforce_with_rg(
    user_id: str,
    cost: int,
    tokens_units: int = 0,
) -> Optional[dict[str, object]]:
    """
    Attempt to enforce embeddings limits via Resource Governor.

    Requests are enforced at ingress via `RGSimpleMiddleware`. This helper is
    used for token accounting and diagnostics-only behavior when RG is
    unavailable, and MUST NOT reserve `requests` to avoid double-enforcement
    on RG-governed routes.

    Returns a decision dict when RG is used, or None when RG is unavailable/disabled.
    """
    gov = await _get_embeddings_rg_governor()
    if gov is None:
        return None
    policy_id = os.getenv("RG_EMBEDDINGS_POLICY_ID", "embeddings.default")
    op_id = f"emb-{user_id}-{time.time_ns()}"
    try:
        try:
            tu = int(tokens_units or 0)
        except Exception:  # noqa: BLE001 - defensive conversion
            tu = 0
        tu = max(0, tu)

        # Only enforce token budgets here; request-rate limiting happens at ingress.
        categories: dict[str, dict[str, int]] = {}
        if tu > 0:
            categories["tokens"] = {"units": tu}
        else:
            # No token units to enforce; allow and bypass compatibility shim.
            return {"allowed": True, "retry_after": None, "policy_id": policy_id}

        decision, handle = await gov.reserve(
            RGRequest(
                entity=f"user:{user_id}",
                categories=categories,
                tags={"policy_id": policy_id, "module": "embeddings"},
            ),
            op_id=op_id,
        )
        if decision.allowed:
            # Treat reserve as consumption and finalize immediately to keep semantics simple.
            if handle:
                try:
                    await gov.commit(handle, None, op_id=op_id)
                except Exception:  # noqa: BLE001 - logging-only fallback
                    logger.debug("Embeddings RG commit failed", exc_info=True)
            return {"allowed": True, "retry_after": None, "policy_id": policy_id}
        return {
            "allowed": False,
            "retry_after": decision.retry_after or 1,
            "policy_id": policy_id,
        }
    except Exception as exc:  # noqa: BLE001 - diagnostics-only shim on RG errors
        logger.debug(f"Embeddings RG reserve failed; using diagnostics-only shim path: {exc}")
        return None
