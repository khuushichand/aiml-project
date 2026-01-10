import pytest


@pytest.mark.e2e
def test_llm_providers_dropdown_populated(page, server_url):
    page.goto(f"{server_url}/webui/")
    page.get_by_role("tab", name="Chat", exact=True).click()
    page.get_by_role("tab", name="Chat Completions").click()

    page.wait_for_selector("#tabChatCompletions")
    page.wait_for_timeout(1200)  # allow config load and populateModelDropdowns

    dropdowns = page.locator(".llm-model-select")
    assert dropdowns.count() >= 1
    html = dropdowns.first.inner_html()
    assert ("option" in html) or ("No models available" in html)
