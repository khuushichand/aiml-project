import pytest


@pytest.mark.e2e
def test_mcp_status_and_health(page, server_url):
    page.goto(f"{server_url}/webui/")
    page.get_by_role("tab", name="MCP").click()
    page.get_by_role("tab", name="/api/v1/mcp/status").click()

    page.get_by_text("Check Status").click()
    page.wait_for_selector("#mcpStatus_response")
    status_text = page.locator("#mcpStatus_response").inner_text()
    assert status_text != ""

    # Health endpoint
    page.get_by_role("tab", name="/api/v1/mcp/health").click()
    page.get_by_text("Check Health").click()
    page.wait_for_selector("#mcpHealth_response")
    health_text = page.locator("#mcpHealth_response").inner_text()
    assert health_text != ""

