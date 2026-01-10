import pytest


@pytest.mark.e2e
def test_health_dashboard_and_checks(page, server_url):
    page.goto(f"{server_url}/webui/")
    # Open Health tab and Health Dashboard subtab
    page.get_by_role("tab", name="Health").click()
    # Updated sub-tab label is simply 'Dashboard'
    page.get_by_role("tab", name="Dashboard").click()

    # Click 'Check All Services' and wait for cards
    page.get_by_text("Check All Services").click()
    page.wait_for_selector("#health-status-grid .health-card")
    # Expect at least 1 card present (main API)
    assert page.locator("#health-status-grid .health-card").count() >= 1

    # Switch to Individual Health Checks and run Main API health
    page.get_by_role("tab", name="Individual Checks").click()
    page.get_by_text("Check Main API").click()
    # Response <pre> should populate with JSON or error string
    page.wait_for_selector("#health_main_response")
    text = page.locator("#health_main_response").inner_text()
    # Allow non-empty content and avoid explicit 'Error' string
    assert text.strip() != "" and "Error" not in text
