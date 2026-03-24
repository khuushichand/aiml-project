from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
TLDW_PAGE = ROOT / "Docs/Website/index.html"
VADEM_PAGE = ROOT / "Docs/Website/vademhq/index.html"


def parse_html(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


def test_tldw_homepage_keeps_old_live_section_structure():
    soup = parse_html(TLDW_PAGE)

    assert soup.find(id="cta") is not None  # nosec B101
    assert soup.find(id="about") is not None  # nosec B101
    assert soup.find(id="features") is not None  # nosec B101
    assert soup.find(id="community") is not None  # nosec B101
    assert soup.find(id="whats-new") is None  # nosec B101


def test_tldw_homepage_setup_copy_matches_current_repo_guidance():
    text = parse_html(TLDW_PAGE).get_text(" ", strip=True)

    assert "v0.1.26" in text  # nosec B101
    assert "make quickstart" in text  # nosec B101
    assert "make quickstart-docker" in text  # nosec B101
    assert "make quickstart-install" in text  # nosec B101
    assert "make quickstart-prereqs" in text  # nosec B101
    assert "pip install tldw_server" not in text  # nosec B101
    assert "docker compose up" not in text  # nosec B101


def test_tldw_homepage_messaging_centers_the_primer_goal_and_direct_job():
    text = parse_html(TLDW_PAGE).get_text(" ", strip=True)

    assert "Build your own Primer. Ingest, transcribe, search, and query your own material." in text  # nosec B101
    assert "The long-term goal is The Young Lady's Illustrated Primer." in text  # nosec B101
    assert "tldw is an open-source, self-hosted research system." in text  # nosec B101
    assert "OpenAI-compatible Chat / Audio / Embeddings / Evals" in text  # nosec B101
    assert "FastAPI backend + WebUI" in text  # nosec B101
    assert "Hybrid RAG" in text  # nosec B101
    assert "self-hosted step toward" not in text  # nosec B101
    assert "working context" not in text  # nosec B101


def test_tldw_homepage_points_shared_deployments_to_multi_user_guide():
    soup = parse_html(TLDW_PAGE)
    links = [link.get("href", "") for link in soup.find_all("a")]

    assert any("Profile_Docker_Multi_User_Postgres.md" in href for href in links)  # nosec B101


def test_tldw_homepage_structured_data_uses_current_version():
    text = TLDW_PAGE.read_text(encoding="utf-8")

    assert '"softwareVersion": "0.1.26"' in text  # nosec B101


def test_vademhq_page_still_exists_and_is_untouched_in_scope():
    soup = parse_html(VADEM_PAGE)
    text = soup.get_text(" ", strip=True)

    assert VADEM_PAGE.exists()  # nosec B101
    assert "VademHQ" in soup.title.get_text()  # nosec B101
    assert "Start hosted trial" in text  # nosec B101


def test_pages_have_distinct_canonical_urls():
    tldw = parse_html(TLDW_PAGE)
    vadem = parse_html(VADEM_PAGE)

    assert tldw.find("link", rel="canonical")["href"] == "https://tldwproject.com"  # nosec B101
    assert vadem.find("link", rel="canonical")["href"] == "https://vademhq.com"  # nosec B101


def test_both_pages_include_skip_links():
    assert parse_html(TLDW_PAGE).find("a", class_="skip") is not None  # nosec B101
    assert parse_html(VADEM_PAGE).find("a", class_="skip") is not None  # nosec B101
