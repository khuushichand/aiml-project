from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import (
    DatabasePool,
    _apply_single_user_fallback,
)

_SQLITE_INTEGRITY_CHECK_NONCRITICAL_EXCEPTIONS = (
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    sqlite3.Error,
)


def _resolve_authnz_sqlite_path(*, database_url: str, auth_mode: str) -> Path | None:
    raw_url = str(database_url or "").strip()
    if not raw_url:
        return None

    resolved_url = _apply_single_user_fallback(raw_url, auth_mode=auth_mode)
    _, _, fs_path = DatabasePool._resolve_sqlite_paths(resolved_url)
    if not fs_path:
        return None
    if str(fs_path).strip() == ":memory:":
        return None

    db_path = Path(fs_path)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    return db_path.resolve()


def _sqlite_ro_uri(path: Path) -> str:
    return f"file:{quote(str(path), safe='/:')}?mode=ro"


def _run_sqlite_pragma_check(
    *,
    db_path: Path,
    pragma_sql: str,
    timeout_seconds: float,
) -> list[str]:
    timeout = max(0.1, float(timeout_seconds))
    busy_timeout_ms = int(timeout * 1000)
    uri = _sqlite_ro_uri(db_path)

    with sqlite3.connect(uri, uri=True, timeout=timeout) as conn:
        conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        rows = conn.execute(pragma_sql).fetchall()

    results: list[str] = []
    for row in rows:
        if not row:
            continue
        value = str(row[0]).strip()
        if value:
            results.append(value)
    return results


async def _dispatch_integrity_alert(
    *,
    db_path: str,
    quick_check_result: str,
    integrity_sample: str,
    error_detail: str,
) -> None:
    try:
        from tldw_Server_API.app.core.AuthNZ.alerting import get_security_alert_dispatcher

        dispatcher = get_security_alert_dispatcher()
        await dispatcher.dispatch(
            subject="AuthNZ SQLite integrity check failed at startup",
            message=(
                "AuthNZ database preflight detected corruption or unreadable content. "
                "Startup was stopped to prevent unsafe writes."
            ),
            severity="critical",
            metadata={
                "db_path": db_path,
                "quick_check_result": quick_check_result,
                "integrity_check_sample": integrity_sample,
                "error_detail": error_detail,
            },
        )
    except _SQLITE_INTEGRITY_CHECK_NONCRITICAL_EXCEPTIONS as alert_err:
        logger.warning(
            "AuthNZ startup integrity alert dispatch failed: {}",
            alert_err,
        )


async def verify_authnz_sqlite_startup_integrity(
    *,
    database_url: str,
    auth_mode: str,
    dispatch_alerts: bool = True,
    fail_on_error: bool = True,
    timeout_seconds: float = 1.5,
) -> None:
    """Validate AuthNZ SQLite DB integrity during startup.

    - Skips non-SQLite and in-memory backends.
    - Skips when the sqlite file does not exist yet (first-run bootstrap).
    - Uses ``PRAGMA quick_check`` and captures a short ``integrity_check`` sample
      on failure for diagnostics/alert payloads.
    """
    db_path = _resolve_authnz_sqlite_path(
        database_url=database_url,
        auth_mode=auth_mode,
    )
    if db_path is None:
        logger.debug("AuthNZ startup integrity check skipped (non-SQLite or in-memory)")
        return
    if not db_path.exists():
        logger.debug(
            "AuthNZ startup integrity check skipped (database does not exist yet): {}",
            db_path,
        )
        return

    quick_result = "ok"
    integrity_sample = "ok"
    error_detail = ""
    is_healthy = False

    try:
        quick_rows = _run_sqlite_pragma_check(
            db_path=db_path,
            pragma_sql="PRAGMA quick_check;",
            timeout_seconds=timeout_seconds,
        )
        quick_result = quick_rows[0] if quick_rows else "no result"
        is_healthy = quick_result.lower() == "ok"
        if not is_healthy:
            try:
                integrity_rows = _run_sqlite_pragma_check(
                    db_path=db_path,
                    pragma_sql="PRAGMA integrity_check(10);",
                    timeout_seconds=timeout_seconds,
                )
                if integrity_rows:
                    integrity_sample = "; ".join(integrity_rows[:3])
                else:
                    integrity_sample = "no result"
            except _SQLITE_INTEGRITY_CHECK_NONCRITICAL_EXCEPTIONS as detail_err:
                integrity_sample = f"integrity_check failed: {detail_err}"
    except _SQLITE_INTEGRITY_CHECK_NONCRITICAL_EXCEPTIONS as check_err:
        is_healthy = False
        quick_result = f"check failed: {check_err}"
        error_detail = str(check_err)

    if is_healthy:
        logger.info(
            "AuthNZ startup integrity check passed for {}",
            db_path,
        )
        return

    failure_message = (
        "AuthNZ startup integrity check failed for "
        f"{db_path}: quick_check={quick_result}; integrity_check_sample={integrity_sample}"
    )
    logger.critical(failure_message)

    if dispatch_alerts:
        await _dispatch_integrity_alert(
            db_path=str(db_path),
            quick_check_result=quick_result,
            integrity_sample=integrity_sample,
            error_detail=error_detail,
        )

    if fail_on_error:
        raise RuntimeError(failure_message)

    logger.warning(
        "AuthNZ startup integrity check failed but fail-on-error is disabled; continuing startup"
    )

