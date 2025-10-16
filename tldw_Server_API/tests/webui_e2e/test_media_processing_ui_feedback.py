import pytest


@pytest.mark.e2e
def test_media_processing_long_running_indicator(page, server_url):
    page.goto(f"{server_url}/webui/")
    page.get_by_role("tab", name="Media").click()
    page.get_by_role("tab", name="Processing (No DB)").click()

    # Trigger process-videos without files/urls to exercise UI long-running indicator
    section = page.locator("#processVideos")
    section.get_by_text("POST /api/v1/media/process-videos").scroll_into_view_if_needed()
    section.get_by_text("Send Request").click()

    # Response area should show long-running notice before request completes
    page.wait_for_selector("#processVideos_response")
    response_html = page.locator("#processVideos_response").inner_html()
    assert "Processing in progress" in response_html or "Sending request" in response_html
