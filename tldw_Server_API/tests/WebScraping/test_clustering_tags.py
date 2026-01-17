from tldw_Server_API.app.core.Web_Scraping import Article_Extractor_Lib as ael


def test_cluster_tags_respect_top_k():
    html = """
    <html><body>
      <p>Subscribe to the newsletter for price updates.</p>
    </body></html>
    """

    result = ael.extract_cluster_entities(
        html,
        "https://example.com",
        cluster_settings={
            "min_block_chars": 10,
            "min_word_count": 1,
            "tag_top_k": 2,
        },
    )

    assert result["extraction_successful"] is True
    tags = result.get("cluster_tags") or []
    assert tags == ["marketing", "commerce"]
