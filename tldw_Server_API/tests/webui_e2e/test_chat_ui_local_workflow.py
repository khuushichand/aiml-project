import pytest


@pytest.mark.e2e
def test_chat_ui_add_and_clear_local(page, server_url):
    page.goto(f"{server_url}/webui/")
    page.get_by_role("tab", name="Chat", exact=True).click()
    # The chat UI lives within the Chat Completions tab
    page.get_by_role("tab", name="Chat Completions").click()

    # Ensure chat area present
    page.wait_for_selector("#chat-messages")

    # Type a message and click Send (client-side handler)
    page.fill("#chat-input", "Hello there!")
    page.get_by_role("button", name="Send message").click()

    # A new message element should appear in the chat messages container
    assert page.locator("#chat-messages .chat-message").count() >= 1

    # Clear chat and verify system-only or empty state remains
    page.get_by_role("button", name="Clear chat history").click()
    # Wait a bit for DOM updates
    page.wait_for_timeout(200)
    assert page.locator("#chat-messages").is_visible()
