from __future__ import annotations

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (
    get_media_by_url,
    media_dedupe_url_candidates,
    normalize_media_dedupe_url,
)


def test_normalize_media_dedupe_url_http_rules() -> None:
    raw = "HTTPS://Example.COM:443/path//to///doc/?utm_source=abc&b=2&a=1#section"
    normalized = normalize_media_dedupe_url(raw)
    assert normalized == "https://example.com/path/to/doc?a=1&b=2"


def test_media_dedupe_url_candidates_include_raw_for_legacy_rows() -> None:
    raw = "https://Example.com/article/?utm_source=alpha&b=2&a=1"
    candidates = media_dedupe_url_candidates(raw)
    assert candidates[0] == "https://example.com/article?a=1&b=2"
    assert raw in candidates


def test_add_media_with_keywords_dedupes_url_variants(memory_db_factory) -> None:
    db = memory_db_factory("dedupe-url-client")
    content = "Same content body for canonical URL dedupe test."

    first_url = "https://Example.com/article/?utm_source=alpha&b=2&a=1"
    second_url = "https://example.com/article?a=1&b=2"

    media_id_1, media_uuid_1, msg_1 = db.add_media_with_keywords(
        url=first_url,
        title="Canonical URL Seed",
        media_type="document",
        content=content,
        keywords=None,
        transcription_model="whisper-test",
    )

    media_id_2, media_uuid_2, msg_2 = db.add_media_with_keywords(
        url=second_url,
        title="Canonical URL Variant",
        media_type="document",
        content=content,
        keywords=None,
        transcription_model="whisper-test",
        overwrite=False,
    )

    assert media_id_1 == media_id_2
    assert media_uuid_1 == media_uuid_2
    assert msg_1 == "Media 'Canonical URL Seed' added."
    assert "already exists" in msg_2

    row = db.execute_query("SELECT url FROM Media WHERE id = ?", (media_id_1,)).fetchone()
    assert row["url"] == "https://example.com/article?a=1&b=2"


def test_get_media_by_url_matches_variant_forms(memory_db_factory) -> None:
    db = memory_db_factory("get-media-by-url-client")

    media_id, _, _ = db.add_media_with_keywords(
        url="https://example.com/path?a=1&b=2",
        title="Lookup Variant",
        media_type="document",
        content="lookup-content",
        keywords=None,
    )

    fetched = get_media_by_url(db, "https://EXAMPLE.com/path/?utm_source=x&b=2&a=1#frag")
    assert fetched is not None
    assert fetched["id"] == media_id


def test_add_media_with_keywords_identical_content_different_urls_dedupes_by_hash(
    memory_db_factory,
) -> None:
    db = memory_db_factory("dedupe-hash-client")
    content = "Identical content hash should dedupe regardless of differing non-canonical URL forms."

    first_id, first_uuid, _ = db.add_media_with_keywords(
        url="https://example.com/first",
        title="First URL",
        media_type="document",
        content=content,
        keywords=None,
    )

    second_id, second_uuid, msg = db.add_media_with_keywords(
        url="https://example.com/completely-different",
        title="Second URL",
        media_type="document",
        content=content,
        keywords=None,
        overwrite=False,
    )

    assert second_id == first_id
    assert second_uuid == first_uuid
    assert "already exists" in msg
