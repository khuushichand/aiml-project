import os
from uuid import uuid4

import pytest


def _api_key() -> str:
    return os.environ.get("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")


def _auth_headers() -> dict:
    return {"X-API-KEY": _api_key()}


def _require_ok(resp, label: str) -> None:
    if not resp.ok:
        raise AssertionError(f"{label} failed: status={resp.status} body={resp.text()}")


@pytest.mark.e2e
def test_mcp_tools_lifecycle_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]
    title = f"E2E MCP Note {suffix}"
    content = f"mcp-tool-search-{suffix}"

    create_resp = page.request.post(
        "/api/v1/notes/",
        headers=headers,
        json={"title": title, "content": content, "keywords": ["mcp", suffix]},
    )
    _require_ok(create_resp, "create note")
    note_payload = create_resp.json()
    note_id = note_payload["id"]
    version = note_payload["version"]

    search_resp = page.request.get(
        "/api/v1/notes/search",
        headers=headers,
        params={"query": content},
    )
    _require_ok(search_resp, "notes search")

    tools_resp = page.request.get("/api/v1/mcp/tools", headers=headers)
    _require_ok(tools_resp, "list MCP tools")
    tools_payload = tools_resp.json()
    tools = tools_payload.get("tools", [])
    assert tools, "Expected MCP tools list"

    knowledge_tool = next((tool for tool in tools if tool.get("name") == "knowledge.search"), None)
    assert knowledge_tool, "knowledge.search tool not registered"
    assert knowledge_tool.get("canExecute") is True

    exec_resp = page.request.post(
        "/api/v1/mcp/tools/execute",
        headers=headers,
        json={
            "tool_name": "knowledge.search",
            "arguments": {
                "query": content,
                "sources": ["notes"],
                "limit": 5,
            },
        },
    )
    _require_ok(exec_resp, "execute MCP tool")
    exec_payload = exec_resp.json()
    result_payload = exec_payload.get("result")
    if isinstance(result_payload, dict):
        results = result_payload.get("results", [])
        assert isinstance(results, list)
        if results:
            assert any(item.get("source") == "notes" for item in results)

    metrics_resp = page.request.get("/api/v1/mcp/metrics/prometheus", headers=headers)
    _require_ok(metrics_resp, "fetch MCP metrics")
    metrics_text = metrics_resp.text()
    assert "mcp_module_operations_total" in metrics_text
    assert "tools_call" in metrics_text

    delete_resp = page.request.delete(
        f"/api/v1/notes/{note_id}",
        headers={**headers, "expected-version": str(version)},
    )
    assert delete_resp.status == 204
