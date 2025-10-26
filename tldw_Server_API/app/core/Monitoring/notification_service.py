from __future__ import annotations

"""
Notification scaffolding for Topic Monitoring.

Goals (Phase 1):
- Provide a minimal, local-first notification hook for high-severity alerts.
- Avoid external dependencies; log to JSONL file and simulate webhook/email via configuration flags.

Configuration (env or config dict under 'monitoring.notifications'):
- MONITORING_NOTIFY_ENABLED: 'true'|'false' (default: false)
- MONITORING_NOTIFY_MIN_SEVERITY: 'info'|'warning'|'critical' (default: 'critical')
- MONITORING_NOTIFY_FILE: path for JSONL sink (default: 'Databases/monitoring_notifications.log')
- MONITORING_NOTIFY_WEBHOOK_URL: URL (future use; not sent in offline mode)
- MONITORING_NOTIFY_EMAIL_TO: comma-separated emails (future use; not sent in Phase 1)

This scaffolding records intent locally so operators can forward to their systems.
"""

import json
import os
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import threading
import smtplib
from email.mime.text import MIMEText

from tldw_Server_API.app.core.DB_Management.TopicMonitoring_DB import TopicAlert
from tldw_Server_API.app.core.config import load_and_log_configs


_SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}


class NotificationService:
    def __init__(self) -> None:
        cfg = load_and_log_configs() or {}
        ncfg = (cfg.get("monitoring") or {}).get("notifications") if isinstance(cfg, dict) else None
        self.enabled = os.getenv("MONITORING_NOTIFY_ENABLED", str((ncfg or {}).get("enabled", False))).strip().lower() in {"1","true","yes","on","y"}
        self.min_severity = str(os.getenv("MONITORING_NOTIFY_MIN_SEVERITY", (ncfg or {}).get("min_severity", "critical"))).strip().lower()
        raw_file = os.getenv("MONITORING_NOTIFY_FILE", (ncfg or {}).get("file", "Databases/monitoring_notifications.log"))
        try:
            fp = Path(str(raw_file))
            if not fp.is_absolute():
                from tldw_Server_API.app.core.Utils.Utils import get_project_root as _gpr
                fp = Path(_gpr()) / fp
            self.file_path = str(fp)
        except Exception:
            # Last resort: anchor relative to package root to avoid CWD effects
            self.file_path = str(Path(__file__).resolve().parents[5] / str(raw_file))
        self.webhook_url = os.getenv("MONITORING_NOTIFY_WEBHOOK_URL", (ncfg or {}).get("webhook_url", ""))
        self.email_to = os.getenv("MONITORING_NOTIFY_EMAIL_TO", (ncfg or {}).get("email_to", ""))
        # SMTP configuration (optional)
        self.smtp_host = os.getenv("MONITORING_NOTIFY_SMTP_HOST", (ncfg or {}).get("smtp_host", ""))
        self.smtp_port = int(os.getenv("MONITORING_NOTIFY_SMTP_PORT", (ncfg or {}).get("smtp_port", "587") or 587))
        self.smtp_starttls = str(os.getenv("MONITORING_NOTIFY_SMTP_STARTTLS", (ncfg or {}).get("smtp_starttls", "true"))).lower() in {"1","true","yes","on","y"}
        self.smtp_user = os.getenv("MONITORING_NOTIFY_SMTP_USER", (ncfg or {}).get("smtp_user", ""))
        self.smtp_password = os.getenv("MONITORING_NOTIFY_SMTP_PASSWORD", (ncfg or {}).get("smtp_password", ""))
        self.email_from = os.getenv("MONITORING_NOTIFY_EMAIL_FROM", (ncfg or {}).get("email_from", self.smtp_user or ""))
        self._lock = threading.RLock()
        try:
            Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def get_settings(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "min_severity": self.min_severity,
            "file": self.file_path,
            "webhook_url": self.webhook_url,
            "email_to": self.email_to,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_starttls": self.smtp_starttls,
            "smtp_user": self.smtp_user,
            "email_from": self.email_from,
        }

    def update_settings(
        self,
        *,
        enabled: Optional[bool] = None,
        min_severity: Optional[str] = None,
        file: Optional[str] = None,
        webhook_url: Optional[str] = None,
        email_to: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_starttls: Optional[bool] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        email_from: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Update runtime settings (non-persistent). Best-effort.
        if enabled is not None:
            self.enabled = bool(enabled)
        if min_severity is not None:
            self.min_severity = str(min_severity).lower()
        if file is not None:
            try:
                Path(file).parent.mkdir(parents=True, exist_ok=True)
                self.file_path = file
            except Exception as e:
                logger.warning(f"Failed to update MONITORING_NOTIFY_FILE: {e}")
        if webhook_url is not None:
            self.webhook_url = webhook_url
        if email_to is not None:
            self.email_to = email_to
        if smtp_host is not None:
            self.smtp_host = smtp_host
        if smtp_port is not None:
            try:
                self.smtp_port = int(smtp_port)
            except Exception:
                pass
        if smtp_starttls is not None:
            self.smtp_starttls = bool(smtp_starttls)
        if smtp_user is not None:
            self.smtp_user = smtp_user
        if smtp_password is not None:
            self.smtp_password = smtp_password
        if email_from is not None:
            self.email_from = email_from
        return self.get_settings()

    def _meets_threshold(self, severity: Optional[str]) -> bool:
        if not self.enabled:
            return False
        sev = (severity or "info").lower()
        try:
            return _SEVERITY_ORDER.get(sev, 0) >= _SEVERITY_ORDER.get(self.min_severity, 2)
        except Exception:
            return False

    def notify(self, alert: TopicAlert) -> None:
        """Record a notification intent for an alert. Phase 1: JSONL file sink only.

        Future: send to webhook/email if configured and networking permitted.
        """
        if not self._meets_threshold(alert.rule_severity):
            return
        payload: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "topic_alert",
            "user_id": alert.user_id,
            "scope_type": alert.scope_type,
            "scope_id": alert.scope_id,
            "source": alert.source,
            "watchlist_id": alert.watchlist_id,
            "rule_category": alert.rule_category,
            "rule_severity": alert.rule_severity,
            "pattern": alert.pattern,
            "snippet": alert.text_snippet,
            "metadata": alert.metadata or {},
            "route_tags": {"scope_type": alert.scope_type, "scope_id": alert.scope_id},
        }
        # Always append to JSONL file (local-first scaffold)
        try:
            with self._lock:
                with open(self.file_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"Notification file sink failed: {e}")
        # Best-effort asynchronous sends (non-blocking)
        try:
            if self.webhook_url:
                threading.Thread(target=self._send_webhook_safe, args=(payload,), daemon=True).start()
        except Exception as e:
            logger.debug(f"Webhook thread start failed: {e}")
        try:
            # Email optional and only if SMTP configured and recipients provided
            if self.email_to and (self.smtp_host and (self.smtp_user or not self.smtp_user)) and self.email_from:
                threading.Thread(target=self._send_email_safe, args=(alert,), daemon=True).start()
        except Exception as e:
            logger.debug(f"Email thread start failed: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=False)
    def _send_webhook(self, payload: Dict[str, Any]) -> None:
        import httpx
        timeout = httpx.Timeout(5.0, connect=3.0)
        with httpx.Client(timeout=timeout) as client:
            headers = {"Content-Type": "application/json"}
            client.post(self.webhook_url, json=payload, headers=headers)

    def _send_webhook_safe(self, payload: Dict[str, Any]) -> None:
        try:
            self._send_webhook(payload)
        except Exception as e:
            logger.info(f"Webhook notify failed: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=False)
    def _send_email(self, alert: TopicAlert) -> None:
        if not (self.smtp_host and self.email_from and self.email_to):
            return
        subject = f"Topic Alert: {alert.rule_category or 'topic'} ({alert.rule_severity or 'info'})"
        body = (
            f"Source: {alert.source}\n"
            f"User: {alert.user_id}\n"
            f"Watchlist: {alert.watchlist_id}\n"
            f"Category: {alert.rule_category}\n"
            f"Severity: {alert.rule_severity}\n"
            f"Pattern: {alert.pattern}\n\n"
            f"Snippet:\n{alert.text_snippet}\n"
        )
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.email_from
        msg["To"] = self.email_to

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
            if self.smtp_starttls:
                try:
                    server.starttls()
                except Exception:
                    pass
            if self.smtp_user:
                server.login(self.smtp_user, self.smtp_password or "")
            server.sendmail(self.email_from, [self.email_to], msg.as_string())

    def _send_email_safe(self, alert: TopicAlert) -> None:
        try:
            self._send_email(alert)
        except Exception as e:
            logger.info(f"Email notify failed: {e}")


_notify_singleton: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    global _notify_singleton
    if _notify_singleton is None:
        _notify_singleton = NotificationService()
    return _notify_singleton
