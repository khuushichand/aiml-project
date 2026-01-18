import pytest


@pytest.mark.e2e
def test_onboarding_connects_and_enters_playground(page, server_url, single_user_api_key):
    page.goto("/")
    page.get_by_role("heading", name="Welcome to tldw Assistant").wait_for()

    page.get_by_placeholder("http://127.0.0.1:8000").fill(server_url)
    page.get_by_placeholder("Enter your API key").fill(single_user_api_key)
    page.get_by_role("button", name="Connect").click()

    page.get_by_text("You're connected!").wait_for(timeout=120_000)
    page.get_by_role("button", name="Done").click()

    page.get_by_test_id("connection-status").wait_for()
    page.wait_for_selector("#textarea-message")
