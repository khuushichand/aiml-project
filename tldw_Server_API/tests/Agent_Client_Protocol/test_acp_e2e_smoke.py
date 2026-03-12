"""End-to-end smoke test for ACP with stub agent.

Exercises the full lifecycle: spawn runner → initialize → create session →
send prompt → receive response → close session.

Requires the stub agent script at Helper_Scripts/acp_stub_agent.py.
Skips if stub agent is missing.
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

STUB_AGENT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "Helper_Scripts",
    "acp_stub_agent.py",
)


@pytest.fixture
def stub_agent_available():
    if not os.path.isfile(STUB_AGENT_PATH):
        pytest.skip("Stub agent script not found")


async def test_full_lifecycle_smoke(stub_agent_available):
    """Full ACP lifecycle with stub agent."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import (
        ACPStdioClient,
    )

    client = ACPStdioClient(
        command=sys.executable,
        args=[os.path.abspath(STUB_AGENT_PATH)],
    )

    try:
        # 1. Start
        await client.start()
        assert client.is_running

        # 2. Initialize
        init_result = await client.call("initialize", {})
        assert init_result.result is not None
        agent_info = init_result.result.get("agentInfo", {})
        assert agent_info.get("name") == "tldw-acp-stub"

        # 3. Create session
        new_result = await client.call("session/new", {})
        session_id = new_result.result["sessionId"]
        assert session_id

        # 4. Send prompt
        prompt_result = await client.call(
            "session/prompt",
            {"sessionId": session_id, "prompt": "What is 2+2?"},
        )
        assert prompt_result.result["stopReason"] == "end"

        # 5. Cancel (should succeed)
        cancel_result = await client.call("session/cancel", {})
        assert cancel_result.result is None

    finally:
        await client.close()

    assert not client.is_running


async def test_protocol_version_check(stub_agent_available):
    """Verify initialize returns expected protocol version."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import (
        ACPStdioClient,
    )

    client = ACPStdioClient(
        command=sys.executable,
        args=[os.path.abspath(STUB_AGENT_PATH)],
    )

    try:
        await client.start()
        result = await client.call("initialize", {})
        assert result.result["protocolVersion"] == 1
        assert "agentCapabilities" in result.result
        caps = result.result["agentCapabilities"]
        assert caps["loadSession"] is False
        assert "promptCapabilities" in caps
    finally:
        await client.close()


async def test_multiple_prompts_same_session(stub_agent_available):
    """Verify multiple prompts can be sent to the same session."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import (
        ACPStdioClient,
    )

    client = ACPStdioClient(
        command=sys.executable,
        args=[os.path.abspath(STUB_AGENT_PATH)],
    )

    try:
        await client.start()
        await client.call("initialize", {})
        new_result = await client.call("session/new", {})
        session_id = new_result.result["sessionId"]

        for i in range(3):
            result = await client.call(
                "session/prompt",
                {"sessionId": session_id, "prompt": f"Prompt {i}"},
            )
            assert result.result["stopReason"] == "end"

    finally:
        await client.close()
