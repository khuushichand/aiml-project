"""Shared fixtures for ACP tests.

Provides a ``stub_agent_process`` fixture that spawns the stub agent
via the real ``ACPStdioClient``, enabling integration-level tests of the
full STDIO JSON-RPC protocol without needing the Go runner binary.
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPStdioClient


STUB_AGENT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "Helper_Scripts",
    "acp_stub_agent.py",
)


@pytest.fixture
async def stub_stdio_client() -> ACPStdioClient:
    """Spawn the stub agent via ACPStdioClient for integration tests.

    Yields a started client; shuts it down after the test.
    """
    client = ACPStdioClient(
        command=sys.executable,
        args=[os.path.abspath(STUB_AGENT_PATH)],
    )
    await client.start()
    yield client
    await client.close()
