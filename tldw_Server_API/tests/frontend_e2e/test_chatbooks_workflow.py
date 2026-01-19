import re
import uuid

import pytest


@pytest.mark.e2e
def test_chatbooks_export_with_notes(configured_page):
    page = configured_page
    note_suffix = uuid.uuid4().hex[:8]
    note_title = f"E2E Chatbook Note {note_suffix}"
    note_body = "Chatbooks export needs at least one note."

    page.goto("/notes")
    page.get_by_placeholder("Search notes...").wait_for()
    page.get_by_role("button", name="New note").first.click()
    page.get_by_placeholder("Title").fill(note_title)
    page.get_by_placeholder("Write your note here... (Markdown supported)").fill(note_body)
    page.get_by_role("button", name="Save").click()
    page.get_by_text("Note created").wait_for()

    page.goto("/chatbooks")
    page.get_by_text("Chatbooks Playground").wait_for()

    export_name = f"e2e-chatbook-{note_suffix}"
    export_desc = f"Chatbook export {note_suffix}"
    page.get_by_placeholder("Name").fill(export_name)
    page.get_by_placeholder("Description").fill(export_desc)

    notes_card = page.locator(".ant-card").filter(
        has=page.get_by_text("Notes", exact=True)
    ).first
    notes_card.get_by_role("switch").click()

    page.get_by_role("button", name="Export chatbook").click()
    page.get_by_text(
        re.compile(r"Export (job created|complete)", re.IGNORECASE)
    ).wait_for(timeout=120_000)

    page.get_by_role("tab", name="Jobs").click()
    page.get_by_text("Job status").wait_for()
    page.get_by_text(export_name).wait_for(timeout=120_000)
