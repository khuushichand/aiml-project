from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.MediaWiki import Media_Wiki as mediawiki


@pytest.mark.unit
def test_mediawiki_config_lazy_load(monkeypatch):
    mediawiki._mediawiki_import_config_cache = None

    def _boom():
        raise FileNotFoundError("missing config")

    monkeypatch.setattr(mediawiki, "load_mediawiki_import_config", _boom)

    cfg = mediawiki.get_mediawiki_import_config()
    assert cfg == {}
