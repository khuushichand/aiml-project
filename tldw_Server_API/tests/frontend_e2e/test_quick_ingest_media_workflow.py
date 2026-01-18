import re

import pytest


@pytest.mark.e2e
def test_quick_ingest_document_and_verify_media(configured_page, sample_text_path):
    page = configured_page
    page.set_default_timeout(120_000)

    page.goto("/")
    page.get_by_test_id("connection-status").wait_for()

    page.get_by_test_id("open-quick-ingest").click()
    page.get_by_text("Quick Ingest").wait_for()

    page.get_by_role("tab", name="Options").click()
    analysis_toggle = page.get_by_role("switch", name=re.compile("analysis", re.I))
    if analysis_toggle.get_attribute("aria-checked") == "true":
        analysis_toggle.click()

    chunking_toggle = page.get_by_role("switch", name=re.compile("chunking", re.I))
    if chunking_toggle.get_attribute("aria-checked") == "true":
        chunking_toggle.click()

    page.get_by_role("tab", name="Queue").click()
    page.get_by_test_id("qi-file-input").set_input_files(sample_text_path)

    run_button = page.get_by_test_id("quick-ingest-run")
    page.wait_for_function("el => !el.disabled", run_button)
    run_button.click()

    page.get_by_role("tab", name="Results").click()
    page.get_by_test_id("quick-ingest-open-media-primary").wait_for(timeout=120_000)
    page.get_by_test_id("quick-ingest-open-media-primary").click()

    page.wait_for_url("**/media**")
    search = page.get_by_placeholder("Search media (title/content)")
    search.fill("Hello world from E2E document processing.")
    page.wait_for_timeout(500)

    result_button = page.get_by_role(
        "button", name=re.compile(r"Select .*e2e_sample\\.txt")
    )
    result_button.wait_for()
    result_button.click()
    page.get_by_text("Hello world from E2E document processing.").wait_for()

    page.get_by_role("button", name="Delete item").click()
    delete_dialog = page.get_by_role("dialog")
    delete_dialog.get_by_role("button", name="Delete").wait_for()
    delete_dialog.get_by_role("button", name="Delete").click()
