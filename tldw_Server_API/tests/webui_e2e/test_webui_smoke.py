import pytest


@pytest.mark.e2e
def test_webui_loads_and_shows_connected(page, server_url):
    page.goto(f"{server_url}/webui/")
    page.get_by_text("TLDW API Testing Interface").wait_for()

    # Global settings visible
    page.wait_for_selector("#baseUrl")
    page.wait_for_selector("#apiKeyInput")

    # Status becomes connected
    page.wait_for_selector(".api-status-text")
    page.wait_for_timeout(1000)
    status_text = page.locator(".api-status-text").inner_text()
    assert "Connected" in status_text

    # Auto-config indicator present in label
    label_html = page.locator("label[for='apiKeyInput']").inner_html()
    assert "Auto-configured" in label_html
