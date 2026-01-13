from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import (
    clear_extraction_caches,
    extract_article_with_pipeline,
    get_extraction_cache_stats,
)


def test_cluster_fallback_groups_similar_paragraphs():
    html = """
    <html>
      <body>
        <p>Alpha system allows research on renewable energy in 2025.</p>
        <p>Alpha system continues with research findings and energy savings.</p>
        <p>Subscribe now for updates and newsletters.</p>
      </body>
    </html>
    """

    result = extract_article_with_pipeline(
        html,
        "https://example.com",
        strategy_order=["cluster"],
    )

    assert result["extraction_successful"] is True
    assert "Alpha system allows research" in (result.get("content") or "")
    assert "Alpha system continues" in (result.get("content") or "")
    assert "Subscribe now" not in (result.get("content") or "")
    assert result.get("cluster_block_count") == 2


def test_cluster_cache_clear_hook():
    html = """
    <html>
      <body>
        <p>Cache test paragraph one.</p>
        <p>Cache test paragraph two.</p>
      </body>
    </html>
    """

    clear_extraction_caches()
    extract_article_with_pipeline(
        html,
        "https://example.com",
        strategy_order=["cluster"],
    )

    stats = get_extraction_cache_stats()
    assert stats.get("cluster_embedding_cache_size", 0) > 0

    clear_extraction_caches()
    stats = get_extraction_cache_stats()
    assert stats.get("cluster_embedding_cache_size", 0) == 0
