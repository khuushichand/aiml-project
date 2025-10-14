"""
Security alert dispatch utilities for the AuthNZ module.

Alerts are recorded to disk and optionally forwarded to webhooks or email
based on configuration supplied via AuthNZ settings.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import smtplib
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class SecurityAlertDispatcher:
    """Dispatch security alerts to configured sinks."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.enabled = getattr(self.settings, "SECURITY_ALERTS_ENABLED", False)
        self.min_severity = getattr(
            self.settings, "SECURITY_ALERT_MIN_SEVERITY", "high"
        ).lower()
        self.file_path = getattr(
            self.settings, "SECURITY_ALERT_FILE_PATH", "Databases/security_alerts.log"
        )
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

        tasks = []
        if self.file_path:
            tasks.append(self._write_file(record))
        if self.webhook_url:
            tasks.append(self._send_webhook(record))
        if self._can_send_email():
            tasks.append(self._send_email(record))

        if not tasks:
            return True

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Security alert sink failed: {result}")
        return True

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
