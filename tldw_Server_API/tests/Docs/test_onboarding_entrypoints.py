from pathlib import Path


def test_readme_start_here_links_to_profile_index() -> None:
    text = Path("README.md").read_text()
    assert "Docs/Getting_Started/README.md" in text
    assert "Local single-user" in text
    assert "Docker single-user" in text


def test_getting_started_index_lists_all_profiles() -> None:
    text = Path("Docs/Getting_Started/README.md").read_text()
    for label in [
        "Local single-user",
        "Docker single-user",
        "Docker multi-user + Postgres",
        "GPU/STT Add-on",
    ]:
        assert label in text
