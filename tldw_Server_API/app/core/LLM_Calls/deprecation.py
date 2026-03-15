from __future__ import annotations

from tldw_Server_API.app.core.deprecations import log_runtime_deprecation


def log_legacy_once(key: str, message: str) -> None:
    log_runtime_deprecation(key, message=message)
