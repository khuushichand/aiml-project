import pytest

from tldw_Server_API.app.core.Web_Scraping.scoring import (
    PathDepthScorer,
    KeywordRelevanceScorer,
    ContentTypeScorer,
    FreshnessScorer,
    DomainAuthorityScorer,
    CompositeScorer,
)


@pytest.mark.unit
def test_path_depth_scorer_prefers_optimal():
    s = PathDepthScorer(optimal_depth=3)
    assert s.score("https://ex.com/a/b/c") > s.score("https://ex.com/a/b") > s.score("https://ex.com/a")


@pytest.mark.unit
def test_keyword_relevance_scorer():
    s = KeywordRelevanceScorer(keywords=["python", "ai"])  # weight default 1
    assert s.score("https://ex.com/python/ai") == 1.0
    assert s.score("https://ex.com/python/") == 0.5
    assert s.score("https://ex.com/") == 0.0


@pytest.mark.unit
def test_content_type_scorer():
    s = ContentTypeScorer()
    assert s.score("https://ex.com/index.html") == 1.0
    assert s.score("https://ex.com/report.pdf") == 0.0


@pytest.mark.unit
def test_freshness_scorer():
    s = FreshnessScorer(current_year=2024)
    assert s.score("https://ex.com/2024/post") > s.score("https://ex.com/2020/post")


@pytest.mark.unit
def test_domain_authority_scorer():
    s = DomainAuthorityScorer(domain_weights={"docs.python.org": 1.0, "github.com": 0.8}, default_weight=0.2)
    assert s.score("https://docs.python.org/3/") == 1.0
    assert s.score("https://github.com/") == 0.8
    assert s.score("https://unknown.local/") == 0.2


@pytest.mark.unit
def test_composite_scorer_normalized():
    comp = CompositeScorer(
        [PathDepthScorer(optimal_depth=1), ContentTypeScorer()],
        normalize=True,
    )
    # HTML path at depth 1 should get higher average than PDF at depth 2
    a = comp.score("https://ex.com/a")
    b = comp.score("https://ex.com/a/b.pdf")
    assert a > b
