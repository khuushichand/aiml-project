import uuid

import pytest


@pytest.mark.e2e
def test_knowledge_rag_search_notes(configured_page):
    page = configured_page
    note_suffix = uuid.uuid4().hex[:8]
    note_title = f"E2E Knowledge Note {note_suffix}"
    note_body = f"RAG E2E note content {note_suffix}."

    page.goto("/notes")
    page.get_by_placeholder("Search notes...").wait_for()
    page.get_by_role("button", name="New note").first.click()
    page.get_by_placeholder("Title").fill(note_title)
    page.get_by_placeholder("Write your note here... (Markdown supported)").fill(note_body)
    page.get_by_role("button", name="Save").click()
    page.get_by_text("Note created").wait_for()

    page.goto("/knowledge")
    try:
        page.get_by_text("Quick RAG search").wait_for(timeout=30_000)
    except Exception:
        if page.locator("text=Index knowledge to use Knowledge QA").count() > 0:
            pytest.skip("Knowledge index is empty; ingest or index content before running RAG search.")
        if page.locator("text=Connect to use Knowledge").count() > 0:
            pytest.skip("Knowledge requires a connected server; configure connection before running.")
        if page.locator("text=Explore Knowledge in demo mode").count() > 0:
            pytest.skip("Knowledge demo mode is active; connect to run RAG search.")
        raise

    notes_checkbox = page.get_by_role("checkbox", name="Notes")
    if notes_checkbox.get_attribute("aria-checked") != "true":
        notes_checkbox.click()

    page.get_by_placeholder("Search across configured RAG sources").fill(note_title)
    page.get_by_role("button", name="Search").click()
    page.get_by_text(note_title).wait_for(timeout=120_000)
