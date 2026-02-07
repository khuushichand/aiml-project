from __future__ import annotations

import os
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.byok_config import (
    PROVIDER_APP_CONFIG_KEYS,
    merge_app_config_overrides,
)
from tldw_Server_API.app.core.AuthNZ.byok_helpers import (
    is_byok_enabled,
    is_provider_allowlisted,
    is_trusted_base_url_request,
    resolve_byok_base_url_allowlist,
    resolve_server_default_key,
    validate_credential_fields,
)
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.orgs_teams import list_memberships_for_user
from tldw_Server_API.app.core.AuthNZ.repos.org_provider_secrets_repo import (
    AuthnzOrgProviderSecretsRepo,
)
from tldw_Server_API.app.core.AuthNZ.repos.user_provider_secrets_repo import (
    AuthnzUserProviderSecretsRepo,
)
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
    decrypt_byok_payload,
    loads_envelope,
    normalize_provider_name,
)
from tldw_Server_API.app.core.config import loaded_config_data
from tldw_Server_API.app.core.Metrics import increment_counter

DEFAULT_LAST_USED_THROTTLE_SECONDS = 300

_BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    ConnectionError,
    EOFError,
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
    UnicodeDecodeError,
    ValueError,
)


def _last_used_throttle_seconds() -> int:
    raw = os.getenv("BYOK_LAST_USED_THROTTLE_SECONDS")
    if not raw:
        return DEFAULT_LAST_USED_THROTTLE_SECONDS
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_LAST_USED_THROTTLE_SECONDS


def _parse_last_used(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS:
            return None
    return None


def _should_touch(last_used_at: datetime | None) -> bool:
    if last_used_at is None:
        return True
    throttle = _last_used_throttle_seconds()
    if throttle <= 0:
        return True
    delta = datetime.now(timezone.utc) - last_used_at
    return delta.total_seconds() >= throttle


def _bool_label(value: bool) -> str:
    return "true" if value else "false"


def _can_use_base_url_override(provider: str, request: Any | None) -> bool:
    if not is_trusted_base_url_request(request):
        return False
    provider_norm = normalize_provider_name(provider)
    return provider_norm in resolve_byok_base_url_allowlist()


def _sanitize_credential_fields(
    provider: str,
    credential_fields_raw: Any,
    *,
    allow_base_url: bool,
) -> dict[str, Any]:
    if credential_fields_raw is None:
        return {}
    if not isinstance(credential_fields_raw, dict):
        raise ValueError("credential_fields must be an object")

    cleaned = dict(credential_fields_raw)
    if not allow_base_url and "base_url" in cleaned:
        cleaned.pop("base_url", None)
        logger.debug("BYOK base_url override ignored for provider={}", provider)

    return validate_credential_fields(provider, cleaned, allow_base_url=allow_base_url)


def _apply_active_scope(ids: list[int], active_id: Any) -> list[int]:
    if not ids:
        return []
    if active_id is None:
        return ids if len(ids) == 1 else []
    try:
        active = int(active_id)
    except (TypeError, ValueError):
        return []
    return [active] if active in ids else []


@dataclass
class ResolvedByokCredentials:
    provider: str
    api_key: str | None
    app_config: dict[str, Any] | None
    credential_fields: dict[str, Any]
    source: str
    allowlisted: bool
    _touch_cb: Callable[[], Awaitable[None]] | None = None

    @property
    def uses_byok(self) -> bool:
        return self.source in {"user", "team", "org"}

    async def touch_last_used(self) -> None:
        if not self._touch_cb:
            return
        try:
            await self._touch_cb()
        except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"BYOK last_used_at update failed for {self.provider}: {exc}")


def _record_byok_resolution(resolved: ResolvedByokCredentials, *, byok_enabled: bool) -> None:
    """Emit a counter entry for BYOK credential resolution."""
    try:
        increment_counter(
            "byok_resolution_total",
            labels={
                "provider": resolved.provider,
                "source": resolved.source,
                "allowlisted": _bool_label(resolved.allowlisted),
                "byok_enabled": _bool_label(byok_enabled),
            },
        )
    except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(f"BYOK resolution metrics failed for {resolved.provider}: {exc}")


