import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace


def _load_patchpoints_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "media"
        / "compat_patchpoints.py"
    )
    spec = importlib.util.spec_from_file_location(
        "media_compat_patchpoints_test_module",
        module_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_get_download_url_async_resolves_callable():
    patchpoints = _load_patchpoints_module()
    sentinel = lambda *args, **kwargs: None
    media_module = SimpleNamespace(_download_url_async=sentinel)
    assert patchpoints.get_download_url_async(media_module) is sentinel


def test_get_save_uploaded_files_resolves_callable():
    patchpoints = _load_patchpoints_module()
    sentinel = lambda *args, **kwargs: None
    media_module = SimpleNamespace(_save_uploaded_files=sentinel)
    assert patchpoints.get_save_uploaded_files(media_module) is sentinel


def test_get_process_web_scraping_task_prefers_media_module_override():
    patchpoints = _load_patchpoints_module()
    sentinel = lambda *args, **kwargs: {"ok": True}
    media_module = SimpleNamespace(process_web_scraping_task=sentinel)
    assert patchpoints.get_process_web_scraping_task(media_module) is sentinel


def test_get_process_web_scraping_task_falls_back_to_service():
    patchpoints = _load_patchpoints_module()
    media_module = SimpleNamespace()
    task = patchpoints.get_process_web_scraping_task(media_module)
    assert callable(task)

