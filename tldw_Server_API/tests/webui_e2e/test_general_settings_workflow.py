import pytest


@pytest.mark.e2e
def test_general_settings_offline_online_toggle(page, server_url):
    page.goto(f"{server_url}/webui/")

    # Confirm initial Connected
    page.wait_for_selector(".api-status-text")
    page.wait_for_timeout(1000)
    assert "Connected" in page.locator(".api-status-text").inner_text()

    # Change base URL to an invalid one
    page.fill("#baseUrl", "http://127.0.0.1:1")
    # Trigger blur/change event
    page.keyboard.press("Tab")
    page.get_by_text("Test Connection").click()
    page.wait_for_timeout(1000)
    # Expect an offline/unreachable indicator
    offline_text = page.locator(".api-status-text").inner_text()
    assert ("API Offline" in offline_text) or ("API Unreachable" in offline_text) or ("Error" in offline_text)

    # Restore valid URL and re-test
    page.fill("#baseUrl", server_url)
    page.keyboard.press("Tab")
    page.get_by_text("Test Connection").click()
    page.wait_for_timeout(1000)
    assert "Connected" in page.locator(".api-status-text").inner_text()