def record_byok_missing_credentials(provider: str, *, operation: str) -> None:
    """Emit a counter entry for missing provider credentials."""
    provider_norm = normalize_provider_name(provider)
    try:
        allowlisted = is_provider_allowlisted(provider_norm)
    except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS:
        allowlisted = False
    try:
        byok_enabled = is_byok_enabled()
    except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS:
        byok_enabled = False
    try:
        increment_counter(
            "byok_missing_credentials_total",
            labels={
                "provider": provider_norm,
                "operation": operation,
                "allowlisted": _bool_label(allowlisted),
                "byok_enabled": _bool_label(byok_enabled),
            },
        )
    except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(f"BYOK missing-credentials metrics failed for {provider_norm}: {exc}")


def _finalize_resolution(
    resolved: ResolvedByokCredentials,
    *,
    byok_enabled: bool,
) -> ResolvedByokCredentials:
    _record_byok_resolution(resolved, byok_enabled=byok_enabled)
    return resolved


async def _get_user_repo() -> AuthnzUserProviderSecretsRepo:
    pool = await get_db_pool()
    return AuthnzUserProviderSecretsRepo(pool)


async def _get_org_repo() -> AuthnzOrgProviderSecretsRepo:
    pool = await get_db_pool()
    return AuthnzOrgProviderSecretsRepo(pool)


def _fallback_result(
    provider: str,
    *,
    allowlisted: bool,
    fallback_resolver: Callable[[str], str | None] | None,
) -> ResolvedByokCredentials:
    api_key = None
    if fallback_resolver is not None:
        try:
            api_key = fallback_resolver(provider)
        except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"BYOK fallback resolver failed for {provider}: {exc}")
            api_key = None
    if api_key is None:
        api_key = resolve_server_default_key(provider)
    source = "server_default" if api_key else "none"
    return ResolvedByokCredentials(
        provider=provider,
        api_key=api_key,
        app_config=None,
        credential_fields={},
        source=source,
        allowlisted=allowlisted,
        _touch_cb=None,
    )


def _invalid_byok_result(provider: str, *, source: str) -> ResolvedByokCredentials:
    return ResolvedByokCredentials(
        provider=provider,
        api_key=None,
        app_config=None,
        credential_fields={},
        source=source,
        allowlisted=True,
        _touch_cb=None,
    )


def _build_app_config(provider: str, credential_fields: dict[str, Any]) -> dict[str, Any] | None:
    if not credential_fields:
        return None
    try:
        base_cfg = loaded_config_data
    except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS:
        base_cfg = None
    provider_norm = normalize_provider_name(provider)
    scrubbed_cfg: dict[str, Any] | None = None
    if base_cfg:
        try:
            section = PROVIDER_APP_CONFIG_KEYS.get(provider_norm)
            if section and isinstance(base_cfg.get(section), dict):
                cleaned = {
                    k: v
                    for k, v in base_cfg.get(section, {}).items()
                    if k not in {"api_base_url", "org_id", "project_id"}
                }
                scrubbed_cfg = dict(base_cfg)
                scrubbed_cfg[section] = cleaned
            else:
                scrubbed_cfg = dict(base_cfg)
        except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS:
            scrubbed_cfg = None
    merged = merge_app_config_overrides(scrubbed_cfg if scrubbed_cfg else None, provider, credential_fields)
    return merged or None


def _extract_payload(row: dict[str, Any], provider: str) -> dict[str, Any] | None:
    encrypted_blob = row.get("encrypted_blob")
    if not encrypted_blob:
        return None
    try:
        return decrypt_byok_payload(loads_envelope(encrypted_blob))
    except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"BYOK decrypt failed for provider={provider}: {exc}")
        return None


