import re
import uuid

import pytest


@pytest.mark.e2e
def test_notes_create_search_update_delete(configured_page):
    page = configured_page
    page.goto("/notes")

    page.get_by_placeholder("Search notes...").wait_for()

    note_suffix = uuid.uuid4().hex[:8]
    note_title = f"E2E Note {note_suffix}"
    note_body = "E2E notes flow content.\nSecond line."
    note_tag = f"e2e-{note_suffix}"

    page.get_by_role("button", name="New note").first.click()
    page.get_by_placeholder("Title").fill(note_title)
    page.get_by_placeholder("Write your note here... (Markdown supported)").fill(note_body)

    tag_select = page.get_by_placeholder("Keywords (tags)")
    tag_select.click()
    page.keyboard.type(note_tag)
    page.keyboard.press("Enter")

    page.get_by_role("button", name="Save").click()
    page.get_by_text("Note created").wait_for()

    search_input = page.get_by_placeholder("Search notes...")
    search_input.fill(note_title)
    page.wait_for_timeout(500)
    result_button = page.get_by_role("button", name=re.compile(re.escape(note_title)))
    result_button.wait_for()
    result_button.click()

    page.get_by_role("button", name="Preview").click()
    page.get_by_text("E2E notes flow content.").wait_for()

    page.get_by_role("button", name="Edit").click()
    updated_body = f"{note_body}\nUpdated."
    page.get_by_placeholder("Write your note here... (Markdown supported)").fill(updated_body)
    page.get_by_role("button", name="Save").click()
    page.get_by_text("Note updated").wait_for()

    page.get_by_role("button", name="Delete").click()
    delete_dialog = page.get_by_role("dialog")
    delete_dialog.get_by_role("button", name="Delete").wait_for()
    delete_dialog.get_by_role("button", name="Delete").click()
    page.get_by_text("Note deleted").wait_for()
