"""
Security alert dispatch utilities for the AuthNZ module.

Alerts are recorded to disk and optionally forwarded to webhooks or email
based on configuration supplied via AuthNZ settings.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
import smtplib
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings
from tldw_Server_API.app.core.AuthNZ.monitoring import update_security_alert_metrics

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class SecurityAlertDispatcher:
    """Dispatch security alerts to configured sinks."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.enabled = getattr(self.settings, "SECURITY_ALERTS_ENABLED", False)
        self.min_severity = getattr(
            self.settings, "SECURITY_ALERT_MIN_SEVERITY", "high"
        ).lower()
        raw_fp = getattr(self.settings, "SECURITY_ALERT_FILE_PATH", "Databases/security_alerts.log")
        try:
            fp = Path(str(raw_fp))
            if not fp.is_absolute():
                from tldw_Server_API.app.core.Utils.Utils import get_project_root as _gpr
                fp = Path(_gpr()) / fp
        except Exception:
            # Anchor relative to package root if project resolution fails
            fp = Path(__file__).resolve().parents[5] / str(raw_fp)
        self.file_path = str(fp)
        self.webhook_url = getattr(self.settings, "SECURITY_ALERT_WEBHOOK_URL", None)
        raw_headers = getattr(
            self.settings, "SECURITY_ALERT_WEBHOOK_HEADERS", None
        ) or ""
        self.webhook_headers: Dict[str, str] = self._parse_headers(raw_headers)
        recipients = getattr(self.settings, "SECURITY_ALERT_EMAIL_TO", "") or ""
        self.email_recipients = [
            email.strip() for email in recipients.split(",") if email.strip()
        ]
        self.email_from = getattr(self.settings, "SECURITY_ALERT_EMAIL_FROM", None)
        self.email_subject_prefix = getattr(
            self.settings, "SECURITY_ALERT_EMAIL_SUBJECT_PREFIX", "[AuthNZ]"
        ).strip()
        self.smtp_host = getattr(self.settings, "SECURITY_ALERT_SMTP_HOST", None)
        self.smtp_port = getattr(self.settings, "SECURITY_ALERT_SMTP_PORT", 587)
        self.smtp_starttls = getattr(
            self.settings, "SECURITY_ALERT_SMTP_STARTTLS", True
        )
        self.smtp_user = getattr(self.settings, "SECURITY_ALERT_SMTP_USERNAME", None)
        self.smtp_password = getattr(
            self.settings, "SECURITY_ALERT_SMTP_PASSWORD", None
        )
        self.smtp_timeout = getattr(
            self.settings, "SECURITY_ALERT_SMTP_TIMEOUT", 10
        )
        self._file_lock = asyncio.Lock()
        self._last_dispatch_time: Optional[datetime] = None
        self._last_dispatch_success: Optional[bool] = None
        self._last_dispatch_error: Optional[str] = None
        self._last_sink_status: Dict[str, Optional[bool]] = {
            "file": None,
            "webhook": None,
            "email": None,
        }
        self._last_sink_errors: Dict[str, Optional[str]] = {
            "file": None,
            "webhook": None,
            "email": None,
        }
        self._dispatch_count = 0
        self._last_validation_time: Optional[datetime] = None
        self._last_validation_errors: Optional[list[str]] = None
        try:
            self.file_min_severity = self._normalize_threshold(
                getattr(self.settings, "SECURITY_ALERT_FILE_MIN_SEVERITY", None)
            )
            self.webhook_min_severity = self._normalize_threshold(
                getattr(self.settings, "SECURITY_ALERT_WEBHOOK_MIN_SEVERITY", None)
            )
            self.email_min_severity = self._normalize_threshold(
                getattr(self.settings, "SECURITY_ALERT_EMAIL_MIN_SEVERITY", None)
            )
        except ValueError as threshold_error:
            raise ValueError(f"Security alert severity configuration error: {threshold_error}") from threshold_error
        self.backoff_seconds = max(0, int(getattr(self.settings, "SECURITY_ALERT_BACKOFF_SECONDS", 30)))
        self._sink_backoff: Dict[str, datetime] = {}

        if self.file_path:
            try:
                Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                logger.debug(f"Security alert log path setup failed: {exc}")

    @staticmethod
    def _parse_headers(raw_headers: str) -> Dict[str, str]:
        if not raw_headers:
            return {}
        try:
            parsed = json.loads(raw_headers)
            if not isinstance(parsed, dict):
                raise ValueError("Headers must be a JSON object")
            return {str(k): str(v) for k, v in parsed.items()}
        except Exception as exc:
            logger.warning(f"Invalid SECURITY_ALERT_WEBHOOK_HEADERS value: {exc}")
            return {}

    def _meets_threshold(self, severity: str) -> bool:
        if not self.enabled:
            return False
        sev_value = _SEVERITY_ORDER.get(severity, _SEVERITY_ORDER["low"])
        threshold_value = _SEVERITY_ORDER.get(
            self.min_severity, _SEVERITY_ORDER["high"]
        )
        return sev_value >= threshold_value

    def _normalize_threshold(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        normalized = value.strip().lower()
        if normalized not in _SEVERITY_ORDER:
            raise ValueError(f"Invalid severity threshold '{value}'")
        return normalized

    def _severity_passes(self, severity: str, threshold: Optional[str]) -> bool:
        if not threshold:
            return True
        return _SEVERITY_ORDER.get(severity, 0) >= _SEVERITY_ORDER[threshold]

    def _sink_in_backoff(self, sink: str, now: datetime) -> bool:
        expiry = self._sink_backoff.get(sink)
        return bool(expiry and expiry > now)

    def _set_backoff(self, sink: str, now: datetime) -> None:
        if self.backoff_seconds > 0:
            self._sink_backoff[sink] = now + timedelta(seconds=self.backoff_seconds)

    def _clear_backoff(self, sink: str) -> None:
        if sink in self._sink_backoff:
            del self._sink_backoff[sink]

    def validate_configuration(self) -> None:
        """
        Validate alert configuration during startup.
        Raises ValueError if security alerting is enabled but misconfigured.
        """
        self._last_validation_time = datetime.now(timezone.utc)
        issues: list[str] = []

        if not self.enabled:
            self._last_validation_errors = None
            update_security_alert_metrics(self._last_sink_status, None)
            return

        sink_configured = False

        if self.file_path:
            sink_configured = True
            try:
                path = Path(self.file_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8"):
                    pass
            except Exception as exc:
                issues.append(f"File sink not writable: {exc}")

        if self.webhook_url:
            sink_configured = True
            parsed = urlparse(self.webhook_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                issues.append("Webhook URL must be a valid http/https endpoint")

        if self._can_send_email():
            sink_configured = True
        else:
            email_fields = [
                bool(self.email_recipients),
                bool(self.email_from),
                bool(self.smtp_host),
                bool(self.smtp_user),
                bool(self.smtp_password),
            ]
            if any(email_fields):
                issues.append(
                    "Email alerting requires recipients, from address, SMTP host, "
                    "and credentials when authentication is needed"
                )

        if not sink_configured:
            issues.append("Security alerts enabled but no delivery sink configured")

        self._last_validation_errors = issues or None
        if issues:
            update_security_alert_metrics(self._last_sink_status, False)
            raise ValueError("; ".join(issues))

        update_security_alert_metrics(self._last_sink_status, None)

    async def dispatch(
        self,
        subject: str,
        message: str,
        *,
        severity: str = "high",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Dispatch a security alert."""
        severity = (severity or "high").lower()
        metadata = metadata or {}

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "subject": subject,
            "message": message,
            "severity": severity,
            "metadata": metadata,
        }

        log_method = {
            "low": logger.info,
            "medium": logger.warning,
            "high": logger.error,
            "critical": logger.critical,
        }.get(severity, logger.warning)
        log_method(f"🚨 SECURITY ALERT [{severity.upper()}]: {subject} - {message}")

        if not self._meets_threshold(severity):
            return False

        current_time = datetime.now(timezone.utc)

        sink_status: Dict[str, Optional[bool]] = {
            "file": None,
            "webhook": None,
            "email": None,
        }
        sink_errors: Dict[str, Optional[str]] = {
            "file": None,
            "webhook": None,
            "email": None,
        }
        errors: list[tuple[str, Exception]] = []

        if self.file_path:
            if self._sink_in_backoff("file", current_time):
                sink_status["file"] = False
                sink_errors["file"] = "backoff"
            elif self._severity_passes(severity, self.file_min_severity):
                try:
                    await self._write_file(record)
                    sink_status["file"] = True
                    self._clear_backoff("file")
                except Exception as exc:
                    sink_status["file"] = False
                    sink_errors["file"] = str(exc)
                    errors.append(("file", exc))
                    self._set_backoff("file", current_time)
            else:
                sink_status["file"] = None

        if self.webhook_url:
            if self._sink_in_backoff("webhook", current_time):
                sink_status["webhook"] = False
                sink_errors["webhook"] = "backoff"
            elif self._severity_passes(severity, self.webhook_min_severity):
                try:
                    await self._send_webhook(record)
                    sink_status["webhook"] = True
                    self._clear_backoff("webhook")
                except Exception as exc:
                    sink_status["webhook"] = False
                    sink_errors["webhook"] = str(exc)
                    errors.append(("webhook", exc))
                    self._set_backoff("webhook", current_time)
            else:
                sink_status["webhook"] = None

        if self._can_send_email():
            if self._sink_in_backoff("email", current_time):
                sink_status["email"] = False
                sink_errors["email"] = "backoff"
            elif self._severity_passes(severity, self.email_min_severity):
                try:
                    await self._send_email(record)
                    sink_status["email"] = True
                    self._clear_backoff("email")
                except Exception as exc:
                    sink_status["email"] = False
                    sink_errors["email"] = str(exc)
                    errors.append(("email", exc))
                    self._set_backoff("email", current_time)
            else:
                sink_status["email"] = None

        self._last_dispatch_time = datetime.now(timezone.utc)
        self._dispatch_count += 1
        self._last_sink_status = sink_status
        self._last_sink_errors = sink_errors

        has_failure = bool(errors) or any(
            status is False for status in sink_status.values() if status is not None
        )
        success = not has_failure
        self._last_dispatch_success = success
        if errors:
            self._last_dispatch_error = str(errors[0][1])
        elif not success:
            self._last_dispatch_error = "backoff"
        else:
            self._last_dispatch_error = None

        update_security_alert_metrics(sink_status, success)

        for sink_name, exc in errors:
            logger.warning(f"Security alert sink '{sink_name}' failed: {exc}")
        for sink_name, err in sink_errors.items():
            if err == "backoff":
                logger.warning(
                    f"Security alert sink '{sink_name}' in backoff window; delivery skipped"
                )

        return success

    def _can_send_email(self) -> bool:
        return (
            bool(self.email_recipients)
            and bool(self.email_from)
            and bool(self.smtp_host)
        )

    async def _write_file(self, record: Dict[str, Any]) -> None:
        async with self._file_lock:
            await asyncio.to_thread(self._write_file_sync, record)

    def _write_file_sync(self, record: Dict[str, Any]) -> None:
        if not self.file_path:
            return
        try:
            with open(self.file_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            raise RuntimeError(f"File sink failed: {exc}") from exc

    async def _send_webhook(self, record: Dict[str, Any]) -> None:
        timeout = httpx.Timeout(5.0, connect=3.0)
        headers = {"Content-Type": "application/json", **self.webhook_headers}
        async with httpx.AsyncClient(timeout=timeout) as client:
            await client.post(self.webhook_url, json=record, headers=headers)

    async def _send_email(self, record: Dict[str, Any]) -> None:
        await asyncio.to_thread(self._send_email_sync, record)

    def _send_email_sync(self, record: Dict[str, Any]) -> None:
        if not self._can_send_email():
            return

        message = EmailMessage()
        subject = f"{self.email_subject_prefix} {record['subject']} ({record['severity'].upper()})"
        message["Subject"] = subject.strip()
        message["From"] = self.email_from
        message["To"] = ", ".join(self.email_recipients)

        body_lines = [
            f"Message: {record['message']}",
            f"Severity: {record['severity']}",
            f"Timestamp: {record['timestamp']}",
        ]
        if record["metadata"]:
            try:
                metadata_json = json.dumps(record["metadata"], indent=2, default=str)
            except TypeError:
                metadata_json = str(record["metadata"])
            body_lines.append("Metadata:")
            body_lines.append(metadata_json)

        message.set_content("\n".join(body_lines))

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.smtp_timeout) as smtp:
            smtp.ehlo()
            if self.smtp_starttls:
                try:
                    smtp.starttls()
                except smtplib.SMTPException as exc:
                    raise RuntimeError(f"SMTP STARTTLS failed: {exc}") from exc
                smtp.ehlo()
            if self.smtp_user:
                smtp.login(self.smtp_user, self.smtp_password or "")
            smtp.send_message(message)

    def get_status(self) -> Dict[str, Any]:
        """Return current dispatcher configuration and dispatch metadata."""
        return {
            "enabled": self.enabled,
            "min_severity": self.min_severity,
            "file_sink_configured": bool(self.file_path),
            "webhook_configured": bool(self.webhook_url),
            "email_configured": self._can_send_email(),
            "last_dispatch_time": self._last_dispatch_time,
            "last_dispatch_success": self._last_dispatch_success,
            "last_dispatch_error": self._last_dispatch_error,
            "dispatch_count": self._dispatch_count,
            "last_sink_status": self._last_sink_status,
            "last_sink_errors": self._last_sink_errors,
            "sink_thresholds": {
                "file": self.file_min_severity,
                "webhook": self.webhook_min_severity,
                "email": self.email_min_severity,
            },
            "sink_backoff_until": self._sink_backoff,
            "last_validation_time": self._last_validation_time,
            "last_validation_errors": self._last_validation_errors,
        }


_dispatcher: Optional[SecurityAlertDispatcher] = None


def get_security_alert_dispatcher() -> SecurityAlertDispatcher:
    """Return the singleton security alert dispatcher."""
    global _dispatcher
    if not _dispatcher:
        _dispatcher = SecurityAlertDispatcher()
    return _dispatcher


async def reset_security_alert_dispatcher() -> None:
    """Reset the security alert dispatcher singleton (primarily for tests)."""
    global _dispatcher
    _dispatcher = None
