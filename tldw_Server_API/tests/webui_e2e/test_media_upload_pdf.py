import os
from pathlib import Path

import pytest


@pytest.mark.e2e
def test_process_pdfs_upload_and_validate(page, server_url):
    page.goto(f"{server_url}/webui/")
    page.get_by_role("tab", name="Media").click()
    page.get_by_role("tab", name="Processing (No DB)").click()

    # Scroll to the Process PDFs section
    page.get_by_text("POST /api/v1/media/process-pdfs").scroll_into_view_if_needed()

    # Disable analysis to avoid external LLM dependency
    checkbox = page.locator("#processPdfs_perform_analysis")
    if checkbox.is_checked():
        checkbox.uncheck()

    # Use the sample PDF shipped with the repo
    pdf_path = Path(__file__).resolve().parents[2] / "tests" / "Media_Ingestion_Modification" / "test_media" / "sample.pdf"
    assert pdf_path.exists(), f"Sample PDF not found at {pdf_path}"

    page.set_input_files("#processPdfs_files", str(pdf_path))

    # Send the request (scoped to the PDF section)
    page.locator("#processPdfs").get_by_text("Send Request").click()

    # Wait for response to render
    page.wait_for_selector("#processPdfs_response")
    # Wait until the processed JSON is rendered (beyond the progress banner)
    page.wait_for_function(
        "() => { const t = (document.querySelector('#processPdfs_response')?.innerText || ''); return t.includes('processed_count'); }",
        timeout=120000,
    )
    # Expand any collapsed JSON nodes to reveal nested fields
    for _ in range(5):
        collapsed = page.locator("#processPdfs_response .json-toggle.collapsed")
        if collapsed.count() == 0:
            break
        try:
            collapsed.first.click()
        except Exception:
            break
    resp_text = page.locator("#processPdfs_response").inner_text()

    # Require concrete processed structure and specific file reference
    assert "processed_count" in resp_text, "Expected processed_count in response"
    assert "sample.pdf" in resp_text, "Expected sample.pdf to be referenced in response"
