from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_media_deprecation_window_documented():
    ingestion_doc = _read(
        "Docs/Published/Code_Documentation/Ingestion_Media_Processing.md"
    )
    assert "one-release compatibility window" in ingestion_doc.lower()
    assert "Deprecation" in ingestion_doc
    assert "Release N+1" in ingestion_doc


def test_email_and_web_docs_note_additive_deprecation_headers():
    email_doc = _read("Docs/Published/API-related/Email_Processing_API.md")
    web_doc = _read("Docs/Published/User_Guides/Server/Web_Scraping_Ingestion_Guide.md")
    assert "Deprecation" in email_doc and "Sunset" in email_doc and "Link" in email_doc
    assert "deprecation headers" in web_doc.lower()
