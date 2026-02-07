from __future__ import annotations

import os
from typing import Any

from loguru import logger

try:
    from tldw_Server_API.app.core.config import settings
except Exception:  # pragma: no cover - config import fallback
    settings = None  # type: ignore[assignment]


_PROMPT_STUDIO_DOMAIN = "PROMPT_STUDIO"
_QUOTA_ENV_MAP = {
    "PROMPT_STUDIO_MAX_CONCURRENT_JOBS": f"JOBS_QUOTA_MAX_INFLIGHT_{_PROMPT_STUDIO_DOMAIN}",
    "PROMPT_STUDIO_JOBS_MAX_QUEUED": f"JOBS_QUOTA_MAX_QUEUED_{_PROMPT_STUDIO_DOMAIN}",
    "PROMPT_STUDIO_JOBS_SUBMITS_PER_MIN": f"JOBS_QUOTA_SUBMITS_PER_MIN_{_PROMPT_STUDIO_DOMAIN}",
}
_USER_PROFILE_QUOTA_KEYS = {
    "limits.prompt_studio_max_concurrent_jobs": "JOBS_QUOTA_MAX_INFLIGHT_PROMPT_STUDIO_USER_{user_id}",
    "limits.prompt_studio_max_queued_jobs": "JOBS_QUOTA_MAX_QUEUED_PROMPT_STUDIO_USER_{user_id}",
    "limits.prompt_studio_submits_per_min": "JOBS_QUOTA_SUBMITS_PER_MIN_PROMPT_STUDIO_USER_{user_id}",
}
_APPLIED_USER_QUOTAS: dict[str, set[str]] = {}


def _parse_quota(value: str) -> int | None:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _read_setting(key: str) -> str | None:
    env_value = os.getenv(key)
    if env_value is not None and str(env_value).strip() != "":
        return env_value
    if settings is not None:
        try:
            value = settings.get(key)
        except Exception:
            value = None
        if value is not None:
            return str(value)
    return env_value


def apply_prompt_studio_quota_defaults() -> dict[str, int]:
    """Apply Prompt Studio quota defaults to core Jobs env vars."""
    applied: dict[str, int] = {}
    for source_key, target_key in _QUOTA_ENV_MAP.items():
        if os.getenv(target_key):
            continue
        raw = _read_setting(source_key)
        if raw is None or str(raw).strip() == "":
            continue
        parsed = _parse_quota(raw)
        if parsed is None:
            logger.warning("Prompt Studio quota env {}={} is invalid; ignoring", source_key, raw)
            continue
        os.environ[target_key] = str(parsed)
        applied[target_key] = parsed
    return applied


async def _load_effective_config(user_id: int) -> dict[str, Any]:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
    from tldw_Server_API.app.core.UserProfiles.service import UserProfileService

    db_pool = await get_db_pool()
    service = UserProfileService(db_pool)
    return await service._build_effective_config(
        int(user_id),
        include_sources=False,
        mask_secrets=True,
    )


async def apply_prompt_studio_quota_policy(user_id: str) -> dict[str, int]:
    """Apply per-user Prompt Studio quotas from AuthNZ policy/DB overrides."""
    if not user_id:
        return {}
    if str(os.getenv("TEST_MODE", "")).lower() in {"1", "true", "yes", "on"}:
        return {}
    try:
        user_id_int = int(str(user_id))
    except (TypeError, ValueError):
        return {}

    try:
        effective = await _load_effective_config(user_id_int)
    except Exception as exc:
        logger.debug("Prompt Studio quota policy lookup failed for user {}: {}", user_id, exc)
        return {}

    applied: dict[str, int] = {}
    active_keys: set[str] = set()
    for profile_key, env_fmt in _USER_PROFILE_QUOTA_KEYS.items():
        raw = effective.get(profile_key)
        if raw is None:
            continue
        parsed = _parse_quota(raw)
        if parsed is None:
            logger.debug("Prompt Studio quota policy invalid for {}: {}", profile_key, raw)
            continue
        env_key = env_fmt.format(user_id=user_id_int)
        os.environ[env_key] = str(parsed)
        applied[env_key] = parsed
        active_keys.add(env_key)

    user_key = str(user_id_int)
    previous = _APPLIED_USER_QUOTAS.get(user_key, set())
    for stale_key in previous - active_keys:
        if stale_key in os.environ:
            del os.environ[stale_key]
    _APPLIED_USER_QUOTAS[user_key] = active_keys
    return applied
