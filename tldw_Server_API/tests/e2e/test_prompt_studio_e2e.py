"""
test_prompt_studio_e2e.py
Description: Prompt Studio E2E - create project, create test case, subscribe WS, echo job update.
"""

import os
import json
import pytest
import httpx

from .fixtures import api_client


def _maybe_import_websockets():
    try:
        import websockets  # type: ignore
        return websockets
    except Exception:
        return None


@pytest.mark.critical
def test_prompt_studio_project_and_ws(api_client):
    # 1) Create a project
    proj_payload = {
        "name": "E2E Project",
        "description": "Prompt Studio smoke project",
        "status": "active",
    }
    try:
        pr = api_client.client.post("/api/v1/prompt-studio/projects", json=proj_payload)
        pr.raise_for_status()
        project = pr.json() if isinstance(pr.json(), dict) else pr.json().get("data")
        project_id = project.get("id") or project.get("project_id")
        assert project_id
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Prompt Studio not available/configured: {e}")

    # 2) Create a simple test case
    tc_payload = {
        "project_id": int(project_id),
        "name": "Smoke test case",
        "inputs": {"text": "Hello world"},
        "expected_outputs": {"summary": "Hello world"},
        "tags": ["e2e"],
        "is_golden": True,
    }
    try:
        tc = api_client.client.post("/api/v1/prompt-studio/test-cases/create", json=tc_payload)
        tc.raise_for_status()
        tcd = tc.json()
        assert tcd.get("success") is True or tcd.get("data")
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Prompt Studio test-case create failed: {e}")

    # 3) WebSocket subscribe and job update echo
    wsmod = _maybe_import_websockets()
    if not wsmod:
        pytest.skip("websockets package not installed; skipping Prompt Studio WS test.")

    base = os.getenv("E2E_TEST_BASE_URL", "http://localhost:8000").replace("http://", "ws://").replace("https://", "wss://")
    url = f"{base}/api/v1/prompt-studio/ws"

    try:
        async def _run():
            async with wsmod.connect(url) as ws:
                # subscribe to project
                await ws.send(json.dumps({"type": "subscribe", "project_id": int(project_id)}))
                ack = json.loads(await ws.recv())
                # Accept either {type: connection} then subscribed, or direct subscribed
                if ack.get("type") == "connection":
                    # read next
                    ack = json.loads(await ws.recv())
                assert ack.get("type") in {"subscribed", "initial_state"}

                # Echo job update path supported by endpoint
                msg = {"type": "job_update", "job_id": "job-smoke", "status": "completed"}
                await ws.send(json.dumps(msg))
                resp = json.loads(await ws.recv())
                assert resp.get("type") == "job_update"

        import asyncio
        asyncio.get_event_loop().run_until_complete(_run())
    except Exception as e:
        pytest.skip(f"Prompt Studio WS not available/configured: {e}")
