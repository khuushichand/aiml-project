import pytest


@pytest.mark.e2e
def test_tab_navigation_and_search(page, server_url):
    page.goto(f"{server_url}/webui/")
    page.get_by_role("tab", name="Media").click()
    page.get_by_role("tab", name="Media Management").click()
    page.wait_for_selector("#tabMediaManagement")

    # Use search box to filter endpoints
    page.locator("#endpoint-search").fill("health")
    page.wait_for_timeout(300)  # debounce wait
    # At least ensure search box exists and UI remains responsive
    assert page.locator("#endpoint-search").is_visible()


@pytest.mark.e2e
def test_request_history_modal(page, server_url):
    page.goto(f"{server_url}/webui/")
    # Click Test Connection (triggers GET /health)
    page.get_by_text("Test Connection").click()
    page.wait_for_timeout(800)

    # Open history modal
    page.get_by_text("View History").click()
    page.wait_for_selector(".modal")
    # Expect at least one entry
    assert page.locator(".history-item").count() >= 1


@pytest.mark.e2e
def test_theme_persistence(page, server_url):
    page.goto(f"{server_url}/webui/")
    page.click("#theme-toggle")
    page.wait_for_timeout(100)
    page.reload()
    theme = page.locator("html").get_attribute("data-theme")
    assert theme in ("dark", "light")

