from __future__ import annotations

import importlib


def test_pricing_catalog_loads_from_config_file(monkeypatch):
    # Force reload to ensure file overrides are applied afresh
    mod = importlib.import_module('tldw_Server_API.app.core.Usage.pricing_catalog')
    importlib.reload(mod)
    catalog = mod.get_pricing_catalog()

    # Should read from tldw_Server_API/Config_Files/model_pricing.json
    in_per_1k, out_per_1k, estimated = catalog.get_rates('openai', 'gpt-4o')

    # Values set in Config_Files/model_pricing.json
    assert round(in_per_1k, 6) == 0.005
    assert round(out_per_1k, 6) == 0.015
    # File override yields exact match, not estimated
    assert estimated is False
