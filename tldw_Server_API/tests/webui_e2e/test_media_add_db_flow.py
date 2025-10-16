import os
import time
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_media_add_db_and_list(page, server_url):
    page.goto(f"{server_url}/webui/")
    # Go to Media → Ingestion (DB)
    page.get_by_role("tab", name="Media").click()
    page.get_by_role("tab", name="Ingestion (DB)").click()

    # Prepare unique-ish title
    title = "E2E DB Media"

    # Choose media type 'Document'
    page.select_option("#addMedia_media_type", label="Document (includes .txt, .md, .html, .xml, .docx, .rtf)")

    # Disable analysis for speed/determinism
    checkbox = page.locator("#addMedia_perform_analysis")
    if checkbox.is_checked():
        checkbox.uncheck()

    # Set title and keywords
    page.fill("#addMedia_title", title)
    page.fill("#addMedia_keywords", "e2e-db-test")

    # Attach small text file as content
    asset_path = Path(__file__).resolve().parents[1] / "assets" / "e2e_sample.txt"
    assert asset_path.exists(), f"Asset not found: {asset_path}"
    page.set_input_files("#addMedia_files", str(asset_path))

    # Send request scoped to Add Media section
    page.locator("#addMedia").get_by_text("Send Request").click()

    # Wait for response content to render
    page.wait_for_selector("#addMedia_response", timeout=30000)
    try:
        page.wait_for_function("() => (document.querySelector('#addMedia_response')?.innerText || '').length > 0", timeout=30000)
    except Exception:
        pass
    resp_text = page.locator("#addMedia_response").inner_text()
    assert resp_text.strip() != ""
    # Should contain results and DB hints
    assert "results" in resp_text
    # Verify newly added item appears in list and search (strict checks)
    # Navigate to Media Management for list/search endpoints
    page.get_by_role("tab", name="Media Management").click()

    # List All Media (GET /api/v1/media/)
    page.get_by_text("GET /api/v1/media/ - List All Media Items").scroll_into_view_if_needed()
    # Increase page size to ensure the newly added item appears
    page.fill("#listAllMedia_results_per_page", "100")
    page.locator("#listAllMedia").get_by_text("Send Request").click()
    page.wait_for_selector("#listAllMedia_response", timeout=30000)
    try:
        page.wait_for_function("() => (document.querySelector('#listAllMedia_response')?.innerText || '').length > 0", timeout=30000)
    except Exception:
        pass
    # Expand JSON nodes to reveal nested item fields
    for _ in range(5):
        collapsed = page.locator("#listAllMedia_response .json-toggle.collapsed")
        if collapsed.count() == 0:
            break
        try:
            collapsed.first.click()
        except Exception:
            break
    list_text = page.locator("#listAllMedia_response").inner_text()
    assert "items" in list_text, "Expected items array in list response"
    assert title in list_text, "Newly added title not found in list response"

    # Search Media Items (POST /api/v1/media/search) using our title
    page.get_by_text("POST /api/v1/media/search - Search Media Items").scroll_into_view_if_needed()
    # Replace payload with our query to reduce noise
    page.fill("#searchMediaItems_payload", '{\n  "query": "' + title + '",\n  "fields": ["title"]\n}')
    page.locator("#searchMediaItems").get_by_text("Send Request").click()
    page.wait_for_selector("#searchMediaItems_response", timeout=30000)
    try:
        page.wait_for_function("() => (document.querySelector('#searchMediaItems_response')?.innerText || '').length > 0", timeout=30000)
    except Exception:
        pass
    # Expand nested JSON nodes before asserting
    for _ in range(5):
        collapsed = page.locator("#searchMediaItems_response .json-toggle.collapsed")
        if collapsed.count() == 0:
            break
        try:
            collapsed.first.click()
        except Exception:
            break
    search_text = page.locator("#searchMediaItems_response").inner_text()
    assert "items" in search_text, "Expected items array in search response"
    assert title in search_text, "Newly added title not found in search response"
