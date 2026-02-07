from __future__ import annotations

from tldw_Server_API.app.core.config import load_and_log_configs


def test_load_and_log_configs_includes_section_dicts():
    data = load_and_log_configs()
    assert isinstance(data, dict)
    assert isinstance(data.get("Redis"), dict)
    assert isinstance(data.get("Web-Scraping"), dict)
