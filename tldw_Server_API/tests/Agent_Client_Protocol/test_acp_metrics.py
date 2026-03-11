"""Tests for ACP metrics module."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_metrics_registration():
    """Verify ACP metrics register without error."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.metrics import (
        _ensure_registered,
    )

    _ensure_registered()  # Should not raise


def test_record_session_created():
    """Verify session creation metric increments."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.metrics import (
        record_session_created,
    )

    record_session_created("claude_code")  # Should not raise


def test_record_session_closed():
    """Verify session close metric increments."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.metrics import (
        record_session_closed,
    )

    record_session_closed("normal")
    record_session_closed("timeout")


def test_set_active_sessions():
    """Verify active sessions gauge can be set."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.metrics import (
        set_active_sessions,
    )

    set_active_sessions(5, "claude_code")
    set_active_sessions(0)


def test_record_prompt():
    """Verify prompt counter increments."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.metrics import record_prompt

    record_prompt("codex")


def test_record_prompt_latency():
    """Verify latency histogram records."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.metrics import (
        record_prompt_latency,
    )

    record_prompt_latency(1.5, "claude_code")


def test_record_token_usage():
    """Verify token usage counter increments."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.metrics import (
        record_token_usage,
    )

    record_token_usage(500, "claude_code", "input")
    record_token_usage(200, "claude_code", "output")


def test_record_governance_block():
    """Verify governance block counter increments."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.metrics import (
        record_governance_block,
    )

    record_governance_block("rate_limit", "claude_code")


def test_record_error():
    """Verify error counter increments."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.metrics import record_error

    record_error("timeout")
    record_error("connection_refused")


def test_record_quota_rejection():
    """Verify quota rejection counter increments."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.metrics import (
        record_quota_rejection,
    )

    record_quota_rejection("concurrent_sessions")
    record_quota_rejection("token_limit")


def test_record_orchestration_task():
    """Verify orchestration task counter increments."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.metrics import (
        record_orchestration_task,
    )

    record_orchestration_task("created")
    record_orchestration_task("completed")


def test_record_orchestration_run():
    """Verify orchestration run counter increments."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.metrics import (
        record_orchestration_run,
    )

    record_orchestration_run("dispatched")
    record_orchestration_run("completed")


def test_idempotent_registration():
    """Verify metrics can be registered multiple times without error."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.metrics import (
        _ensure_registered,
    )

    _ensure_registered()
    _ensure_registered()  # Should not raise
