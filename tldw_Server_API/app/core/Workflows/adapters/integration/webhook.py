"""Webhook and notification adapters.

This module includes adapters for webhook and notification operations:
- webhook: Send HTTP webhooks
- notify: Send notifications (Slack/webhook compatible)
"""

from __future__ import annotations

import os
from typing import Any, Dict
from urllib.parse import urlparse

from loguru import logger

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters._common import resolve_context_user_id
from tldw_Server_API.app.core.Workflows.adapters.integration._config import NotifyConfig, WebhookConfig
from tldw_Server_API.app.core.http_client import create_client as _wf_create_client
from tldw_Server_API.app.core.Security.egress import is_url_allowed, is_url_allowed_for_tenant


@registry.register(
    "notify",
    category="integration",
    description="Send notifications",
    parallelizable=True,
    tags=["integration", "notification"],
    config_model=NotifyConfig,
)
async def run_notify_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Send a notification via webhook (Slack/email-compatible JSON).

    Config:
      - url: http(s) webhook URL
      - message: str (templated)
      - subject: str (optional)
      - headers: dict (optional extra headers)

    Output: { dispatched: bool, status_code?, provider?: 'slack'|'webhook' }
    """
    from tldw_Server_API.app.core.Chat.prompt_template_manager import apply_template_to_string as _tmpl

    msg_t = str(config.get("message") or "").strip()
    message = _tmpl(msg_t, context) or msg_t
    subject = str(config.get("subject") or "").strip() or None
    url = str(config.get("url") or "").strip()
    extra_headers = config.get("headers") if isinstance(config.get("headers"), dict) else {}

    if not (url.startswith("http://") or url.startswith("https://")):
        return {"error": "invalid_url"}

    if os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes"):
        return {"dispatched": False, "test_mode": True}

    try:
        tenant_id = str((context.get("tenant_id") or "default")) if isinstance(context, dict) else "default"
        ok = False
        try:
            ok = is_url_allowed_for_tenant(url, tenant_id)
        except Exception:
            ok = is_url_allowed(url)

        if not ok:
            return {"dispatched": False, "error": "blocked_egress"}

        headers = {"content-type": "application/json"}
        try:
            headers.update({k: str(v) for k, v in extra_headers.items()})
        except Exception:
            pass

        body = {"text": message}
        if subject:
            body["subject"] = subject

        timeout = float(os.getenv("WORKFLOWS_NOTIFY_TIMEOUT", "10"))
        with _wf_create_client(timeout=timeout) as client:
            resp = client.post(url, json=body, headers=headers)
            ok = 200 <= resp.status_code < 300

        host = urlparse(url).hostname or ""
        prov = "slack" if "slack" in host else "webhook"
        return {"dispatched": ok, "status_code": resp.status_code, "provider": prov}

    except Exception as e:
        return {"dispatched": False, "error": str(e)}


@registry.register(
    "webhook",
    category="integration",
    description="Send webhooks",
    parallelizable=True,
    tags=["integration", "webhook"],
    config_model=WebhookConfig,
)
async def run_webhook_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Send an HTTP request (with safe egress) or dispatch a local webhook event.

    Config (HTTP mode when 'url' provided):
      - url: str (templated)
      - method: str = POST (GET|POST|PUT|PATCH|DELETE)
      - headers: dict[str,str] (templated values)
      - body: dict|list|str|number|bool|null - request JSON body
      - timeout_seconds: int (default: 10)

    Config (local webhook mode when no 'url' provided):
      - event: str (default 'workflow.event')
      - data: dict (templated minimal)

    Output keys:
      - dispatched: bool
      - status_code: int (HTTP mode)
      - response_json: any (when response is JSON)
      - response_text: str (when response not JSON)
      - error: str (on failure)
    """
    # This adapter is complex with many inline helpers. Import from legacy for full functionality.
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_webhook_adapter as _legacy_webhook
    return await _legacy_webhook(config, context)
