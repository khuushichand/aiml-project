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

    # Wait for response; allow generous timeout
    page.wait_for_selector("#addMedia_response", timeout=30000)
    resp_text = page.locator("#addMedia_response").inner_text()
    assert resp_text != ""
    # Should contain results and DB hints
    assert "results" in resp_text

    # Now verify via Media Management → List All Media
    page.get_by_role("tab", name="Media").click()
    page.get_by_role("tab", name="Media Management").click()

    # Trigger list call
    page.locator("#listAllMedia").get_by_text("Send Request").click()
    page.wait_for_selector("#listAllMedia_response")
    list_text = page.locator("#listAllMedia_response").inner_text()
    assert title in list_text or "e2e_sample.txt" in list_text

    # Also verify via Search endpoint using the title as query
    page.locator("#searchMediaItems").scroll_into_view_if_needed()
    # Overwrite payload with a focused title search
    search_payload = {
        "query": title,
        "fields": ["title", "content"],
        "sort_by": "relevance"
    }
    # Fill textarea with JSON
    page.fill("#searchMediaItems_payload", __import__("json").dumps(search_payload, indent=2))
    # Trigger search in the scoped section
    page.locator("#searchMediaItems").get_by_text("Send Request").click()
    page.wait_for_selector("#searchMediaItems_response")
    search_text = page.locator("#searchMediaItems_response").inner_text()
    assert title in search_text or "e2e_sample.txt" in search_text
