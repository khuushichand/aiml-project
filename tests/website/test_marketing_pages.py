from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
TLDW_PAGE = ROOT / "Docs/Website/index.html"
VADEM_PAGE = ROOT / "Docs/Website/vademhq/index.html"


def parse_html(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


def test_tldw_homepage_keeps_open_source_positioning():
    soup = parse_html(TLDW_PAGE)
    text = soup.get_text(" ", strip=True)

    assert "Open-source research assistant" in soup.title.get_text()  # nosec B101 - pytest assertion
    assert soup.find(id="whats-new") is not None  # nosec B101 - pytest assertion
    assert "self-host" in text.lower()  # nosec B101 - pytest assertion
    assert "VademHQ" in text  # nosec B101 - pytest assertion


def test_tldw_homepage_surfaces_recent_progress_and_hosted_pointer():
    soup = parse_html(TLDW_PAGE)
    text = soup.get_text(" ", strip=True)

    assert soup.find(id="whats-new") is not None  # nosec B101 - pytest assertion
    assert "OpenAI-compatible" in text  # nosec B101 - pytest assertion
    assert "Unified RAG" in text  # nosec B101 - pytest assertion
    assert "MCP Unified" in text  # nosec B101 - pytest assertion
    assert "Visit VademHQ" in text  # nosec B101 - pytest assertion


def test_vademhq_page_exists_with_hosted_trial_cta():
    assert VADEM_PAGE.exists()  # nosec B101 - pytest assertion
    soup = parse_html(VADEM_PAGE)
    text = soup.get_text(" ", strip=True)

    assert "Start hosted trial" in text  # nosec B101 - pytest assertion
    assert "built on open-source tldw" in text.lower()  # nosec B101 - pytest assertion
    assert "in progress" in text.lower()  # nosec B101 - pytest assertion


def test_vademhq_page_has_trust_problem_and_cta_sections():
    soup = parse_html(VADEM_PAGE)

    assert soup.find(id="hero") is not None  # nosec B101 - pytest assertion
    assert soup.find(id="trust") is not None  # nosec B101 - pytest assertion
    assert soup.find(id="problem") is not None  # nosec B101 - pytest assertion
    assert soup.find(id="how-it-works") is not None  # nosec B101 - pytest assertion
    assert soup.find(id="roadmap") is not None  # nosec B101 - pytest assertion


def test_pages_have_distinct_canonical_urls():
    tldw = parse_html(TLDW_PAGE)
    vadem = parse_html(VADEM_PAGE)

    assert tldw.find("link", rel="canonical")["href"] == "https://tldwproject.com"  # nosec B101 - pytest assertion
    assert vadem.find("link", rel="canonical")["href"] == "https://vademhq.com"  # nosec B101 - pytest assertion


def test_pages_keep_distinct_primary_intents():
    tldw_text = parse_html(TLDW_PAGE).get_text(" ", strip=True).lower()
    vadem_text = parse_html(VADEM_PAGE).get_text(" ", strip=True).lower()

    assert "get started" in tldw_text  # nosec B101 - pytest assertion
    assert "start hosted trial" in vadem_text  # nosec B101 - pytest assertion
    assert "self-host" in tldw_text  # nosec B101 - pytest assertion
    assert "managed cloud" in vadem_text  # nosec B101 - pytest assertion


def test_both_pages_include_skip_links():
    assert parse_html(TLDW_PAGE).find("a", class_="skip") is not None  # nosec B101 - pytest assertion
    assert parse_html(VADEM_PAGE).find("a", class_="skip") is not None  # nosec B101 - pytest assertion
