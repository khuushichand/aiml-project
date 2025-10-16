import os
import pytest


@pytest.mark.e2e
def test_process_documents_upload_and_validate(page, server_url):
    page.goto(f"{server_url}/webui/")
    page.get_by_role("tab", name="Media").click()
    page.get_by_role("tab", name="Processing (No DB)").click()

    # Scroll to the Process Documents section
    page.get_by_text("POST /api/v1/media/process-documents").scroll_into_view_if_needed()

    # Uncheck Perform Analysis to avoid external LLM dependency
    checkbox = page.locator("#processDocuments_perform_analysis")
    if checkbox.is_checked():
        checkbox.uncheck()

    # Attach a small text file
    asset_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', 'assets', 'e2e_sample.txt'
    ))
    page.set_input_files("#processDocuments_files", asset_path)

    # Send the request (scoped to the Process Documents section)
    page.locator("#processDocuments").get_by_text("Send Request").click()

    # Wait for response to render
    page.wait_for_selector("#processDocuments_response")
    # Wait until the actual processed JSON arrives (not just the long-running banner)
    page.wait_for_function(
        "() => { const t = (document.querySelector('#processDocuments_response')?.innerText || ''); return t.includes('processed_count'); }",
        timeout=120000,
    )
    # Read response text and require concrete success structure/content
    # Expand any collapsed JSON nodes (best effort)
    for _ in range(5):
        collapsed = page.locator("#processDocuments_response .json-toggle.collapsed")
        if collapsed.count() == 0:
            break
        try:
            collapsed.first.click()
        except Exception:
            break
    resp_text = page.locator("#processDocuments_response").inner_text()
    assert "processed_count" in resp_text, "Expected processed_count in response"
    # Verify sample file content surfaced in response payload
    assert "Hello world from E2E document processing." in resp_text, "Expected uploaded document content in response"