def _build_touch_cb(
    *,
    provider: str,
    last_used_at: datetime | None,
    repo: AuthnzUserProviderSecretsRepo | AuthnzOrgProviderSecretsRepo,
    user_id: int | None = None,
    scope_type: str | None = None,
    scope_id: int | None = None,
) -> Callable[[], Awaitable[None]]:
    async def _touch() -> None:
        if not _should_touch(last_used_at):
            return
        now = datetime.now(timezone.utc)
        if isinstance(repo, AuthnzUserProviderSecretsRepo):
            if user_id is None:
                return
            await repo.touch_last_used(int(user_id), provider, now)
        else:
            if not scope_type or scope_id is None:
                return
            await repo.touch_last_used(scope_type, int(scope_id), provider, now)

    return _touch


async def resolve_byok_credentials(
    provider: str,
    *,
    user_id: int | None,
    request: Any | None = None,
    team_ids: list[int] | None = None,
    org_ids: list[int] | None = None,
    fallback_resolver: Callable[[str], str | None] | None = None,
) -> ResolvedByokCredentials:
    provider_norm = normalize_provider_name(provider)
    byok_enabled = is_byok_enabled()
    allowlisted = is_provider_allowlisted(provider_norm)
    allow_base_url = _can_use_base_url_override(provider_norm, request)

    if not byok_enabled or user_id is None or not allowlisted:
        return _finalize_resolution(
            _fallback_result(
                provider_norm,
                allowlisted=allowlisted,
                fallback_resolver=fallback_resolver,
            ),
            byok_enabled=byok_enabled,
        )

    # Resolve user key
    try:
        user_repo = await _get_user_repo()
        user_row = await user_repo.fetch_secret_for_user(int(user_id), provider_norm)
    except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(f"BYOK user lookup failed for user_id={user_id}, provider={provider_norm}: {exc}")
        user_row = None

    if user_row:
        payload = _extract_payload(user_row, provider_norm)
        if payload:
            api_key = payload.get("api_key")
            if api_key:
                credential_fields_raw = payload.get("credential_fields") or {}
                try:
                    credential_fields = _sanitize_credential_fields(
                        provider_norm,
                        credential_fields_raw,
                        allow_base_url=allow_base_url,
                    )
                except ValueError as exc:
                    logger.warning(
                        "BYOK credential_fields invalid for user_id=%s provider=%s: %s",
                        user_id,
                        provider_norm,
                        exc,
                    )
                    return _finalize_resolution(
                        _invalid_byok_result(provider_norm, source="user"),
                        byok_enabled=byok_enabled,
                    )
                last_used_at = _parse_last_used(user_row.get("last_used_at"))
                return _finalize_resolution(
                    ResolvedByokCredentials(
                        provider=provider_norm,
                        api_key=api_key,
                        app_config=_build_app_config(provider_norm, credential_fields),
                        credential_fields=credential_fields,
                        source="user",
                        allowlisted=True,
                        _touch_cb=_build_touch_cb(
                            provider=provider_norm,
                            last_used_at=last_used_at,
                            repo=user_repo,
                            user_id=int(user_id),
                        ),
                    ),
                    byok_enabled=byok_enabled,
                )

    # Determine org/team scopes if not supplied
    active_team_id = None
    active_org_id = None
    if request is not None and hasattr(request, "state"):
        try:
            active_team_id = getattr(request.state, "active_team_id", None)
        except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS:
            active_team_id = None
        try:
            active_org_id = getattr(request.state, "active_org_id", None)
        except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS:
            active_org_id = None

    if team_ids is None or org_ids is None:
        try:
            if request is not None and hasattr(request, "state"):
                if team_ids is None:
                    team_ids = list(getattr(request.state, "team_ids", None) or [])
                if org_ids is None:
                    org_ids = list(getattr(request.state, "org_ids", None) or [])
        except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS:
            team_ids = team_ids or []
            org_ids = org_ids or []

    if team_ids is None or org_ids is None:
        try:
            memberships = await list_memberships_for_user(int(user_id))
            if team_ids is None:
                team_ids = [
                    m.get("team_id") for m in memberships if m.get("team_id") is not None
                ]
            if org_ids is None:
                org_ids = sorted(
                    {m.get("org_id") for m in memberships if m.get("org_id") is not None}
                )
        except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"BYOK membership lookup failed for user_id={user_id}: {exc}")
            team_ids = team_ids or []
            org_ids = org_ids or []

    team_ids = team_ids or []
    org_ids = org_ids or []
    team_ids = _apply_active_scope(team_ids, active_team_id)
    org_ids = _apply_active_scope(org_ids, active_org_id)

    try:
        shared_repo = await _get_org_repo()
    except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug(f"BYOK shared repo init failed: {exc}")
        shared_repo = None

    if shared_repo:
        # Prefer team scope over org scope, mirroring list_user_provider_keys()
        for team_id in sorted({int(tid) for tid in team_ids if tid is not None}):
            try:
                row = await shared_repo.fetch_secret("team", int(team_id), provider_norm)
            except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"BYOK team lookup failed for team_id={team_id}: {exc}")
                row = None
            if not row:
                continue
            payload = _extract_payload(row, provider_norm)
            if not payload:
                continue
            api_key = payload.get("api_key")
            if not api_key:
                continue
            credential_fields_raw = payload.get("credential_fields") or {}
            try:
                credential_fields = _sanitize_credential_fields(
                    provider_norm,
                    credential_fields_raw,
                    allow_base_url=allow_base_url,
                )
            except ValueError as exc:
                logger.warning(
                    "BYOK credential_fields invalid for team_id=%s provider=%s: %s",
                    team_id,
                    provider_norm,
                    exc,
                )
                return _finalize_resolution(
                    _invalid_byok_result(provider_norm, source="team"),
                    byok_enabled=byok_enabled,
                )
            last_used_at = _parse_last_used(row.get("last_used_at"))
            return _finalize_resolution(
                ResolvedByokCredentials(
                    provider=provider_norm,
                    api_key=api_key,
                        app_config=_build_app_config(provider_norm, credential_fields),
                        credential_fields=credential_fields,
                        source="team",
                        allowlisted=True,
                        _touch_cb=_build_touch_cb(
                            provider=provider_norm,
                            last_used_at=last_used_at,
                            repo=shared_repo,
                        scope_type="team",
                        scope_id=int(team_id),
                    ),
                ),
                byok_enabled=byok_enabled,
            )

        for org_id in sorted({int(oid) for oid in org_ids if oid is not None}):
            try:
                row = await shared_repo.fetch_secret("org", int(org_id), provider_norm)
            except _BYOK_RUNTIME_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"BYOK org lookup failed for org_id={org_id}: {exc}")
                row = None
            if not row:
                continue
            payload = _extract_payload(row, provider_norm)
            if not payload:
                continue
            api_key = payload.get("api_key")
            if not api_key:
                continue
            credential_fields_raw = payload.get("credential_fields") or {}
            try:
                credential_fields = _sanitize_credential_fields(
                    provider_norm,
                    credential_fields_raw,
                    allow_base_url=allow_base_url,
                )
            except ValueError as exc:
                logger.warning(
                    "BYOK credential_fields invalid for org_id=%s provider=%s: %s",
                    org_id,
                    provider_norm,
                    exc,
                )
                return _finalize_resolution(
                    _invalid_byok_result(provider_norm, source="org"),
                    byok_enabled=byok_enabled,
                )
            last_used_at = _parse_last_used(row.get("last_used_at"))
            return _finalize_resolution(
                ResolvedByokCredentials(
                    provider=provider_norm,
                    api_key=api_key,
                    app_config=_build_app_config(provider_norm, credential_fields),
                    credential_fields=credential_fields,
                    source="org",
                    allowlisted=True,
                    _touch_cb=_build_touch_cb(
                        provider=provider_norm,
                        last_used_at=last_used_at,
                        repo=shared_repo,
                        scope_type="org",
                        scope_id=int(org_id),
                    ),
                ),
                byok_enabled=byok_enabled,
            )

    return _finalize_resolution(
        _fallback_result(
            provider_norm,
            allowlisted=allowlisted,
            fallback_resolver=fallback_resolver,
        ),
        byok_enabled=byok_enabled,
    )
