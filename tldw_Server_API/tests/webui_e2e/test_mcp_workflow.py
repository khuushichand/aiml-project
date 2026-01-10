import pytest


@pytest.mark.e2e
def test_mcp_status_and_health(page, server_url):
    page.goto(f"{server_url}/webui/")
    page.get_by_role("tab", name="MCP").click()
    page.get_by_role("tab", name="Status").click()

    page.get_by_text("Check Status").click()
    page.wait_for_selector("#mcpStatus_response")
    try:
        page.wait_for_function("() => (document.querySelector('#mcpStatus_response')?.innerText || '').length > 0", timeout=30000)
    except Exception:
        pass
    status_text = page.locator("#mcpStatus_response").inner_text()
    assert status_text.strip() != ""

    # Health endpoint (scoped to MCP sub-tabs to avoid ambiguity)
    page.locator("#mcp-subtabs").get_by_role("tab", name="Health").click()
    page.locator("#tabMCPHealth").get_by_role("button", name="Check Health").click()
    page.wait_for_selector("#mcpHealth_response")
    try:
        page.wait_for_function("() => (document.querySelector('#mcpHealth_response')?.innerText || '').length > 0", timeout=30000)
    except Exception:
        pass
    health_text = page.locator("#mcpHealth_response").inner_text()
    assert health_text.strip() != ""
