from pathlib import Path
import pytest


pytestmark = pytest.mark.unit


def test_compat_patchpoints_module_removed():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "media"
        / "compat_patchpoints.py"
    )
    assert not module_path.exists()


def test_media_module_drops_legacy_patchpoints():
    from tldw_Server_API.app.api.v1.endpoints import media as media_mod

    assert not hasattr(media_mod, "_download_url_async")
    assert not hasattr(media_mod, "_save_uploaded_files")


def test_web_scraping_endpoint_resolves_task_without_compat_module():
    source_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "media"
        / "process_web_scraping.py"
    )
    source = source_path.read_text(encoding="utf-8")
    assert "compat_patchpoints" not in source
    assert 'getattr(media_mod, "process_web_scraping_task"' in source
